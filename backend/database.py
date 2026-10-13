import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean, event
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./care_router.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Enforce SQLite foreign keys, WAL mode for concurrency, and busy timeout
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(100), nullable=True, index=True)
    caller_name = Column(String(100), default="Unknown Caller")
    caller_phone = Column(String(50), default="")
    patient_name = Column(String(100), default="Unknown Patient")
    room_number = Column(String(50), default="Unassigned")
    raw_transcript = Column(Text, nullable=False) # In original language (Kannada, Hindi, or English)
    language = Column(String(20), default="en") # kn, hi, en
    language_confidence = Column(Float, default=1.0)
    translated_transcript = Column(Text, default="") # English translation if non-English
    summary = Column(Text, default="")
    audio_filename = Column(String(255), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default="processed")

    tickets = relationship("Ticket", back_populates="call", cascade="all, delete-orphan")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    department = Column(String(100), nullable=False, index=True)
    category = Column(String(150), default="Nursing and patient care", index=True)
    intent = Column(String(100), default="general_request", index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    raw_quote = Column(Text, default="") # Quote in original language
    translated_quote = Column(Text, default="") # English translation if applicable
    language = Column(String(20), default="en")
    urgency = Column(String(50), nullable=False, index=True) # STAT_EMERGENCY, URGENT, ROUTINE, INQUIRY
    priority_rationale = Column(Text, default="")
    required_action = Column(Text, default="")
    explicit_deadline = Column(String(100), nullable=True, default=None)
    confidence_score = Column(Float, default=1.0)
    source_timestamp = Column(String(100), nullable=True, default=None)
    requires_human_review = Column(Boolean, default=False, index=True)
    human_review_reason = Column(Text, default="")
    urgency_evidence = Column(Text, default="{}") # JSON object string
    status = Column(String(50), default="PENDING", index=True) # PENDING, IN_PROGRESS, DISPATCHED, RESOLVED
    clinical_flags = Column(Text, default="[]") # JSON string array
    assigned_to = Column(String(100), default="Unassigned")
    assigned_team = Column(String(100), default="Rapid Response & Critical Nursing", index=True)
    assigned_staff = Column(String(100), default="Unassigned")
    is_acknowledged = Column(Boolean, default=False, index=True)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    sla_minutes = Column(Integer, default=60)
    deadline_at = Column(DateTime, nullable=True, index=True)
    escalation_level = Column(Integer, default=0, index=True)
    escalated_at = Column(DateTime, nullable=True)
    escalation_reason = Column(Text, default="")
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_notes = Column(Text, default="")
    is_reviewed = Column(Boolean, default=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(String(100), nullable=True)
    review_notes = Column(Text, default="")
    room_number = Column(String(50), default="Unassigned")
    patient_name = Column(String(100), default="Unknown Patient")
    triage_notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    call = relationship("Call", back_populates="tickets")
    audit_logs = relationship("AuditLog", back_populates="ticket", cascade="all, delete-orphan", order_by="AuditLog.created_at.desc()")

    @property
    def flags_list(self):
        try:
            return json.loads(self.clinical_flags) if self.clinical_flags else []
        except Exception:
            return []

    @property
    def evidence_data(self):
        try:
            return json.loads(self.urgency_evidence) if self.urgency_evidence else {}
        except Exception:
            return {}

    @property
    def is_overdue(self) -> bool:
        if self.status == "RESOLVED" or not self.deadline_at:
            return False
        now_utc = datetime.now(timezone.utc)
        target_dl = self.deadline_at
        if target_dl.tzinfo is None:
            target_dl = target_dl.replace(tzinfo=timezone.utc)
        return now_utc > target_dl

    @property
    def is_escalated(self) -> bool:
        return bool(self.escalation_level and self.escalation_level > 0)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    action = Column(String(100), nullable=False)
    note = Column(Text, default="")
    actor = Column(String(100), default="Clinical Staff")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    ticket = relationship("Ticket", back_populates="audit_logs")

def init_db():
    Base.metadata.create_all(bind=engine)
    # Automatic backward-compatible column addition for SQLite
    if DATABASE_URL.startswith("sqlite"):
        import sqlite3
        db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
        if os.path.exists(db_path):
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                # Migrate calls table
                cursor.execute("PRAGMA table_info(calls)")
                call_cols = {row[1] for row in cursor.fetchall()}
                new_call_cols = [
                    ("idempotency_key", "VARCHAR(100) DEFAULT NULL"),
                    ("caller_name", "VARCHAR(100) DEFAULT 'Unknown Caller'"),
                    ("caller_phone", "VARCHAR(50) DEFAULT ''"),
                    ("patient_name", "VARCHAR(100) DEFAULT 'Unknown Patient'"),
                    ("room_number", "VARCHAR(50) DEFAULT 'Unassigned'"),
                    ("language", "VARCHAR(20) DEFAULT 'en'"),
                    ("language_confidence", "FLOAT DEFAULT 1.0"),
                    ("translated_transcript", "TEXT DEFAULT ''"),
                    ("summary", "TEXT DEFAULT ''"),
                    ("audio_filename", "VARCHAR(255) DEFAULT ''"),
                    ("status", "VARCHAR(50) DEFAULT 'processed'"),
                ]
                for col_name, col_def in new_call_cols:
                    if col_name not in call_cols:
                        cursor.execute(f"ALTER TABLE calls ADD COLUMN {col_name} {col_def}")

                # Migrate tickets table
                cursor.execute("PRAGMA table_info(tickets)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                new_columns = [
                    ("category", "VARCHAR(150) DEFAULT 'Nursing and patient care'"),
                    ("intent", "VARCHAR(100) DEFAULT 'general_request'"),
                    ("priority_rationale", "TEXT DEFAULT ''"),
                    ("required_action", "TEXT DEFAULT ''"),
                    ("explicit_deadline", "VARCHAR(100) DEFAULT NULL"),
                    ("confidence_score", "FLOAT DEFAULT 1.0"),
                    ("source_timestamp", "VARCHAR(100) DEFAULT NULL"),
                    ("requires_human_review", "BOOLEAN DEFAULT 0"),
                    ("human_review_reason", "TEXT DEFAULT ''"),
                    ("urgency_evidence", "TEXT DEFAULT '{}'"),
                    ("assigned_team", "VARCHAR(100) DEFAULT 'Rapid Response & Critical Nursing'"),
                    ("assigned_staff", "VARCHAR(100) DEFAULT 'Unassigned'"),
                    ("is_acknowledged", "BOOLEAN DEFAULT 0"),
                    ("acknowledged_at", "DATETIME DEFAULT NULL"),
                    ("acknowledged_by", "VARCHAR(100) DEFAULT NULL"),
                    ("sla_minutes", "INTEGER DEFAULT 60"),
                    ("deadline_at", "DATETIME DEFAULT NULL"),
                    ("escalation_level", "INTEGER DEFAULT 0"),
                    ("escalated_at", "DATETIME DEFAULT NULL"),
                    ("escalation_reason", "TEXT DEFAULT ''"),
                    ("resolved_at", "DATETIME DEFAULT NULL"),
                    ("resolved_by", "VARCHAR(100) DEFAULT NULL"),
                    ("resolution_notes", "TEXT DEFAULT ''"),
                    ("is_reviewed", "BOOLEAN DEFAULT 0"),
                    ("reviewed_at", "DATETIME DEFAULT NULL"),
                    ("reviewed_by", "VARCHAR(100) DEFAULT NULL"),
                    ("review_notes", "TEXT DEFAULT ''"),
                ]
                for col_name, col_def in new_columns:
                    if col_name not in existing_cols:
                        cursor.execute(f"ALTER TABLE tickets ADD COLUMN {col_name} {col_def}")

                # Also migrate audit_logs table
                cursor.execute("PRAGMA table_info(audit_logs)")
                audit_cols = {row[1] for row in cursor.fetchall()}
                if "actor" not in audit_cols:
                    cursor.execute("ALTER TABLE audit_logs ADD COLUMN actor VARCHAR(100) DEFAULT 'Clinical Staff'")
                if "note" not in audit_cols:
                    cursor.execute("ALTER TABLE audit_logs ADD COLUMN note TEXT DEFAULT ''")

                conn.commit()
                conn.close()
            except Exception as e:
                pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
