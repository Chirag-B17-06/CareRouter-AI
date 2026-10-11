import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./care_router.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    caller_name = Column(String(100), default="Unknown Caller")
    caller_phone = Column(String(50), default="")
    patient_name = Column(String(100), default="Unknown Patient")
    room_number = Column(String(50), default="Unassigned")
    raw_transcript = Column(Text, nullable=False)
    summary = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    status = Column(String(50), default="processed")

    tickets = relationship("Ticket", back_populates="call", cascade="all, delete-orphan")

class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("calls.id"), nullable=True)
    department = Column(String(100), nullable=False, index=True) # Rapid Response, Nursing, Pharmacy, Dietary, Administration, Facilities
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    raw_quote = Column(Text, default="")
    urgency = Column(String(50), nullable=False, index=True) # STAT_EMERGENCY, URGENT, ROUTINE, INQUIRY
    status = Column(String(50), default="PENDING", index=True) # PENDING, IN_PROGRESS, DISPATCHED, RESOLVED
    clinical_flags = Column(Text, default="[]") # JSON string array
    assigned_to = Column(String(100), default="Unassigned")
    room_number = Column(String(50), default="Unassigned")
    patient_name = Column(String(100), default="Unknown Patient")
    triage_notes = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    call = relationship("Call", back_populates="tickets")
    audit_logs = relationship("AuditLog", back_populates="ticket", cascade="all, delete-orphan")

    @property
    def flags_list(self):
        try:
            return json.loads(self.clinical_flags) if self.clinical_flags else []
        except Exception:
            return []

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    action = Column(String(100), nullable=False) # CREATED, STATUS_CHANGED, ASSIGNED, NOTE_ADDED
    note = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    ticket = relationship("Ticket", back_populates="audit_logs")

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
