"""Deterministic, offline extractor (default provider).

Reuses the project's multilingual rule engine for tasks, urgency and negation, and adds
extraction of the structured fields the schema requires.  It only reports what the text
states: anything it cannot ground becomes ``None`` plus an uncertainty note.

Known limits (surfaced to reviewers, not hidden):
  * Symptom / diagnosis / relationship lexicons are English; for Hindi/Kannada the engine's
    emergency vocabulary and task segmentation still apply, but other fields fall back to
    human review.  Use the LLM provider (when authorised) or manual entry for richer coverage.
"""
import re
from datetime import date, timedelta
from typing import List, Optional, Tuple

from extraction.schema import (
    Assertion, AppointmentIntentType, ExtractedTask, Priority, PRIORITY_RANK, TaskCategory,
)
from nlp_parser import (
    process_real_transcript, evaluate_clinical_urgency_and_evidence, extract_explicit_deadline,
    detect_script_language,
)
from routing import task_category_for

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")

_NAME_STOPWORDS = {
    "reports", "report", "reported", "needs", "need", "is", "was", "has", "had", "with", "in", "on", "at", "who",
    "requests", "requested", "asking", "asks", "called", "calling", "wants", "want", "complains", "complaining",
    "presented", "presents", "came", "feels", "feeling", "says", "said", "will", "would", "may", "might", "also",
    "not", "no", "and", "the", "a", "an", "age", "aged", "of", "for", "to", "from", "here", "there", "again",
    "name", "named", "id", "number", "room", "bed", "ward", "mrn", "uhid", "refill", "follow", "if", "having",
}
_NAME_TOKEN = r"[A-Za-z][A-Za-z'\-]{1,24}"

RELATIONSHIPS = {
    "father": "father", "dad": "father", "mother": "mother", "mom": "mother", "mum": "mother",
    "wife": "wife", "husband": "husband", "son": "son", "daughter": "daughter", "brother": "brother",
    "sister": "sister", "grandfather": "grandfather", "grandmother": "grandmother", "uncle": "uncle",
    "aunt": "aunt", "relative": "relative", "friend": "friend", "neighbour": "neighbour",
    "neighbor": "neighbour", "guardian": "guardian", "caretaker": "caretaker", "daughter-in-law": "daughter-in-law",
}

SYMPTOM_TERMS = [
    "chest pain", "abdominal pain", "stomach pain", "back pain", "joint pain", "leg pain", "arm pain",
    "headache", "pain", "fever", "cough", "cold", "vomiting", "nausea", "diarrhoea", "diarrhea", "dizziness",
    "swelling", "bleeding", "rash", "itching", "shortness of breath", "breathlessness", "difficulty breathing",
    "weakness", "fatigue", "numbness", "tingling", "burning sensation", "loss of appetite", "constipation",
    "sore throat", "blurred vision", "palpitations", "fainting", "seizure", "bruising", "discharge",
    "wound", "injury", "fall",
]
DIAGNOSIS_TERMS = [
    "fracture", "broken bone", "pneumonia", "diabetes", "hypertension", "infection", "appendicitis",
    "stroke", "heart attack", "asthma", "tuberculosis", "dengue", "malaria", "typhoid", "covid", "cancer",
    "kidney stone", "anaemia", "anemia", "jaundice", "sprain", "dislocation", "ulcer",
]
NEGATION_RE = re.compile(r"\b(no|not|without|denies|denied|never|negative for|free of|ruled out|nil)\b", re.I)
HEDGE_RE = re.compile(
    r"\b(possible|possibly|may have|might have|might be|may be|suspected|suspect|suspicion|probable|probably|"
    r"could be|seems? to have|appears? to have|unsure|not sure|query|\?)", re.I
)
STAFF_COMMIT_RE = re.compile(
    r"\b(?:i|we|doctor|dr\.?\s*\w+|nurse|the team|staff)(?:\s+will|'ll)\s+([^.;\n]{3,120})", re.I
)
CALLBACK_RE = re.compile(
    r"(?:call(?:\s+(?:me|us|them|back))?\s*back|callback|call\s+(?:me|him|her|them)\s+(?:on|by|at|tomorrow|today)|"
    r"get back to (?:me|us|him|her|them)|ring (?:me|back))([^.;\n]{0,80})", re.I
)
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], start=1)}
_WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------
def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s and s.strip()]


def _sentence_with(text: str, span_start: int) -> str:
    cursor = 0
    for sent in _sentences(text):
        idx = text.find(sent, cursor)
        if idx == -1:
            continue
        cursor = idx + len(sent)
        if idx <= span_start < cursor:
            return sent
    return text[:300]


def extract_age(text: str) -> Optional[int]:
    patterns = [
        r"\bage[d]?\s*(?:is|of|:)?\s*(\d{1,3})\b",
        r"\b(\d{1,3})[\s-]*(?:years?|yrs?)[\s-]*old\b",
        r"\b(\d{1,3})\s*(?:years?|yrs?)\b(?:\s+(?:male|female|man|woman|boy|girl|patient))",
        r"(?:उम्र|आयु)\s*(\d{1,3})",
        r"(\d{1,3})\s*(?:साल|वर्ष)",
        r"ವಯಸ್ಸು\s*(\d{1,3})",
        r"(\d{1,3})\s*ವರ್ಷ",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            age = int(m.group(1))
            if 0 <= age <= 120:
                return age
    return None


def extract_dob(text: str) -> Optional[date]:
    m = re.search(r"(?:date of birth|dob|born on|born)\s*(?:is|:)?\s*(\d{4})-(\d{1,2})-(\d{1,2})", text, re.I)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(?:date of birth|dob|born on|born)\s*(?:is|:)?\s*(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text, re.I)
    if m:  # day-first, the convention for Indian records
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = re.search(r"(?:date of birth|dob|born on|born)\s*(?:is|:)?\s*(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)\s+(\d{4})", text, re.I)
    if m and m.group(2).lower() in _MONTHS:
        return _safe_date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)))
    return None


def _safe_date(y: int, mo: int, d: int) -> Optional[date]:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def extract_patient_identifier(text: str) -> Optional[str]:
    m = re.search(r"\b(?:mrn|uhid|patient\s*(?:id|number|no\.?)|hospital\s*(?:id|number))\s*(?:is|:|number)?\s*([A-Z0-9][A-Z0-9\-/]{3,24})\b", text, re.I)
    if m and re.search(r"\d", m.group(1)):
        return m.group(1)
    return None


def extract_patient_name(text: str) -> Optional[str]:
    patterns = [
        rf"\b(?:mr|mrs|ms|miss|shri|smt|master)\.?\s+({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})",
        rf"\bpatient\s+name\s*(?:is|:)?\s*({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})",
        rf"\bpatient\s+(?:called\s+|named\s+)?({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})",
        rf"\b(?:calling|call(?:ing)?\s+about|regarding|concerning)\s+(?:my\s+\w+\s+)?({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})",
        rf"\bmy\s+(?:father|mother|wife|husband|son|daughter|brother|sister)[,\s]+({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,2}})",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            tokens: List[str] = []
            for tok in m.group(1).split():
                if tok.lower().strip(",.") in _NAME_STOPWORDS:
                    break
                tokens.append(tok.strip(",."))
            if tokens and all(len(t) >= 2 for t in tokens):
                return " ".join(t[:1].upper() + t[1:] for t in tokens)
    return None


def extract_caller_relationship(text: str) -> Optional[str]:
    m = re.search(
        r"\b(?:my|his|her|their)\s+(" + "|".join(sorted(RELATIONSHIPS, key=len, reverse=True)) + r")\b", text, re.I
    )
    if m:
        return RELATIONSHIPS[m.group(1).lower()]
    m = re.search(r"\bi\s*(?:am|'m)\s+(?:the\s+|his\s+|her\s+)?(" + "|".join(RELATIONSHIPS) + r")\b", text, re.I)
    if m:
        return RELATIONSHIPS[m.group(1).lower()]
    if re.search(r"\b(?:i am the patient|this is the patient|calling for myself|for myself)\b", text, re.I):
        return "self"
    return None


def _assertion_for(sentence: str, term_start: int) -> Assertion:
    before = sentence[:term_start]
    window = " ".join(before.split()[-5:])
    if NEGATION_RE.search(window):
        return Assertion.negated
    if HEDGE_RE.search(sentence):
        return Assertion.possible
    return Assertion.reported


def extract_symptoms(text: str) -> List[Tuple[str, Assertion, str]]:
    found: List[Tuple[str, Assertion, str]] = []
    seen = set()
    for sent in _sentences(text):
        low = sent.lower()
        consumed: List[Tuple[int, int]] = []
        for term in sorted(SYMPTOM_TERMS, key=len, reverse=True):
            for m in re.finditer(rf"\b{re.escape(term)}\b", low):
                if any(s <= m.start() < e for s, e in consumed):
                    continue  # "pain" inside an already-matched "chest pain"
                consumed.append((m.start(), m.end()))
                key = (term, sent)
                if key not in seen:
                    seen.add(key)
                    found.append((term, _assertion_for(low, m.start()), sent))
    return found


def extract_diagnosis_mentions(text: str) -> List[Tuple[str, Assertion, str]]:
    found: List[Tuple[str, Assertion, str]] = []
    for sent in _sentences(text):
        low = sent.lower()
        for term in DIAGNOSIS_TERMS:
            m = re.search(rf"\b{re.escape(term)}\b", low)
            if m:
                assertion = _assertion_for(low, m.start())
                # A bare mention is never upgraded to "confirmed": the best it gets is "reported as stated".
                found.append((term, assertion, sent))
    return found


def extract_medication_mentions(text: str) -> List[Tuple[str, str]]:
    out = []
    for m in re.finditer(r"\b([A-Za-z][A-Za-z\-]{3,30})\s+(\d+(?:\.\d+)?\s?(?:mg|mcg|g|ml|iu|units?))\b", text, re.I):
        word = m.group(1)
        if word.lower() in {"about", "around", "nearly", "almost", "every", "after", "since", "only", "with"}:
            continue
        out.append((m.group(0), _sentence_with(text, m.start())))
    return out


def resolve_relative_date(text: str, reference: date) -> Optional[date]:
    low = text.lower()
    if re.search(r"\bday after tomorrow\b", low):
        return reference + timedelta(days=2)
    if re.search(r"\btomorrow\b", low):
        return reference + timedelta(days=1)
    if re.search(r"\btoday\b", low):
        return reference
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", low)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"\b(?:on\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+(" + "|".join(_MONTHS) + r")\b", low)
    if m:
        d, mo = int(m.group(1)), _MONTHS[m.group(2)]
        candidate = _safe_date(reference.year, mo, d)
        if candidate and candidate < reference:
            candidate = _safe_date(reference.year + 1, mo, d)
        return candidate
    m = re.search(r"\b(?:next|on|this)?\s*(" + "|".join(_WEEKDAYS) + r")\b", low)
    if m:
        delta = (_WEEKDAYS[m.group(1)] - reference.weekday()) % 7
        return reference + timedelta(days=delta or 7)
    return None


def extract_callback(text: str, reference: date) -> Tuple[Optional[str], Optional[date], Optional[str]]:
    m = CALLBACK_RE.search(text)
    if not m:
        return None, None, None
    raw = (m.group(0) or "").strip()
    sentence = _sentence_with(text, m.start())
    return raw[:200], resolve_relative_date(sentence, reference), sentence


def extract_appointment_intent(text: str) -> Tuple[AppointmentIntentType, Optional[str], Optional[str]]:
    for sent in _sentences(text):
        low = sent.lower()
        if re.search(r"\b(cancel)\b.*\bappointment\b|\bappointment\b.*\bcancel", low):
            return AppointmentIntentType.cancel, None, sent
        if re.search(r"\b(reschedule|postpone|change|move|shift)\b.*\b(appointment|consultation|visit|slot)\b", low):
            return AppointmentIntentType.reschedule, None, sent
        if re.search(r"\bfollow[\s-]?up\b.*\b(appointment|visit|consultation|review)\b|\bfollow[\s-]?up visit\b", low):
            return AppointmentIntentType.follow_up, None, sent
        if re.search(r"\b(book|schedule|arrange|need|want|fix|get|request)\b.*\b(appointment|consultation|opd|slot)\b|"
                     r"\bappointment\b.*\b(please|needed|required)\b", low):
            return AppointmentIntentType.book, None, sent
    return AppointmentIntentType.none, None, None


def extract_commitments(text: str) -> List[Tuple[str, Optional[str], str]]:
    out = []
    for m in STAFF_COMMIT_RE.finditer(text):
        action = m.group(1).strip(" ,.")
        sentence = _sentence_with(text, m.start())
        out.append((action, extract_explicit_deadline(sentence), sentence))
    return out


# ---------------------------------------------------------------------------
# Priority mapping
# ---------------------------------------------------------------------------
_URGENCY_TO_PRIORITY = {
    "STAT_EMERGENCY": Priority.emergency, "URGENT": Priority.urgent,
    "ROUTINE": Priority.routine, "INQUIRY": Priority.inquiry,
}


def priority_from_urgency(urgency: str) -> Priority:
    return _URGENCY_TO_PRIORITY.get(urgency, Priority.requires_review)


def most_severe(priorities: List[Priority]) -> Priority:
    if not priorities:
        return Priority.requires_review
    return min(priorities, key=lambda p: PRIORITY_RANK[p.value])


def _task_category_enum(standard_category: str, text: str) -> TaskCategory:
    return TaskCategory(task_category_for(standard_category, text))


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
class RuleBasedExtractor:
    name = "rules"

    def extract(self, transcript: str, language: Optional[str], reference_date: date,
                caller_name: Optional[str] = None, patient_name: Optional[str] = None,
                room_number: Optional[str] = None) -> Tuple[dict, dict]:
        """Return (raw_extraction_dict, legacy_engine_result).

        ``legacy_engine_result`` is the original rule-engine output, used to create tickets so
        the established urgency/negation behaviour is preserved.
        """
        lang = language or detect_script_language(transcript)
        legacy = process_real_transcript(
            transcript=transcript, language=lang, caller_name=caller_name,
            patient_name=patient_name, room_number=room_number,
        )

        name = extract_patient_name(transcript)
        age = extract_age(transcript)
        dob = extract_dob(transcript)
        pid = extract_patient_identifier(transcript)
        relationship = extract_caller_relationship(transcript)

        symptoms = [{"text": t, "assertion": a.value, "evidence": s[:500]} for t, a, s in extract_symptoms(transcript)]
        diagnoses = [{"text": t, "assertion": a.value, "evidence": s[:500]} for t, a, s in extract_diagnosis_mentions(transcript)]
        meds = [{"text": t, "evidence": s[:500]} for t, s in extract_medication_mentions(transcript)]
        commitments = [{"commitment": c, "due_text": d, "evidence": s[:500]} for c, d, s in extract_commitments(transcript)]
        cb_raw, cb_date, cb_sentence = extract_callback(transcript, reference_date)
        appt_intent, _, appt_sentence = extract_appointment_intent(transcript)

        uncertainty: List[str] = []
        if lang != "en":
            uncertainty.append(
                f"Rule-based extraction has limited coverage for '{lang}'; fields beyond tasks and emergency "
                "terms may be missing. Review manually."
            )
        if cb_raw and cb_date is None:
            uncertainty.append("A callback was requested but its date could not be determined exactly.")

        tasks: List[dict] = []
        priorities: List[Priority] = []
        for t in legacy["tickets"]:
            prio = priority_from_urgency(t["urgency"])
            priorities.append(prio)
            tasks.append(ExtractedTask(
                title=t["title"][:200],
                category=_task_category_enum(t.get("category", ""), t.get("raw_quote", "")),
                description=(t.get("description") or "")[:2000],
                requested_action=(t.get("required_action") or None),
                priority=prio, priority_reason=(t.get("priority_rationale") or "")[:500],
                evidence=(t.get("raw_quote") or None), due_text=t.get("explicit_deadline"),
                requires_review=bool(t.get("requires_human_review")),
                review_reason=(t.get("human_review_reason") or "")[:300],
                legacy={"standard_category": t.get("category"), "urgency": t["urgency"]},
            ).model_dump(mode="json"))

        # Clinical content that did not rise to urgent must not be silently filed as routine.
        has_clinical_concern = bool(symptoms or diagnoses) and any(
            s["assertion"] != "negated" for s in symptoms + diagnoses
        )
        overall = most_severe(priorities)
        review_reasons: List[str] = []
        if has_clinical_concern and overall != Priority.emergency:
            # The queue urgency of each task is kept, but the overall recommendation says a
            # qualified person must triage - it is never presented as a settled priority.
            overall = Priority.requires_review
            review_reasons.append("Clinical concern reported - needs qualified clinical review")

        concern = None
        for s in symptoms + diagnoses:
            if s["assertion"] != "negated":
                concern = s["evidence"]
                break
        requested_action = next((t["requested_action"] for t in tasks if t.get("requested_action")), None)

        evidence = []
        for key, ev in (("patient.name", name), ("patient.age", age), ("reported_concern", concern),
                        ("callback", cb_sentence), ("appointment_intent", appt_sentence)):
            if ev:
                src = ev if isinstance(ev, str) else None
                if src:
                    evidence.append({"field": key, "excerpt": src[:500]})

        raw = {
            "patient": {
                "name": name, "patient_id": pid, "age": age,
                "date_of_birth": dob.isoformat() if dob else None, "caller_relationship": relationship,
            },
            "reported_concern": concern,
            "symptoms": symptoms, "diagnosis_mentions": diagnoses, "medication_mentions": meds,
            "requested_action": requested_action,
            "staff_commitments": commitments,
            "callback": {"raw_text": cb_raw, "requested_date": cb_date.isoformat() if cb_date else None,
                         "evidence": cb_sentence},
            "appointment_intent": {"intent": appt_intent.value, "evidence": appt_sentence},
            "tasks": tasks, "priority": overall.value, "uncertainty": uncertainty, "evidence": evidence,
            "confidence": None,   # rule engine has no calibrated confidence; none is invented
            "review_required": bool(review_reasons) or any(t["requires_review"] for t in tasks),
            "review_reasons": review_reasons,
        }
        return raw, legacy
