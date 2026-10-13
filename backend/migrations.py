"""Minimal versioned schema migrations.

The project had no migration tool (``init_db`` used ``create_all`` plus ad-hoc ALTERs), so
this keeps the same stack and adds a ``schema_migrations`` ledger.  New *tables* come from
``Base.metadata.create_all``; each migration here only has to handle changes to tables that
may already exist in a deployed database (new columns, indexes).

Run automatically from ``init_db()``; also runnable as ``python manage.py migrate``.
"""
import logging
from datetime import datetime, timezone
from typing import Callable, List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("carerouter.migrations")


def _add_missing_columns(engine: Engine, table: str, columns: List[Tuple[str, str]]) -> None:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    with engine.begin() as conn:
        for name, ddl in columns:
            if name not in existing:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))


def m0002_patient_coordination_columns(engine: Engine) -> None:
    _add_missing_columns(engine, "calls", [
        ("patient_id", "INTEGER REFERENCES patients(id)"),
        ("patient_match_status", "VARCHAR(30) DEFAULT 'none'"),
        ("patient_match_candidates", "TEXT DEFAULT '[]'"),
        ("extraction_json", "TEXT DEFAULT '{}'"),
        ("extraction_provider", "VARCHAR(40) DEFAULT ''"),
        ("source_channel", "VARCHAR(20) DEFAULT 'manual'"),
        ("recording_consent", "BOOLEAN DEFAULT 0"),
        ("original_asr_transcript", "TEXT DEFAULT ''"),
        ("transcription_job_id", "VARCHAR(32)"),
        ("created_by_user_id", "INTEGER REFERENCES users(id)"),
    ])
    _add_missing_columns(engine, "tickets", [
        ("patient_id", "INTEGER REFERENCES patients(id)"),
        ("task_category", "VARCHAR(40) DEFAULT 'general_patient_support'"),
        ("routing_reason", "TEXT DEFAULT ''"),
        ("routing_rule_id", "INTEGER"),
        ("dedupe_key", "VARCHAR(64)"),
    ])


def m0003_indexes(engine: Engine) -> None:
    stmts = [
        "CREATE INDEX IF NOT EXISTS ix_calls_patient_id ON calls (patient_id)",
        "CREATE INDEX IF NOT EXISTS ix_tickets_patient_id ON tickets (patient_id)",
        "CREATE INDEX IF NOT EXISTS ix_tickets_task_category ON tickets (task_category)",
        # Duplicate-task guard: the same extracted task cannot be inserted twice for one conversation.
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_tickets_call_dedupe ON tickets (call_id, dedupe_key)",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


MIGRATIONS: List[Tuple[int, str, Callable[[Engine], None]]] = [
    (2, "patient_coordination_columns", m0002_patient_coordination_columns),
    (3, "indexes", m0003_indexes),
]


def run_migrations(engine: Engine) -> List[int]:
    """Apply pending migrations in order. Returns the versions applied in this run."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, applied_at VARCHAR(40) NOT NULL)"
        ))
        done = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}

    applied: List[int] = []
    for version, name, fn in MIGRATIONS:
        if version in done:
            continue
        fn(engine)
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO schema_migrations (version, name, applied_at) VALUES (:v, :n, :t)"),
                {"v": version, "n": name, "t": datetime.now(timezone.utc).isoformat()},
            )
        applied.append(version)
        logger.info("Applied migration %s (%s)", version, name)
    return applied
