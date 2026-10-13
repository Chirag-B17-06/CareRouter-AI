"""Authentication and role-based authorisation.

* Passwords: scrypt (stdlib) with per-user salt.
* Sessions: short-lived signed JWT bearer tokens; ``token_version`` lets an admin or the
  user revoke every token issued so far.
* Authorisation: every protected route depends on ``require_permission(...)``; patient-scoped
  data additionally goes through ``assert_patient_access``.
* Login throttling: per-account lockout after repeated failures.
"""
import base64
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, FrozenSet, List, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from audit import record_audit
from config import get_settings
from database import get_db
from models_care import User, Patient, USER_ROLES, utcnow

# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------
_STAFF_COMMON = {"conversation:read", "task:read", "patient:read"}

ROLE_PERMISSIONS: Dict[str, FrozenSet[str]] = {
    "admin": frozenset({
        "audio:transcribe", "audio:read", "conversation:write", "conversation:read", "conversation:delete",
        "task:read", "task:write", "task:assign", "task:delete",
        "patient:read", "patient:write", "patient:link", "patient:verify",
        "clinical:read", "clinical:write", "medication:read", "medication:write",
        "appointment:manage", "appointment:read_all", "routing:admin", "user:admin", "audit:read",
        "analytics:read", "followup:approve",
    }),
    "nurse": frozenset(_STAFF_COMMON | {
        "audio:transcribe", "conversation:write", "task:write", "task:assign",
        "patient:write", "patient:link", "clinical:read", "medication:read",
        "appointment:manage", "appointment:read_all", "analytics:read",
    }),
    "clinician": frozenset(_STAFF_COMMON | {
        "audio:transcribe", "audio:read", "conversation:write", "task:write", "task:assign",
        "patient:write", "patient:link", "patient:verify",
        "clinical:read", "clinical:write", "medication:read", "medication:write",
        "appointment:manage", "appointment:read_all", "analytics:read", "followup:approve",
    }),
    "coordinator": frozenset(_STAFF_COMMON | {
        "task:write", "task:assign", "appointment:manage", "appointment:read_all", "analytics:read",
        "patient:link",
    }),
    "pharmacist": frozenset(_STAFF_COMMON | {
        "task:write", "medication:read", "medication:write", "clinical:read",
    }),
    "patient": frozenset({"portal:self"}),
}
# Roles whose task visibility is limited to their own department's queue.
DEPARTMENT_SCOPED_ROLES = {"coordinator", "pharmacist"}
# Roles that see every queue.
ALL_QUEUE_ROLES = {"admin", "nurse", "clinician"}


def has_permission(user: User, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2 ** 14, 8, 1
MIN_PASSWORD_LENGTH = 12


def validate_password_strength(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")
    if password.lower() == password or not re.search(r"\d", password):
        raise ValueError("Password must mix upper and lower case letters and include a digit")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(
        _SCRYPT_N, _SCRYPT_R, _SCRYPT_P,
        base64.b64encode(salt).decode(), base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, hash_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=base64.b64decode(salt_b64),
            n=int(n), r=int(r), p=int(p), dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


# A real hash used to equalise timing when the username does not exist.
_DUMMY_HASH = hash_password("dummy-Password-for-timing-1")


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(user.id),
        "role": user.role,
        "tv": user.token_version,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


def _decode_token(token: str) -> dict:
    return jwt.decode(
        token, get_settings().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "tv"]}
    )


def _unauthorized(detail: str = "Authentication required") -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    try:
        claims = _decode_token(token.strip())
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthorized("Invalid or expired session")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active or user.token_version != claims.get("tv"):
        raise _unauthorized("Invalid or expired session")
    request.state.user = user
    return user


def require_permission(*permissions: str) -> Callable[..., User]:
    """Dependency factory: the caller must hold *all* listed permissions."""

    def dependency(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        missing = [p for p in permissions if not has_permission(user, p)]
        if missing:
            record_audit(
                db, user=user, action="access_denied", resource_type="endpoint",
                resource_id=request.url.path, outcome="denied",
                detail={"required": list(permissions), "method": request.method}, commit=True,
            )
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return user

    dependency.__name__ = "require_" + "_".join(p.replace(":", "_") for p in permissions)
    return dependency


def require_patient_portal(user: User = Depends(get_current_user)) -> User:
    """Patient portal routes: the account must be a patient account bound to a profile."""
    if user.role != "patient" or not user.patient_id:
        raise HTTPException(status_code=403, detail="This area is for patient accounts only")
    return user


def assert_patient_access(user: User, patient_id: int) -> None:
    """Cross-patient isolation: patients may only touch their own profile."""
    if user.role == "patient" and user.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Not found")  # 404 avoids confirming existence


def visible_team_for(user: User) -> Optional[str]:
    """Team whose queue the user is restricted to, or None when they may see all queues."""
    if user.role in DEPARTMENT_SCOPED_ROLES:
        return user.department or "__none__"  # unassigned scoped users see nothing
    return None


# ---------------------------------------------------------------------------
# Login / user management
# ---------------------------------------------------------------------------
def authenticate(db: Session, username: str, password: str, ip: str = "") -> User:
    settings = get_settings()
    user = db.query(User).filter(User.username == username.strip().lower()).first()
    generic = HTTPException(status_code=401, detail="Invalid username or password")

    if not user:
        verify_password(password, _DUMMY_HASH)
        record_audit(db, user=None, action="login_failed", resource_type="user",
                     outcome="denied", detail={"reason_code": "unknown_user"}, commit=True)
        raise generic

    now = utcnow()
    locked_until = user.locked_until
    if locked_until is not None and locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until and locked_until > now:
        record_audit(db, user=user, action="login_blocked", resource_type="user", resource_id=user.id,
                     outcome="denied", detail={"reason_code": "locked"}, commit=True)
        raise HTTPException(status_code=429, detail="Account temporarily locked. Try again later.")

    if not user.is_active or not verify_password(password, user.password_hash):
        user.failed_logins = (user.failed_logins or 0) + 1
        if user.failed_logins >= settings.login_max_failures:
            user.locked_until = now + timedelta(minutes=settings.login_lockout_minutes)
            user.failed_logins = 0
        record_audit(db, user=user, action="login_failed", resource_type="user", resource_id=user.id,
                     outcome="denied", detail={"reason_code": "bad_credentials"}, commit=True)
        raise generic

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    record_audit(db, user=user, action="login", resource_type="user", resource_id=user.id, commit=True)
    return user


def create_user(
    db: Session, *, username: str, password: str, full_name: str, role: str,
    department: Optional[str] = None, patient_id: Optional[int] = None,
) -> User:
    if role not in USER_ROLES:
        raise ValueError(f"Unknown role '{role}'")
    validate_password_strength(password)
    if role == "patient" and not patient_id:
        raise ValueError("Patient accounts must be linked to a patient profile")
    if role != "patient" and patient_id:
        raise ValueError("Only patient accounts can be linked to a patient profile")
    if patient_id and not db.query(Patient).filter(Patient.id == patient_id).first():
        raise ValueError("Linked patient profile does not exist")
    uname = username.strip().lower()
    if db.query(User).filter(User.username == uname).first():
        raise ValueError("Username already exists")
    user = User(
        username=uname, password_hash=hash_password(password), full_name=full_name.strip(),
        role=role, department=department, patient_id=patient_id,
    )
    db.add(user)
    db.flush()
    return user


def bootstrap_admin(db: Session) -> Optional[User]:
    """Create the first admin from BOOTSTRAP_ADMIN_* env vars, only when no users exist."""
    settings = get_settings()
    if db.query(User).count() > 0:
        return None
    if not (settings.bootstrap_admin_username and settings.bootstrap_admin_password):
        return None
    user = create_user(
        db, username=settings.bootstrap_admin_username, password=settings.bootstrap_admin_password,
        full_name="Bootstrap Administrator", role="admin",
    )
    record_audit(db, user=None, action="bootstrap_admin_created", resource_type="user",
                 resource_id=user.id, detail={"note_code": "first_run"})
    db.commit()
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=80)
    password: str = Field(..., min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    department: Optional[str] = None
    patient_id: Optional[int] = None
    permissions: List[str] = []


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(..., min_length=1, max_length=200)
    full_name: str = Field(..., min_length=1, max_length=120)
    role: str
    department: Optional[str] = Field(None, max_length=100)
    patient_id: Optional[int] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, full_name=user.full_name, role=user.role,
        department=user.department, patient_id=user.patient_id,
        permissions=sorted(ROLE_PERMISSIONS.get(user.role, frozenset())),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, payload.username, payload.password)
    db.commit()
    return LoginResponse(
        access_token=create_access_token(user),
        expires_in_seconds=get_settings().access_token_minutes * 60,
        user=user_out(user),
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Revokes every token issued to this account so far."""
    user.token_version += 1
    record_audit(db, user=user, action="logout", resource_type="user", resource_id=user.id)
    db.commit()
    return {"message": "Signed out"}


@router.post("/password")
def change_password(payload: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    try:
        validate_password_strength(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1
    record_audit(db, user=user, action="password_changed", resource_type="user", resource_id=user.id)
    db.commit()
    return {"message": "Password updated. Please sign in again."}


@router.get("/users", response_model=List[UserOut])
def list_users(user: User = Depends(require_permission("user:admin")), db: Session = Depends(get_db)):
    return [user_out(u) for u in db.query(User).order_by(User.id).all()]


@router.post("/users", response_model=UserOut, status_code=201)
def create_user_endpoint(
    payload: UserCreate, admin: User = Depends(require_permission("user:admin")), db: Session = Depends(get_db)
):
    try:
        new_user = create_user(
            db, username=payload.username, password=payload.password, full_name=payload.full_name,
            role=payload.role, department=payload.department, patient_id=payload.patient_id,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    record_audit(db, user=admin, action="user_created", resource_type="user", resource_id=new_user.id,
                 patient_id=new_user.patient_id, detail={"role": new_user.role})
    db.commit()
    return user_out(new_user)


@router.post("/users/{user_id}/deactivate")
def deactivate_user(user_id: int, admin: User = Depends(require_permission("user:admin")), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
    target.is_active = False
    target.token_version += 1
    record_audit(db, user=admin, action="user_deactivated", resource_type="user", resource_id=target.id)
    db.commit()
    return {"message": "User deactivated"}
