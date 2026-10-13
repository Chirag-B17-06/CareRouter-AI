"""Append-only, hash-chained audit events for sensitive access and changes.

Each event stores ``sha256(prev_hash + canonical_json(event))`` so any later edit or
deletion of a row breaks the chain and is detectable with ``verify_chain``.  Event
``detail`` is restricted to identifiers and field *names*; free-text clinical content and
direct identifiers are stripped before storage so the audit trail itself does not become
a second copy of the medical record.
"""
import hashlib
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from sqlalchemy.orm import Session

from models_care import AuditEvent

_chain_lock = threading.Lock()  # serialises read-last-hash + insert within this process

_FORBIDDEN_DETAIL_KEYS = {
    "transcript", "raw_transcript", "translated_transcript", "text", "note", "notes", "description",
    "message", "name", "full_name", "patient_name", "phone", "email", "password", "token", "reason",
    "instruction", "resolution_notes", "triage_notes",
}
_MAX_VALUE_LEN = 200


def _clean_detail(detail: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    cleaned: Dict[str, Any] = {}
    for key, value in (detail or {}).items():
        if str(key).lower() in _FORBIDDEN_DETAIL_KEYS:
            cleaned[key] = "[omitted]"
        elif isinstance(value, (int, float, bool)) or value is None:
            cleaned[key] = value
        elif isinstance(value, (list, tuple)):
            cleaned[key] = [str(v)[:_MAX_VALUE_LEN] for v in value][:50]
        else:
            cleaned[key] = str(value)[:_MAX_VALUE_LEN]
    return cleaned


def _canonical(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    return hashlib.sha256((prev_hash + _canonical(payload)).encode("utf-8")).hexdigest()


def _payload_of(ev: AuditEvent) -> Dict[str, Any]:
    occurred = ev.occurred_at
    if occurred.tzinfo is None:
        occurred = occurred.replace(tzinfo=timezone.utc)
    return {
        "occurred_at": occurred.isoformat(),
        "actor_user_id": ev.actor_user_id,
        "actor_role": ev.actor_role,
        "action": ev.action,
        "resource_type": ev.resource_type,
        "resource_id": ev.resource_id,
        "patient_id": ev.patient_id,
        "outcome": ev.outcome,
        "detail": ev.detail,
    }


def record_audit(
    db: Session,
    *,
    user: Any,
    action: str,
    resource_type: str,
    resource_id: Any = None,
    patient_id: Optional[int] = None,
    outcome: str = "success",
    detail: Optional[Dict[str, Any]] = None,
    commit: bool = False,
) -> AuditEvent:
    """Add an audit event to the current session (and commit it when ``commit`` is true).

    ``user`` may be a ``User``, ``None`` (system / unauthenticated) or any object with
    ``id`` and ``role`` attributes.
    """
    with _chain_lock:
        last = db.query(AuditEvent).order_by(AuditEvent.id.desc()).first()
        prev_hash = last.event_hash if last else ""
        ev = AuditEvent(
            occurred_at=datetime.now(timezone.utc),
            actor_user_id=getattr(user, "id", None),
            actor_role=getattr(user, "role", None),
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            patient_id=patient_id,
            outcome=outcome,
            detail=_canonical(_clean_detail(detail)),
            prev_hash=prev_hash,
        )
        ev.event_hash = _compute_hash(prev_hash, _payload_of(ev))
        db.add(ev)
        db.flush()
        if commit:
            db.commit()
    return ev


def verify_chain(db: Session) -> Tuple[bool, Optional[int]]:
    """Recompute the chain. Returns (ok, id_of_first_broken_event)."""
    prev = ""
    for ev in db.query(AuditEvent).order_by(AuditEvent.id.asc()).yield_per(500):
        if ev.prev_hash != prev or ev.event_hash != _compute_hash(prev, _payload_of(ev)):
            return False, ev.id
        prev = ev.event_hash
    return True, None
