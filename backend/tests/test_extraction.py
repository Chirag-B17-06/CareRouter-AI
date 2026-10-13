"""Transcript -> structured information: schema validation, grounding, safety rules, AI fallback.

All transcripts are fictional.  The LLM path is exercised with a mocked HTTP transport - no
network and no real model - so these tests prove the *handling* of model output (validation,
grounding, fallback, emergency floor), not the quality of any model.
"""
import json
from datetime import date

import httpx
import pytest
from pydantic import ValidationError

from extraction import service as ex_service
from extraction.llm import LLMExtractor
from extraction.schema import StructuredExtraction, validate_extraction
from extraction.service import extract_structured
from models_care import Medication

REF = date(2026, 10, 13)


def run(text, lang="en"):
    return extract_structured(text, lang, REF)


# ------------------------------------------------------------------ the example from the specification
def test_spec_example_produces_the_expected_structure():
    out = run("Patient Akshay, age 42. Reports a possible right forearm fracture. Needs clinical assessment.")
    ex = out.extraction
    assert ex.patient.name == "Akshay" and ex.patient.age == 42 and ex.patient.patient_id is None
    assert ex.verified_diagnosis is None
    assert ex.reported_concern and "possible right forearm fracture" in ex.reported_concern.lower()
    assert ex.diagnosis_mentions and ex.diagnosis_mentions[0].text == "fracture"
    assert ex.diagnosis_mentions[0].assertion.value == "possible"
    assert ex.priority.value == "requires_review" and ex.review_required is True
    assert any("unverified" in r.lower() for r in ex.review_reasons)
    assert ex.confidence is None                      # rule engine never invents a confidence value


def test_other_names_and_ages_are_not_hardcoded():
    ex = run("Patient Meera Nair, aged 67, has fever since two days. Needs a doctor to review.").extraction
    assert ex.patient.name == "Meera Nair" and ex.patient.age == 67
    ex2 = run("The patient is 8 years old and his father is calling about him.").extraction
    assert ex2.patient.age == 8 and ex2.patient.caller_relationship == "father"


# ------------------------------------------------------------------ never invent
def test_missing_details_are_null_not_guessed():
    ex = run("Please send someone to room 12, the patient needs help.").extraction
    assert ex.patient.name is None and ex.patient.age is None and ex.patient.patient_id is None
    assert ex.patient.date_of_birth is None
    assert ex.callback.requested_date is None and ex.medication_mentions == []


def test_age_is_not_taken_from_unrelated_numbers():
    ex = run("Room 42 needs a blanket. Call extension 4242 when done.").extraction
    assert ex.patient.age is None


def test_dob_and_identifier_only_when_stated():
    ex = run("Patient Ravi, date of birth 14/03/1980, MRN AB-10293. Wants a billing statement.").extraction
    assert ex.patient.date_of_birth == date(1980, 3, 14) and ex.patient.patient_id == "AB-10293"
    assert run("Patient Ravi wants a billing statement.").extraction.patient.patient_id is None


def test_negation_is_preserved():
    ex = run("Patient Sunil has no chest pain but reports a headache.").extraction
    by_text = {s.text: s.assertion.value for s in ex.symptoms}
    assert by_text["chest pain"] == "negated" and by_text["headache"] == "reported"
    assert run("Patient Sunil has no chest pain.").extraction.priority.value != "emergency"


def test_symptoms_are_not_converted_into_diagnoses():
    ex = run("Patient Leela reports cough and fever.").extraction
    assert {s.text for s in ex.symptoms} >= {"cough", "fever"}
    assert ex.diagnosis_mentions == [] and ex.verified_diagnosis is None


def test_hedged_diagnosis_is_never_confirmed():
    for phrase in ("may have pneumonia", "suspected appendicitis", "possible fracture"):
        ex = run(f"Patient Dev, age 30, {phrase}.").extraction
        assert ex.verified_diagnosis is None
        assert ex.diagnosis_mentions and ex.diagnosis_mentions[0].assertion.value == "possible"
        assert ex.review_required


def test_medications_are_only_echoed_flagged_and_never_prescribed():
    ex = run("Patient Gita asks if Paracetamol 500 mg is still fine to take.").extraction
    assert [m.text for m in ex.medication_mentions] == ["Paracetamol 500 mg"]
    assert ex.review_required and any("verify" in r.lower() for r in ex.review_reasons)
    assert run("Patient Gita feels unwell.").extraction.medication_mentions == []


def test_ambiguous_transcript_is_flagged_for_review():
    out = run("Not sure if it is heart attack or gas, patient Kiran has some discomfort.")
    assert out.extraction.review_required is True
    assert any(t.requires_review for t in out.extraction.tasks)


def test_multiple_independent_tasks_from_one_conversation():
    out = run("Patient Anil in room 8 needs the doctor to review his dressing. Please send the billing statement. "
              "Also reschedule his appointment for next week.")
    cats = {t.category.value for t in out.extraction.tasks}
    assert len(out.extraction.tasks) >= 3
    assert {"billing_inquiry", "appointment_changes"} <= cats
    assert len(out.ticket_drafts) == len(out.extraction.tasks)


def test_callback_and_appointment_intent_and_commitments():
    ex = run("Patient Rohan wants to book an appointment with cardiology. Please call back tomorrow. "
             "I will arrange the report today.").extraction
    assert ex.appointment_intent.intent.value == "book"
    assert ex.callback.requested_date == date(2026, 10, 14) and "call back tomorrow" in ex.callback.raw_text
    assert ex.staff_commitments and "arrange the report" in ex.staff_commitments[0].commitment
    assert run("Please call back sometime soon.").extraction.callback.requested_date is None


# ------------------------------------------------------------------ schema & grounding gate
def test_schema_rejects_unknown_fields_and_bad_enums():
    with pytest.raises(ValidationError):
        StructuredExtraction.model_validate({"surprise": 1})
    with pytest.raises(ValidationError):
        StructuredExtraction.model_validate({"priority": "whenever"})
    with pytest.raises(ValidationError):
        StructuredExtraction.model_validate({"tasks": [{"title": "x", "category": "made_up"}]})
    with pytest.raises(ValidationError):
        StructuredExtraction.model_validate({"patient": {"age": 400}})


def test_verified_diagnosis_is_always_stripped():
    ex = validate_extraction({"verified_diagnosis": "Fracture of radius"}, "Patient has pain.")
    assert ex.verified_diagnosis is None


def test_ungrounded_values_are_removed_and_flagged():
    raw = {
        "patient": {"name": "Imaginary Person", "age": 77, "patient_id": "ZZ999"},
        "symptoms": [{"text": "fever", "assertion": "reported", "evidence": "he has a very high fever"}],
        "medication_mentions": [{"text": "Amoxicillin 500 mg"}],
        "tasks": [{"title": "Book", "category": "appointment_scheduling", "priority": "routine",
                   "evidence": "book me a slot"}],
    }
    ex = validate_extraction(raw, "Patient needs help with something.")
    assert ex.patient.name is None and ex.patient.age is None and ex.patient.patient_id is None
    assert ex.medication_mentions == []
    assert ex.symptoms[0].evidence is None and ex.tasks[0].evidence is None
    assert ex.review_required and len(ex.review_reasons) >= 4


# ------------------------------------------------------------------ LLM provider handling
def llm_env(monkeypatch, allowed=True):
    monkeypatch.setenv("EXTRACTION_PROVIDER", "llm")
    monkeypatch.setenv("EXTERNAL_LLM_ALLOWED", "true" if allowed else "false")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")


def transport_returning(payload=None, text=None, status=200, raise_exc=None, seen=None):
    def handler(request: httpx.Request):
        if seen is not None:
            seen.append(request)
        if raise_exc:
            raise raise_exc
        body = text if text is not None else json.dumps(payload)
        return httpx.Response(status, json={"content": [{"type": "text", "text": body}]})
    return httpx.MockTransport(handler)


@pytest.fixture
def use_llm(monkeypatch):
    def _install(transport):
        monkeypatch.setattr(ex_service, "llm_extractor", LLMExtractor(transport=transport))
    return _install


GOOD = {
    "patient": {"name": "Akshay", "age": 42},
    "reported_concern": "Possible right forearm fracture",
    "diagnosis_mentions": [{"text": "fracture", "assertion": "possible", "evidence": "possible right forearm fracture"}],
    "tasks": [{"title": "Clinical assessment", "category": "clinical_review", "priority": "requires_review",
               "evidence": "Needs clinical assessment", "requested_action": "Arrange clinical assessment"}],
    "priority": "requires_review", "review_required": True, "verified_diagnosis": "Right radius fracture",
}
TEXT = "Patient Akshay, age 42. Reports a possible right forearm fracture. Needs clinical assessment."


def test_llm_output_is_validated_and_used(monkeypatch, use_llm):
    llm_env(monkeypatch)
    seen = []
    use_llm(transport_returning(GOOD, seen=seen))
    out = run(TEXT)
    assert out.provider == "llm" and len(seen) == 1
    assert out.extraction.verified_diagnosis is None            # model tried to assert one; stripped
    assert out.extraction.patient.name == "Akshay"
    assert out.ticket_drafts[0]["required_action"] == "Arrange clinical assessment"
    assert out.ticket_drafts[0]["requires_human_review"] is True
    assert seen[0].headers["x-api-key"] == "test-key"
    assert TEXT in json.loads(seen[0].content)["messages"][0]["content"]


def test_llm_hallucinations_are_dropped_not_trusted(monkeypatch, use_llm):
    llm_env(monkeypatch)
    bad = dict(GOOD, patient={"name": "Zorro Invented", "age": 99}, medication_mentions=[{"text": "Warfarin 5 mg"}])
    use_llm(transport_returning(bad))
    ex = run(TEXT).extraction
    assert ex.patient.name is None and ex.patient.age is None and ex.medication_mentions == []
    assert ex.review_required


def test_llm_invalid_json_falls_back_to_rules_with_review(monkeypatch, use_llm):
    llm_env(monkeypatch)
    use_llm(transport_returning(text="Sure! Here is the answer: not json"))
    out = run(TEXT)
    assert out.provider == "rules" and out.extraction.review_required
    assert any("unavailable or rejected" in r for r in out.extraction.review_reasons)
    assert out.ticket_drafts          # the request is never dropped


def test_llm_schema_violation_falls_back(monkeypatch, use_llm):
    llm_env(monkeypatch)
    use_llm(transport_returning({"priority": "super-urgent", "tasks": "none"}))
    out = run(TEXT)
    assert out.provider == "rules" and any("schema validation" in w for w in out.warnings)


@pytest.mark.parametrize("failure", [
    {"raise_exc": httpx.ConnectError("service down")},
    {"raise_exc": httpx.ReadTimeout("slow")},
    {"status": 503, "payload": {}},
])
def test_llm_outage_falls_back_without_losing_the_request(monkeypatch, use_llm, failure):
    llm_env(monkeypatch)
    use_llm(transport_returning(**failure))
    out = run(TEXT)
    assert out.provider == "rules" and out.ticket_drafts and out.extraction.review_required


def test_external_llm_is_never_called_without_explicit_authorisation(monkeypatch, use_llm):
    llm_env(monkeypatch, allowed=False)
    seen = []
    use_llm(transport_returning(GOOD, seen=seen))
    out = run(TEXT)
    assert seen == [] and out.provider == "rules"
    assert any("EXTERNAL_LLM_ALLOWED" in w for w in out.warnings)


def test_llm_cannot_downgrade_an_emergency(monkeypatch, use_llm):
    llm_env(monkeypatch)
    text = "Patient Hari has severe chest pain and is sweating. Please come immediately."
    mild = {"tasks": [{"title": "Comfort check", "category": "general_patient_support", "priority": "routine"}],
            "priority": "routine"}
    use_llm(transport_returning(mild))
    out = run(text)
    assert out.provider == "llm"
    assert any(d["urgency"] == "STAT_EMERGENCY" for d in out.ticket_drafts)
    assert out.extraction.priority.value == "emergency" and out.extraction.review_required


def test_conversation_persists_the_validated_extraction(care):
    nurse = care.make_user("nurse")
    res = care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": TEXT, "language": "en"})
    assert res.status_code == 200
    body = res.json()
    assert body["structured_extraction"]["patient"]["name"] == "Akshay"
    assert body["structured_extraction"]["verified_diagnosis"] is None
    stored = care.client.get(f"/api/calls/{body['call']['id']}", headers=nurse.headers).json()
    assert stored["extraction"]["diagnosis_mentions"][0]["assertion"] == "possible"
    assert stored["extraction_provider"] == "rules"


def test_transcripts_never_create_prescriptions(care):
    nurse = care.make_user("nurse")
    p = care.make_patient("Gita Rao")
    care.client.post("/api/calls/process-transcript", headers=nurse.headers, json={
        "raw_transcript": "Patient Gita Rao, the doctor prescribed Amoxicillin 500 mg three times daily for a week.",
        "language": "en", "patient_id": p.id})
    with care.Session() as db:
        assert db.query(Medication).count() == 0
pytestmark = pytest.mark.real_auth


# ------------------------------------------------------------------ regression: clinical sentences must never be dropped
def test_clinical_statement_is_kept_when_another_sentence_matches_a_keyword():
    """Regression: an allowlist 'greeting filter' used to discard 'Reports a possible ... fracture' whenever
    another sentence in the same call (here: billing) contained a known keyword."""
    out = run("Patient Akshay, age 42. Reports a possible right forearm fracture. Needs clinical assessment. "
              "Please also send the billing statement.")
    cats = {t.category.value for t in out.extraction.tasks}
    assert "billing_inquiry" in cats and "clinical_review" in cats
    clinical = [t for t in out.extraction.tasks if t.category.value == "clinical_review"]
    assert any("fracture" in (t.evidence or t.description).lower() for t in clinical)
    assert out.extraction.review_required and out.extraction.priority.value == "requires_review"


def test_pure_greetings_and_bare_identification_still_create_no_task():
    from nlp_parser import is_pure_intro_greeting as greeting
    for text in ("Hi, this is nurse on 4th floor", "Hello", "Good morning", "Thank you", "Patient Akshay, age 42",
                 "Mr Rao in room 12", "this is the nurse from the 4th floor"):
        assert greeting(text), text
    for text in ("Reports a possible right forearm fracture", "Needs clinical assessment",
                 "Please send a nurse to room 4", "He is feeling very dizzy", "send the billing statement"):
        assert not greeting(text), text
    out = run("Hi, this is the nurse on the 4th floor. Patient Rao in room 12 needs fresh linen.")
    assert len(out.extraction.tasks) == 1


def test_unrecognised_sentences_become_reviewable_tasks_not_silence():
    out = run("Patient Nila says her legs feel strange since morning. Please send the billing statement.")
    assert len(out.extraction.tasks) == 2
