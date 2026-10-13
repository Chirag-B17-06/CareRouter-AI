"""Extraction orchestration: provider choice, validation, safety floor, ticket drafts.

``extract_structured`` never raises for provider problems - it falls back to the offline rule
engine and records the reason - because a failed AI service must not drop a patient request.
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from config import get_settings
from extraction.llm import LLMExtractor, LLMUnavailable, llm_ready
from extraction.rules import RuleBasedExtractor, priority_from_urgency
from extraction.schema import (
    Priority, PRIORITY_RANK, StructuredExtraction, validate_extraction,
)
from nlp_parser import evaluate_clinical_urgency_and_evidence, detect_script_language
from routing import TASK_TO_STANDARD_CATEGORY

logger = logging.getLogger("carerouter.extraction")

_PRIORITY_TO_URGENCY = {
    Priority.emergency: "STAT_EMERGENCY", Priority.urgent: "URGENT",
    Priority.routine: "ROUTINE", Priority.inquiry: "INQUIRY", Priority.requires_review: "URGENT",
}

# Overridable in tests.
llm_extractor = LLMExtractor()
rule_extractor = RuleBasedExtractor()


@dataclass
class ExtractionOutcome:
    extraction: StructuredExtraction
    provider: str
    ticket_drafts: List[Dict[str, Any]]
    legacy: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)


def _drafts_from_llm_tasks(ex: StructuredExtraction, transcript: str, language: str,
                           patient_name: str, room_number: str) -> List[Dict[str, Any]]:
    drafts = []
    for t in ex.tasks:
        urgency = _PRIORITY_TO_URGENCY[t.priority]
        quote = t.evidence or transcript[:200]
        review = t.requires_review or t.priority == Priority.requires_review
        drafts.append({
            "department": "", "category": TASK_TO_STANDARD_CATEGORY[t.category.value],
            "intent": t.category.value, "title": t.title, "description": t.description or t.title,
            "raw_quote": quote, "translated_quote": quote, "language": language, "urgency": urgency,
            "priority_rationale": t.priority_reason or f"Priority '{t.priority.value}' recommended by extraction.",
            "required_action": t.requested_action or "", "explicit_deadline": t.due_text,
            "confidence_score": ex.confidence if ex.confidence is not None else 0.0,
            "source_timestamp": None, "requires_human_review": review,
            "human_review_reason": t.review_reason or ("Priority needs clinical review" if review else ""),
            "urgency_evidence": {"provider": "llm", "evidence": t.evidence},
            "clinical_flags": ["ai_extracted"] + (["manual_review_required"] if review else []),
            "assigned_to": "Unassigned", "room_number": room_number, "patient_name": patient_name,
            "triage_notes": "",
        })
    return drafts


def _apply_emergency_floor(ex: StructuredExtraction, transcript: str, language: str,
                           drafts: List[Dict[str, Any]], legacy: Dict[str, Any]) -> None:
    """The rule engine's emergency detection can raise priority but never be lowered by the model."""
    assessment = evaluate_clinical_urgency_and_evidence(transcript, language)
    if not assessment["is_emergency"]:
        return
    if not any(d["urgency"] == "STAT_EMERGENCY" for d in drafts):
        drafts.extend(t for t in legacy["tickets"] if t["urgency"] == "STAT_EMERGENCY")
        ex.uncertainty.append("Emergency terms were detected by the safety rules; an emergency task was added.")
    if PRIORITY_RANK[ex.priority.value] > PRIORITY_RANK["emergency"]:
        ex.priority = Priority.emergency
    ex.review_required = True
    if "Possible emergency detected by safety rules" not in ex.review_reasons:
        ex.review_reasons.append("Possible emergency detected by safety rules")


def extract_structured(
    transcript: str, language: Optional[str], reference_date: date,
    caller_name: Optional[str] = None, patient_name: Optional[str] = None, room_number: Optional[str] = None,
) -> ExtractionOutcome:
    settings = get_settings()
    lang = language or detect_script_language(transcript)
    warnings: List[str] = []

    # The rule engine always runs: it supplies the emergency safety floor and is the fallback.
    raw_rules, legacy = rule_extractor.extract(
        transcript, lang, reference_date, caller_name=caller_name, patient_name=patient_name, room_number=room_number,
    )
    p_name = legacy["patient_name"]
    r_num = legacy["room_number"]

    if settings.extraction_provider == "llm":
        reason = llm_ready()
        if reason:
            warnings.append(f"LLM extraction unavailable ({reason}); used the offline rule engine.")
        else:
            try:
                raw_llm = llm_extractor.extract_raw(transcript, lang)
                ex = validate_extraction(raw_llm, transcript)
                drafts = _drafts_from_llm_tasks(ex, transcript, lang, p_name, r_num)
                if not drafts:
                    raise ValueError("model returned no tasks")
                _apply_emergency_floor(ex, transcript, lang, drafts, legacy)
                return ExtractionOutcome(ex, "llm", drafts, legacy, warnings)
            except LLMUnavailable as exc:
                warnings.append(f"LLM extraction failed ({exc}); used the offline rule engine.")
            except (ValidationError, ValueError) as exc:
                logger.warning("LLM output rejected: %s", type(exc).__name__)
                warnings.append("LLM output failed schema validation and was discarded; used the offline rule engine.")

    ex = validate_extraction(raw_rules, transcript)
    for w in warnings:
        ex.uncertainty.append(w)
    if warnings:
        ex.review_required = True
        ex.review_reasons.append("AI extraction was unavailable or rejected; rule-based result needs review")
    return ExtractionOutcome(ex, "rules", list(legacy["tickets"]), legacy, warnings)
