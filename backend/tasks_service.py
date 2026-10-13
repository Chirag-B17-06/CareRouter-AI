"""Task (ticket) creation shared by conversation intake and the patient portal.

Centralises SLA calculation, routing, duplicate prevention and the per-ticket audit trail so
every path that creates work behaves the same way.
"""
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import AuditLog, Ticket
from routing import (
    DEFAULT_SLA_MINUTES, get_policy, route_task, task_category_for,
)

# Original lifecycle plus the extended statuses requested for coordination work.
LEGACY_STATUSES = ("PENDING", "IN_PROGRESS", "DISPATCHED", "RESOLVED")
EXTENDED_STATUSES = ("AWAITING_REVIEW", "ASSIGNED", "AWAITING_PATIENT", "AWAITING_EXTERNAL", "CLOSED")
ALLOWED_STATUSES = LEGACY_STATUSES + EXTENDED_STATUSES
TERMINAL_STATUSES = ("RESOLVED", "CLOSED")


def calculate_sla_and_deadline(
    urgency: str, explicit_deadline: Optional[str] = None, created_at: Optional[datetime] = None,
    sla_map: Optional[Dict[str, int]] = None,
) -> tuple[int, datetime]:
    """SLA minutes and target completion time. ``sla_map`` comes from the admin policy."""
    base_time = created_at or datetime.now(timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)
    sla_mins = (sla_map or DEFAULT_SLA_MINUTES).get(urgency, 120)

    if explicit_deadline:
        dl_lower = explicit_deadline.lower()
        if "within 30 min" in dl_lower:
            sla_mins = min(sla_mins, 30)
        elif "within 1 hour" in dl_lower or "within 1 hr" in dl_lower:
            sla_mins = min(sla_mins, 60)
        elif "within 2 hour" in dl_lower or "within 2 hr" in dl_lower:
            sla_mins = min(sla_mins, 120)
    return sla_mins, base_time + timedelta(minutes=sla_mins)


def dedupe_key(call_id: Optional[int], draft: Dict[str, Any]) -> str:
    basis = re.sub(r"\s+", " ", (draft.get("raw_quote") or draft.get("title") or "")).strip().casefold()
    raw = f"{call_id}|{draft.get('category', '')}|{draft.get('urgency', '')}|{basis}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_ticket(
    db: Session, draft: Dict[str, Any], *, call_id: Optional[int], patient_id: Optional[int],
    actor: str, source_note: str, dedupe: bool = True,
) -> Optional[Ticket]:
    """Create one task from a draft dict. Returns ``None`` if an identical task already exists
    for the conversation (retry / double-submit protection)."""
    key = dedupe_key(call_id, draft) if (dedupe and call_id is not None) else None
    if key:
        existing = db.query(Ticket).filter(Ticket.call_id == call_id, Ticket.dedupe_key == key).first()
        if existing:
            return None

    standard_category = draft.get("category") or "General inquiries and information requests"
    text = f"{draft.get('title', '')} {draft.get('raw_quote', '')}"
    task_cat = task_category_for(standard_category, text)
    decision = route_task(db, standard_category=standard_category, task_category=task_cat,
                          urgency=draft["urgency"], text=text)
    department = decision.team
    reason = decision.reason
    # Built-in defaults mirror the rule engine; if the engine already chose a specific team and no
    # admin rule/emergency policy applies, keep its choice instead of overriding it.
    if decision.source == "default_rule" and draft.get("department") and draft["department"] != department:
        department = draft["department"]
        reason = f"Rule-engine department retained ({draft['department']}); {decision.reason}"

    policy = get_policy(db)
    sla_mins, deadline_dt = calculate_sla_and_deadline(
        draft["urgency"], draft.get("explicit_deadline"), sla_map=policy["sla_minutes"],
    )

    flags = list(draft.get("clinical_flags", []))
    escalation_reason = ""
    if decision.escalation_required:
        flags.append("emergency_escalation_required")
        escalation_reason = decision.escalation_instruction
    if decision.fallback:
        flags.append("fallback_queue")

    ticket = Ticket(
        call_id=call_id, patient_id=patient_id, department=department,
        category=standard_category, intent=draft.get("intent", "general_request"),
        title=draft["title"][:200], description=draft["description"],
        raw_quote=draft.get("raw_quote", ""), translated_quote=draft.get("translated_quote", ""),
        language=draft.get("language", "en"), urgency=draft["urgency"],
        priority_rationale=draft.get("priority_rationale", ""), required_action=draft.get("required_action", ""),
        explicit_deadline=draft.get("explicit_deadline"), confidence_score=draft.get("confidence_score", 1.0),
        source_timestamp=draft.get("source_timestamp"),
        requires_human_review=bool(draft.get("requires_human_review", False)),
        human_review_reason=draft.get("human_review_reason", ""),
        urgency_evidence=json.dumps(draft.get("urgency_evidence", {})),
        status=draft.get("status", "PENDING"), clinical_flags=json.dumps(flags),
        assigned_to=draft.get("assigned_to", "Unassigned"), assigned_team=department, assigned_staff="Unassigned",
        is_acknowledged=False, sla_minutes=sla_mins, deadline_at=deadline_dt, escalation_level=0,
        escalation_reason=escalation_reason,
        room_number=draft.get("room_number", "Unassigned"), patient_name=draft.get("patient_name", "Unknown Patient"),
        triage_notes=draft.get("triage_notes", ""), task_category=task_cat,
        routing_reason=reason, routing_rule_id=decision.rule_id, dedupe_key=key,
    )
    try:
        with db.begin_nested():   # SAVEPOINT: a duplicate must not roll back the whole intake
            db.add(ticket)
            db.flush()
    except IntegrityError:
        # Lost a race with an identical concurrent insert (unique call_id+dedupe_key index).
        return None

    now = datetime.now(timezone.utc)
    ticket.audit_logs.append(AuditLog(ticket_id=ticket.id, action="CREATED", note=source_note, actor=actor, created_at=now))
    ticket.audit_logs.append(AuditLog(ticket_id=ticket.id, action="ROUTED", note=reason, actor="Routing Service", created_at=now))
    if ticket.requires_human_review:
        ticket.audit_logs.append(AuditLog(
            ticket_id=ticket.id, action="FLAGGED_FOR_REVIEW", actor="AI Safety Guard", created_at=now,
            note=f"Flagged for human clinical review: {ticket.human_review_reason}",
        ))
    if decision.escalation_required:
        ticket.audit_logs.append(AuditLog(
            ticket_id=ticket.id, action="EMERGENCY_ESCALATION_FLAGGED", actor="Routing Service", created_at=now,
            note=decision.escalation_instruction,
        ))
    db.flush()
    return ticket
