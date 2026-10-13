"""Department routing and priority policy.

All routing logic lives here (never in the frontend):

1. Emergency priority bypasses ordinary queues.  Admin rules cannot divert an emergency task;
   it always goes to the configured emergency team with the hospital's escalation instruction.
2. Active admin-defined rules (``routing_rules`` table), lowest ``priority`` number first.
3. Built-in default rules (category -> team), which reproduce the departments the original
   rule engine already used so existing behaviour is unchanged until an admin edits rules.
4. A fallback queue (configurable) when nothing matches - never a silent guess.

Every decision records *why* it was made (``RoutingDecision.reason``) and is stored on the task.
"""
import json
from dataclasses import dataclass
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from audit import record_audit
from auth import require_permission
from database import get_db
from models_care import AppSetting, RoutingRule, User

EMERGENCY_TEAM_DEFAULT = "Rapid Response & Critical Nursing"
FALLBACK_TEAM_DEFAULT = "Triage Review Queue"
EMERGENCY_INSTRUCTION_DEFAULT = (
    "Follow the hospital's approved emergency escalation procedure immediately. "
    "Do not wait for this task to be picked up from the queue."
)

# Original 14 rule-engine categories -> the spec's task categories.
STANDARD_TO_TASK_CATEGORY: Dict[str, str] = {
    "Emergency and urgent clinical concerns": "clinical_review",
    "Nursing and patient care": "clinical_review",
    "Medication, pharmacy and prescription queries": "prescription_clarification",
    "Appointments and OPD coordination": "appointment_scheduling",
    "Appointment rescheduling and cancellation": "appointment_changes",
    "Specialist consultations and disease-related appointments": "appointment_scheduling",
    "Routine follow-up appointments": "appointment_scheduling",
    "Billing and payment queries": "billing_inquiry",
    "Insurance and pre-authorisation queries": "insurance_claims_inquiry",
    "Admission and discharge coordination": "discharge_coordination",
    "Facilities, housekeeping and transport": "general_patient_support",
    "Food, dietary and nutrition requests": "general_patient_support",
    "General inquiries and information requests": "general_patient_support",
    "Promised callbacks and other follow-up commitments": "follow_up_commitment",
}

# Built-in defaults: identical to the team each category was already assigned by the parser.
DEFAULT_TEAM_BY_STANDARD_CATEGORY: Dict[str, str] = {
    "Emergency and urgent clinical concerns": EMERGENCY_TEAM_DEFAULT,
    "Nursing and patient care": "Nursing & Clinical Care",
    "Medication, pharmacy and prescription queries": "Pharmacy & Therapeutics",
    "Appointments and OPD coordination": "Outpatient & Appointment Coordination",
    "Appointment rescheduling and cancellation": "Outpatient & Appointment Coordination",
    "Specialist consultations and disease-related appointments": "Specialist Clinic & OPD Services",
    "Routine follow-up appointments": "Outpatient & Appointment Coordination",
    "Billing and payment queries": "Patient Billing & Accounts",
    "Insurance and pre-authorisation queries": "Health Insurance & Pre-Authorisation",
    "Admission and discharge coordination": "Administration & Discharge Coordination",
    "Facilities, housekeeping and transport": "Facilities & Environmental Services",
    "Food, dietary and nutrition requests": "Dietary & Clinical Nutrition",
    "General inquiries and information requests": "Hospital Information & Patient Helpdesk",
    "Promised callbacks and other follow-up commitments": "Clinical Follow-up & Care Coordination",
}
# Used when a task arrives with only the new category (e.g. portal requests, LLM tasks).
DEFAULT_TEAM_BY_TASK_CATEGORY: Dict[str, str] = {
    "appointment_scheduling": "Outpatient & Appointment Coordination",
    "appointment_changes": "Outpatient & Appointment Coordination",
    "billing_inquiry": "Patient Billing & Accounts",
    "insurance_claims_inquiry": "Health Insurance & Pre-Authorisation",
    "prescription_clarification": "Pharmacy & Therapeutics",
    "clinical_review": "Nursing & Clinical Care",
    "discharge_coordination": "Administration & Discharge Coordination",
    "test_report_follow_up": "Clinical Follow-up & Care Coordination",
    "complaint": "Hospital Information & Patient Helpdesk",
    "follow_up_commitment": "Clinical Follow-up & Care Coordination",
    "general_patient_support": "Hospital Information & Patient Helpdesk",
}
# Standard category (rule-engine wording) for each new category, for tasks that don't have one.
TASK_TO_STANDARD_CATEGORY: Dict[str, str] = {
    "appointment_scheduling": "Appointments and OPD coordination",
    "appointment_changes": "Appointment rescheduling and cancellation",
    "billing_inquiry": "Billing and payment queries",
    "insurance_claims_inquiry": "Insurance and pre-authorisation queries",
    "prescription_clarification": "Medication, pharmacy and prescription queries",
    "clinical_review": "Nursing and patient care",
    "discharge_coordination": "Admission and discharge coordination",
    "test_report_follow_up": "Promised callbacks and other follow-up commitments",
    "complaint": "General inquiries and information requests",
    "follow_up_commitment": "Promised callbacks and other follow-up commitments",
    "general_patient_support": "General inquiries and information requests",
}

TASK_CATEGORIES = sorted(set(TASK_TO_STANDARD_CATEGORY))
URGENCY_LEVELS = ("STAT_EMERGENCY", "URGENT", "ROUTINE", "INQUIRY")
DEFAULT_SLA_MINUTES = {"STAT_EMERGENCY": 5, "URGENT": 20, "ROUTINE": 120, "INQUIRY": 240}
MAX_EMERGENCY_SLA_MINUTES = 15  # policy ceiling: an emergency SLA cannot be configured above this

COMPLAINT_WORDS = ("complaint", "complain", "unhappy", "not satisfied", "dissatisfied", "rude", "unacceptable")


def task_category_for(standard_category: Optional[str], text: str = "") -> str:
    low = (text or "").lower()
    if any(w in low for w in COMPLAINT_WORDS):
        return "complaint"
    return STANDARD_TO_TASK_CATEGORY.get(standard_category or "", "general_patient_support")


# ---------------------------------------------------------------------------
# Policy (admin-configurable)
# ---------------------------------------------------------------------------
def _get_json(db: Session, key: str, default):
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return default
    try:
        return json.loads(row.value)
    except ValueError:
        return default


def get_policy(db: Session) -> dict:
    stored = _get_json(db, "routing_policy", {})
    sla = dict(DEFAULT_SLA_MINUTES)
    sla.update({k: v for k, v in (stored.get("sla_minutes") or {}).items() if k in URGENCY_LEVELS})
    return {
        "sla_minutes": sla,
        "fallback_team": stored.get("fallback_team") or FALLBACK_TEAM_DEFAULT,
        "emergency_team": stored.get("emergency_team") or EMERGENCY_TEAM_DEFAULT,
        "emergency_instruction": stored.get("emergency_instruction") or EMERGENCY_INSTRUCTION_DEFAULT,
    }


@dataclass
class RoutingDecision:
    team: str
    reason: str
    source: str                     # emergency | admin_rule | default_rule | fallback
    rule_id: Optional[int] = None
    fallback: bool = False
    escalation_required: bool = False
    escalation_instruction: str = ""


def route_task(
    db: Session, *, standard_category: Optional[str], task_category: Optional[str],
    urgency: str, text: str = "",
) -> RoutingDecision:
    policy = get_policy(db)

    if urgency == "STAT_EMERGENCY":
        return RoutingDecision(
            team=policy["emergency_team"], source="emergency", escalation_required=True,
            escalation_instruction=policy["emergency_instruction"],
            reason=f"Emergency priority: sent directly to '{policy['emergency_team']}' and flagged for the hospital's "
                   "emergency escalation process (ordinary routing rules do not apply).",
        )

    low = (text or "").lower()
    rules: List[RoutingRule] = (
        db.query(RoutingRule).filter(RoutingRule.is_active.is_(True))
        .order_by(RoutingRule.priority.asc(), RoutingRule.id.asc()).all()
    )
    for rule in rules:
        if rule.match_category and rule.match_category not in (standard_category, task_category):
            continue
        if rule.match_urgency and rule.match_urgency != urgency:
            continue
        if rule.match_keyword and rule.match_keyword.lower() not in low:
            continue
        return RoutingDecision(
            team=rule.target_team, source="admin_rule", rule_id=rule.id,
            reason=f"Matched routing rule #{rule.id} '{rule.name}' (priority {rule.priority}).",
        )

    if standard_category in DEFAULT_TEAM_BY_STANDARD_CATEGORY:
        return RoutingDecision(
            team=DEFAULT_TEAM_BY_STANDARD_CATEGORY[standard_category], source="default_rule",
            reason=f"Default rule: category '{standard_category}'.",
        )
    if task_category in DEFAULT_TEAM_BY_TASK_CATEGORY:
        return RoutingDecision(
            team=DEFAULT_TEAM_BY_TASK_CATEGORY[task_category], source="default_rule",
            reason=f"Default rule: task category '{task_category}'.",
        )
    return RoutingDecision(
        team=policy["fallback_team"], source="fallback", fallback=True,
        reason="No routing rule matched; placed in the fallback queue for manual assignment.",
    )


def sla_minutes_for(db: Session, urgency: str, explicit_cap: Optional[int] = None) -> int:
    minutes = get_policy(db)["sla_minutes"].get(urgency, DEFAULT_SLA_MINUTES.get(urgency, 120))
    return min(minutes, explicit_cap) if explicit_cap else minutes


# ---------------------------------------------------------------------------
# Admin API
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/routing", tags=["routing"])


class RuleIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    priority: int = Field(100, ge=1, le=10000)
    match_category: Optional[str] = Field(None, max_length=60)
    match_urgency: Optional[str] = None
    match_keyword: Optional[str] = Field(None, max_length=80)
    target_team: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True

    @field_validator("match_urgency")
    @classmethod
    def _urgency(cls, v):
        if v is not None and v not in URGENCY_LEVELS:
            raise ValueError(f"match_urgency must be one of {URGENCY_LEVELS}")
        if v == "STAT_EMERGENCY":
            raise ValueError("Emergency routing is fixed by policy and cannot be targeted by rules")
        return v


class RuleOut(RuleIn):
    id: int


class PolicyIn(BaseModel):
    sla_minutes: Optional[Dict[str, int]] = None
    fallback_team: Optional[str] = Field(None, min_length=1, max_length=100)
    emergency_team: Optional[str] = Field(None, min_length=1, max_length=100)
    emergency_instruction: Optional[str] = Field(None, min_length=1, max_length=500)

    @field_validator("sla_minutes")
    @classmethod
    def _sla(cls, v):
        if v is None:
            return v
        for level, minutes in v.items():
            if level not in URGENCY_LEVELS:
                raise ValueError(f"Unknown urgency level '{level}'")
            if not 1 <= minutes <= 10080:
                raise ValueError("SLA minutes must be between 1 and 10080")
        if v.get("STAT_EMERGENCY", 0) > MAX_EMERGENCY_SLA_MINUTES:
            raise ValueError(f"Emergency SLA cannot exceed {MAX_EMERGENCY_SLA_MINUTES} minutes")
        return v


def _rule_out(r: RoutingRule) -> RuleOut:
    return RuleOut(id=r.id, name=r.name, priority=r.priority, match_category=r.match_category,
                   match_urgency=r.match_urgency, match_keyword=r.match_keyword,
                   target_team=r.target_team, is_active=r.is_active)


@router.get("/rules", response_model=List[RuleOut])
def list_rules(user: User = Depends(require_permission("task:read")), db: Session = Depends(get_db)):
    return [_rule_out(r) for r in db.query(RoutingRule).order_by(RoutingRule.priority, RoutingRule.id).all()]


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(payload: RuleIn, user: User = Depends(require_permission("routing:admin")), db: Session = Depends(get_db)):
    rule = RoutingRule(**payload.model_dump(), updated_by_user_id=user.id)
    db.add(rule)
    db.flush()
    record_audit(db, user=user, action="routing_rule_created", resource_type="routing_rule", resource_id=rule.id)
    db.commit()
    return _rule_out(rule)


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, payload: RuleIn, user: User = Depends(require_permission("routing:admin")),
                db: Session = Depends(get_db)):
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    changed = [k for k, v in payload.model_dump().items() if getattr(rule, k) != v]
    for key, value in payload.model_dump().items():
        setattr(rule, key, value)
    rule.updated_by_user_id = user.id
    record_audit(db, user=user, action="routing_rule_updated", resource_type="routing_rule",
                 resource_id=rule.id, detail={"changed_fields": changed})
    db.commit()
    return _rule_out(rule)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, user: User = Depends(require_permission("routing:admin")), db: Session = Depends(get_db)):
    rule = db.query(RoutingRule).filter(RoutingRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Routing rule not found")
    db.delete(rule)
    record_audit(db, user=user, action="routing_rule_deleted", resource_type="routing_rule", resource_id=rule_id)
    db.commit()
    return {"message": "Routing rule deleted"}


@router.get("/policy")
def read_policy(user: User = Depends(require_permission("task:read")), db: Session = Depends(get_db)):
    policy = get_policy(db)
    policy["task_categories"] = TASK_CATEGORIES
    policy["default_teams"] = DEFAULT_TEAM_BY_STANDARD_CATEGORY
    return policy


@router.put("/policy")
def update_policy(payload: PolicyIn, user: User = Depends(require_permission("routing:admin")),
                  db: Session = Depends(get_db)):
    current = _get_json(db, "routing_policy", {})
    data = payload.model_dump(exclude_none=True)
    if "sla_minutes" in data:
        current["sla_minutes"] = {**(current.get("sla_minutes") or {}), **data.pop("sla_minutes")}
    current.update(data)
    row = db.query(AppSetting).filter(AppSetting.key == "routing_policy").first()
    if row:
        row.value = json.dumps(current)
        row.updated_by_user_id = user.id
    else:
        db.add(AppSetting(key="routing_policy", value=json.dumps(current), updated_by_user_id=user.id))
    record_audit(db, user=user, action="routing_policy_updated", resource_type="app_setting",
                 resource_id="routing_policy", detail={"changed_fields": sorted(payload.model_dump(exclude_none=True))})
    db.commit()
    return get_policy(db)
