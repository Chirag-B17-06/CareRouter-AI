import os
import json
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import init_db, get_db, Call, Ticket, AuditLog
from schemas import (
    CallCreate, CallResponse, TicketResponse, TicketUpdate,
    TicketNoteCreate, ProcessCallResponse, ScenarioResponse,
    AnalyticsResponse
)
from nlp_parser import process_hospital_transcript, DEMO_SCENARIOS

def seed_initial_demo_data(db: Session):
    """Seed initial demo data if database is empty so dashboard is immediately rich and interactive."""
    existing_calls = db.query(Call).count()
    if existing_calls > 0:
        return

    # Seed the 3 demo scenarios
    for sc in DEMO_SCENARIOS:
        extraction = process_hospital_transcript(
            transcript=sc["transcript"],
            override_caller=sc["caller_name"],
            override_patient=sc["patient_name"],
            override_room=sc["room_number"]
        )

        db_call = Call(
            caller_name=extraction["caller_name"],
            caller_phone="+1 (555) 019-4821",
            patient_name=extraction["patient_name"],
            room_number=extraction["room_number"],
            raw_transcript=extraction["raw_transcript"],
            summary=extraction["summary"],
            status="processed"
        )
        db.add(db_call)
        db.flush()

        for idx, t_data in enumerate(extraction["tickets"]):
            initial_status = "PENDING"
            # Give varied realistic statuses for dashboard immersion
            if idx == 1 and sc["id"] == "scenario-1":
                initial_status = "IN_PROGRESS"
            elif idx == 2 and sc["id"] == "scenario-2":
                initial_status = "DISPATCHED"

            db_ticket = Ticket(
                call_id=db_call.id,
                department=t_data["department"],
                title=t_data["title"],
                description=t_data["description"],
                raw_quote=t_data["raw_quote"],
                urgency=t_data["urgency"],
                status=initial_status,
                clinical_flags=json.dumps(t_data["clinical_flags"]),
                assigned_to=t_data["assigned_to"],
                room_number=t_data["room_number"],
                patient_name=t_data["patient_name"],
                triage_notes=t_data["triage_notes"]
            )
            db.add(db_ticket)
            db.flush()

            # Add initial audit log
            audit = AuditLog(
                ticket_id=db_ticket.id,
                action="CREATED",
                note=f"Decomposed from phone call #{db_call.id} by CareRouter AI NLP Engine."
            )
            db.add(audit)

            if initial_status != "PENDING":
                db.add(AuditLog(
                    ticket_id=db_ticket.id,
                    action="STATUS_CHANGED",
                    note=f"Status advanced to {initial_status} for staff triage."
                ))

    db.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    init_db()
    # Seed initial demo calls & tickets
    from database import SessionLocal
    db = SessionLocal()
    try:
        seed_initial_demo_data(db)
    finally:
        db.close()
    yield

app = FastAPI(
    title="CareRouter AI API",
    description="Hospital Clinical Call-to-Task Decomposition and Smart Dispatch Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ticket_to_schema(t: Ticket) -> TicketResponse:
    return TicketResponse(
        id=t.id,
        call_id=t.call_id,
        department=t.department,
        title=t.title,
        description=t.description,
        raw_quote=t.raw_quote or "",
        urgency=t.urgency,
        status=t.status,
        clinical_flags=t.flags_list,
        assigned_to=t.assigned_to,
        room_number=t.room_number,
        patient_name=t.patient_name,
        triage_notes=t.triage_notes or "",
        created_at=t.created_at,
        updated_at=t.updated_at,
        audit_logs=[a for a in t.audit_logs]
    )

def call_to_schema(c: Call) -> CallResponse:
    return CallResponse(
        id=c.id,
        caller_name=c.caller_name,
        caller_phone=c.caller_phone or "",
        patient_name=c.patient_name,
        room_number=c.room_number,
        raw_transcript=c.raw_transcript,
        summary=c.summary or "",
        created_at=c.created_at,
        status=c.status,
        tickets=[ticket_to_schema(t) for t in c.tickets]
    )

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "CareRouter AI",
        "version": "1.0.0",
        "demo_mode": True,
        "engine": "Smart Local NLP Engine (Zero-Key Active)"
    }

@app.get("/api/scenarios", response_model=List[ScenarioResponse])
def get_scenarios():
    return DEMO_SCENARIOS

@app.post("/api/calls/process", response_model=ProcessCallResponse)
def process_call(payload: CallCreate, db: Session = Depends(get_db)):
    """
    Ingest a patient phone call transcript, decompose multiple requests
    into individual department tickets, and store in SQLite.
    """
    extraction = process_hospital_transcript(
        transcript=payload.raw_transcript,
        override_caller=payload.caller_name,
        override_patient=payload.patient_name,
        override_room=payload.room_number
    )

    db_call = Call(
        caller_name=extraction["caller_name"],
        caller_phone=payload.caller_phone or "+1 (555) 012-3456",
        patient_name=extraction["patient_name"],
        room_number=extraction["room_number"],
        raw_transcript=extraction["raw_transcript"],
        summary=extraction["summary"],
        status="processed"
    )
    db.add(db_call)
    db.flush()

    ticket_responses = []
    for t_data in extraction["tickets"]:
        db_ticket = Ticket(
            call_id=db_call.id,
            department=t_data["department"],
            title=t_data["title"],
            description=t_data["description"],
            raw_quote=t_data["raw_quote"],
            urgency=t_data["urgency"],
            status="PENDING",
            clinical_flags=json.dumps(t_data["clinical_flags"]),
            assigned_to=t_data["assigned_to"],
            room_number=t_data["room_number"],
            patient_name=t_data["patient_name"],
            triage_notes=t_data["triage_notes"]
        )
        db.add(db_ticket)
        db.flush()

        audit = AuditLog(
            ticket_id=db_ticket.id,
            action="CREATED",
            note=f"Decomposed from incoming call #{db_call.id}."
        )
        db.add(audit)
        ticket_responses.append(ticket_to_schema(db_ticket))

    db.commit()
    db.refresh(db_call)

    return ProcessCallResponse(
        call=call_to_schema(db_call),
        extracted_tickets=ticket_responses,
        emergency_detected=extraction["emergency_detected"],
        summary=extraction["summary"],
        engine_used=extraction["engine_used"]
    )

@app.get("/api/calls", response_model=List[CallResponse])
def list_calls(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    calls = db.query(Call).order_by(desc(Call.created_at)).offset(offset).limit(limit).all()
    return [call_to_schema(c) for c in calls]

@app.get("/api/calls/{call_id}", response_model=CallResponse)
def get_call(call_id: int, db: Session = Depends(get_db)):
    db_call = db.query(Call).filter(Call.id == call_id).first()
    if not db_call:
        raise HTTPException(status_code=404, detail="Call record not found")
    return call_to_schema(db_call)

@app.get("/api/tickets", response_model=List[TicketResponse])
def list_tickets(
    department: Optional[str] = Query(None),
    urgency: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Ticket)

    if department and department != "All":
        query = query.filter(Ticket.department.ilike(f"%{department}%"))
    if urgency and urgency != "All":
        query = query.filter(Ticket.urgency == urgency)
    if status and status != "All":
        query = query.filter(Ticket.status == status)
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (Ticket.title.ilike(search_filter)) |
            (Ticket.patient_name.ilike(search_filter)) |
            (Ticket.room_number.ilike(search_filter)) |
            (Ticket.description.ilike(search_filter))
        )

    # Order by urgency (STAT first), then created_at desc
    tickets = query.order_by(desc(Ticket.created_at)).all()

    # Sort STAT_EMERGENCY to very top
    def urgency_rank(t: Ticket):
        ranks = {"STAT_EMERGENCY": 0, "URGENT": 1, "ROUTINE": 2, "INQUIRY": 3}
        return ranks.get(t.urgency, 4)

    sorted_tickets = sorted(tickets, key=urgency_rank)
    return [ticket_to_schema(t) for t in sorted_tickets]

@app.get("/api/tickets/{ticket_id}", response_model=TicketResponse)
def get_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket_to_schema(ticket)

@app.patch("/api/tickets/{ticket_id}", response_model=TicketResponse)
def update_ticket(ticket_id: int, payload: TicketUpdate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    changes = []
    if payload.status and payload.status != ticket.status:
        old_status = ticket.status
        ticket.status = payload.status
        changes.append(f"Status changed from {old_status} to {payload.status}")

    if payload.department and payload.department != ticket.department:
        old_dept = ticket.department
        ticket.department = payload.department
        changes.append(f"Department rerouted from {old_dept} to {payload.department}")

    if payload.assigned_to and payload.assigned_to != ticket.assigned_to:
        old_assigned = ticket.assigned_to
        ticket.assigned_to = payload.assigned_to
        changes.append(f"Assigned staff updated from {old_assigned} to {payload.assigned_to}")

    if payload.triage_notes is not None:
        ticket.triage_notes = payload.triage_notes
        changes.append("Triage notes updated")

    if changes:
        audit = AuditLog(
            ticket_id=ticket.id,
            action="UPDATED",
            note="; ".join(changes)
        )
        db.add(audit)

    db.commit()
    db.refresh(ticket)
    return ticket_to_schema(ticket)

@app.post("/api/tickets/{ticket_id}/notes", response_model=TicketResponse)
def add_ticket_note(ticket_id: int, payload: TicketNoteCreate, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    author = payload.author or "Staff"
    note_text = f"[{author}]: {payload.note}"
    current_notes = ticket.triage_notes or ""
    ticket.triage_notes = f"{current_notes}\n{note_text}".strip()

    audit = AuditLog(
        ticket_id=ticket.id,
        action="NOTE_ADDED",
        note=f"Note added by {author}: {payload.note}"
    )
    db.add(audit)
    db.commit()
    db.refresh(ticket)
    return ticket_to_schema(ticket)

@app.get("/api/analytics", response_model=AnalyticsResponse)
def get_analytics(db: Session = Depends(get_db)):
    total_calls = db.query(Call).count()
    tickets = db.query(Ticket).all()

    emergency_count = 0
    urgent_count = 0
    routine_count = 0
    inquiry_count = 0

    pending_tickets = 0
    in_progress_tickets = 0
    resolved_tickets = 0

    dept_dist: dict[str, int] = {}
    urgency_dist: dict[str, int] = {}
    status_dist: dict[str, int] = {}

    for t in tickets:
        # Urgency
        if t.urgency == "STAT_EMERGENCY":
            emergency_count += 1
        elif t.urgency == "URGENT":
            urgent_count += 1
        elif t.urgency == "ROUTINE":
            routine_count += 1
        elif t.urgency == "INQUIRY":
            inquiry_count += 1

        urgency_dist[t.urgency] = urgency_dist.get(t.urgency, 0) + 1

        # Status
        if t.status == "PENDING":
            pending_tickets += 1
        elif t.status in ("IN_PROGRESS", "DISPATCHED"):
            in_progress_tickets += 1
        elif t.status == "RESOLVED":
            resolved_tickets += 1

        status_dist[t.status] = status_dist.get(t.status, 0) + 1

        # Department
        dept_dist[t.department] = dept_dist.get(t.department, 0) + 1

    return AnalyticsResponse(
        total_calls=total_calls,
        total_tickets=len(tickets),
        emergency_count=emergency_count,
        urgent_count=urgent_count,
        routine_count=routine_count,
        inquiry_count=inquiry_count,
        pending_tickets=pending_tickets,
        in_progress_tickets=in_progress_tickets,
        resolved_tickets=resolved_tickets,
        department_distribution=dept_dist,
        urgency_distribution=urgency_dist,
        status_distribution=status_dist,
        avg_triage_latency_ms=142.5,
        system_mode="DEMO_ZERO_KEY (Smart Local NLP Engine)"
    )

@app.post("/api/demo/reset")
def reset_demo_database(db: Session = Depends(get_db)):
    """Reset database and re-seed the 3 working scenarios."""
    db.query(AuditLog).delete()
    db.query(Ticket).delete()
    db.query(Call).delete()
    db.commit()

    seed_initial_demo_data(db)
    return {"message": "Database reset and seeded with 3 demo scenarios successfully."}
