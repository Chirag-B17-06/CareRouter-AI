"""Shared test configuration.

Environment is prepared *before* ``main`` is imported by any test module:
  * the in-process rate limiter is disabled (it would throttle the large test suite);
  * a fixed JWT secret is used.

Legacy test modules (written before authentication existed) exercise business logic through a
signed-in administrator.  That is done with a ``dependency_overrides`` entry on
``get_current_user`` - the permission checks themselves still run.  Tests that exercise real
authentication/authorisation carry ``@pytest.mark.real_auth`` and get no override.

The ``care`` fixture gives new tests an isolated in-memory database (foreign keys enforced),
synchronous ASR job execution and helpers to create users with real signed tokens.
"""
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "0")
os.environ.setdefault("JWT_SECRET", "test-secret-test-secret-test-secret-0123456789")
os.environ.setdefault("APP_ENV", "test")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "real_auth: run without the default signed-in test administrator")


@pytest.fixture(autouse=True)
def _default_signed_in_admin(request):
    from main import app
    from auth import get_current_user
    from models_care import User

    if request.node.get_closest_marker("real_auth"):
        yield
        return

    admin = User(id=None, username="legacy-test-admin", password_hash="x", full_name="Test Administrator",
                 role="admin", is_active=True, token_version=0)
    app.dependency_overrides[get_current_user] = lambda: admin
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _fk_pragma(engine):
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


def build_care(engine):
    """Wire the app to ``engine`` and return a helper namespace."""
    from fastapi.testclient import TestClient
    from database import Base, get_db
    import models_care  # noqa: F401  (register tables)
    from main import app
    from asr import jobs as asr_jobs
    from asr import service as asr_service
    from auth import create_user, create_access_token

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    asr_jobs.session_factory = Session
    asr_jobs.set_executor(asr_jobs.InlineExecutor())
    asr_service.reset_registry()

    client = TestClient(app)
    counter = {"n": 0}

    def make_user(role="nurse", department=None, patient=None, full_name=None, username=None):
        counter["n"] += 1
        uname = username or f"{role}{counter['n']}"
        with Session() as db:
            user = create_user(
                db, username=uname, password="Str0ng-Passw0rd!", full_name=full_name or f"{role.title()} {counter['n']}",
                role=role, department=department, patient_id=patient.id if patient else None,
            )
            db.commit()
            headers = {"Authorization": f"Bearer {create_access_token(user)}"}
            return SimpleNamespace(id=user.id, username=uname, role=role, headers=headers, full_name=user.full_name)

    def make_patient(name="Test Patient", **kw):
        from models_care import Patient
        from patient_matching import normalize_name, phonetic_key
        with Session() as db:
            p = Patient(full_name=name, name_key=normalize_name(name), phonetic_key=phonetic_key(name), **kw)
            db.add(p)
            db.commit()
            return SimpleNamespace(id=p.id, uid=p.patient_uid, name=name)

    return SimpleNamespace(client=client, Session=Session, engine=engine, make_user=make_user,
                           make_patient=make_patient, app=app)


@pytest.fixture
def care(request):
    """Isolated in-memory database, unauthenticated client and user factory."""
    from database import get_db
    from main import app
    from asr import jobs as asr_jobs
    from asr import service as asr_service

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    _fk_pragma(engine)
    ns = build_care(engine)
    yield ns
    app.dependency_overrides.pop(get_db, None)
    asr_jobs.set_executor(None)
    asr_jobs.session_factory = None
    asr_service.reset_registry()
    engine.dispose()   # throwaway database: no drop_all (circular users<->patients FK)


@pytest.fixture
def care_file(tmp_path):
    """File-backed database with real concurrent connections (for race-condition tests)."""
    from database import get_db
    from main import app
    from asr import jobs as asr_jobs
    from asr import service as asr_service

    engine = create_engine(f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False, "timeout": 30})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, record):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.close()

    ns = build_care(engine)
    yield ns
    app.dependency_overrides.pop(get_db, None)
    asr_jobs.set_executor(None)
    asr_jobs.session_factory = None
    asr_service.reset_registry()
    engine.dispose()   # throwaway database: no drop_all (circular users<->patients FK)
