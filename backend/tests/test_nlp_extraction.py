import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from nlp_parser import (
    process_real_transcript,
    classify_multilingual_segment,
    extract_explicit_deadline,
    check_emergency_with_negation,
    split_multilingual_transcript,
    STANDARD_CATEGORIES
)

def test_all_14_standard_categories_defined():
    """Verify that all 14 categories from DL-VVCE-HK26-HLS004 are defined."""
    assert len(STANDARD_CATEGORIES) == 14
    expected_categories = [
        "Emergency and urgent clinical concerns",
        "Nursing and patient care",
        "Medication, pharmacy and prescription queries",
        "Appointments and OPD coordination",
        "Appointment rescheduling and cancellation",
        "Specialist consultations and disease-related appointments",
        "Routine follow-up appointments",
        "Billing and payment queries",
        "Insurance and pre-authorisation queries",
        "Admission and discharge coordination",
        "Facilities, housekeeping and transport",
        "Food, dietary and nutrition requests",
        "General inquiries and information requests",
        "Promised callbacks and other follow-up commitments"
    ]
    for cat in expected_categories:
        assert cat in STANDARD_CATEGORIES

def test_category_1_emergency_clinical_concern():
    result = process_real_transcript(
        "Patient in Room 204 has crushing chest pain and shortness of breath."
    )
    assert result["emergency_detected"] is True
    assert len(result["tickets"]) == 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Emergency and urgent clinical concerns"
    assert ticket["department"] == "Rapid Response & Critical Nursing"
    assert ticket["urgency"] == "STAT_EMERGENCY"
    assert ticket["confidence_score"] >= 0.95
    assert "rapid response" in ticket["required_action"].lower()
    assert "5 minutes" in ticket["priority_rationale"].lower()

def test_category_2_nursing_and_patient_care():
    result = process_real_transcript(
        "Patient in Room 105 has severe knee pain after knee replacement and needs assistance going to the bathroom."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Nursing and patient care"
    assert ticket["department"] == "Nursing & Clinical Care"
    assert ticket["urgency"] == "URGENT"
    assert "nurse" in ticket["required_action"].lower()

def test_category_3_medication_and_pharmacy():
    result = process_real_transcript(
        "Please check if patient Arthur has a penicillin allergy before administering the 500 mg antibiotic dose."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Medication, pharmacy and prescription queries"
    assert ticket["department"] == "Pharmacy & Therapeutics"
    assert "pharmacist" in ticket["required_action"].lower()
    assert "MEDICATION_SAFETY_CHECK" in ticket["clinical_flags"]

def test_category_4_appointments_and_opd_coordination():
    result = process_real_transcript(
        "I would like to book a new OPD appointment to consult a doctor next Monday."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Appointments and OPD coordination"
    assert ticket["department"] == "Outpatient & Appointment Coordination"
    assert ticket["urgency"] == "ROUTINE"
    assert ticket["intent"] == "book_opd_appointment"

def test_category_5_appointment_rescheduling_and_cancellation():
    result = process_real_transcript(
        "Please reschedule Arthur's appointment from Thursday to next Tuesday at 10 AM."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Appointment rescheduling and cancellation"
    assert ticket["department"] == "Outpatient & Appointment Coordination"
    assert ticket["intent"] == "reschedule_or_cancel_appointment"

def test_category_6_specialist_consultations():
    result = process_real_transcript(
        "The patient needs a specialist consultation with a cardiologist for a second opinion."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Specialist consultations and disease-related appointments"
    assert ticket["department"] == "Specialist Clinic & OPD Services"

def test_category_7_routine_follow_up():
    result = process_real_transcript(
        "Calling to schedule our routine follow-up appointment after last week's gallbladder surgery."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Routine follow-up appointments"
    assert ticket["department"] == "Outpatient & Appointment Coordination"
    assert ticket["intent"] == "routine_follow_up_booking"

def test_category_8_billing_and_payment():
    result = process_real_transcript(
        "Could you send us the itemized bill and receipt for Room 314 before 4 PM?"
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Billing and payment queries"
    assert ticket["department"] == "Patient Billing & Accounts"
    assert ticket["urgency"] == "INQUIRY"
    assert ticket["explicit_deadline"] is not None
    assert "before 4 PM" in ticket["explicit_deadline"]

def test_category_9_insurance_and_preauthorisation():
    result = process_real_transcript(
        "Has the TPA insurance pre-authorisation claim approval come through for cashless surgery?"
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Insurance and pre-authorisation queries"
    assert ticket["department"] == "Health Insurance & Pre-Authorisation"
    assert ticket["urgency"] == "INQUIRY"

def test_category_10_admission_and_discharge():
    result = process_real_transcript(
        "We are waiting for the doctor to sign the discharge summary paperwork so we can take the patient home."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Admission and discharge coordination"
    assert ticket["department"] == "Administration & Discharge Coordination"

def test_category_11_facilities_housekeeping():
    result = process_real_transcript(
        "A water glass shattered on the floor in Room 202 and there is broken glass and water everywhere."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Facilities, housekeeping and transport"
    assert ticket["department"] == "Facilities & Environmental Services"

def test_category_12_food_and_dietary():
    result = process_real_transcript(
        "Patient in Room 410 is diabetic and is still waiting for their lunch tray, please check."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Food, dietary and nutrition requests"
    assert ticket["department"] == "Dietary & Clinical Nutrition"
    assert "DIABETIC_NPO_WATCH" in ticket["clinical_flags"]

def test_category_13_general_inquiries():
    result = process_real_transcript(
        "What are the evening visiting hours and visitor policy for the general ward?"
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "General inquiries and information requests"
    assert ticket["department"] == "Hospital Information & Patient Helpdesk"
    assert ticket["urgency"] == "INQUIRY"

def test_category_14_promised_callbacks():
    result = process_real_transcript(
        "Dr. Sharma promised a callback regarding Arthur's test results this morning and we are still waiting for a call."
    )
    assert len(result["tickets"]) >= 1
    ticket = result["tickets"][0]
    assert ticket["category"] == "Promised callbacks and other follow-up commitments"
    assert ticket["department"] == "Clinical Follow-up & Care Coordination"
    assert ticket["intent"] == "promised_callback_followup"

def test_compound_sentence_multi_request_extraction():
    """Verify that multi-request conversations decompose into separate tasks without dropping secondary requests."""
    transcript = (
        "Arthur in Room 314 has acute chest pain! "
        "Also, we need his insulin dosage verified by the pharmacist within 1 hour. "
        "Plus, can you send housekeeping to mop the floor? "
        "And one more thing, please have the billing department send an itemized bill before 3 PM."
    )
    result = process_real_transcript(transcript)
    assert result["emergency_detected"] is True
    assert len(result["tickets"]) == 4

    categories = [t["category"] for t in result["tickets"]]
    assert "Emergency and urgent clinical concerns" in categories
    assert "Medication, pharmacy and prescription queries" in categories
    assert "Facilities, housekeeping and transport" in categories
    assert "Billing and payment queries" in categories

    # Check deadlines
    pharmacy_ticket = next(t for t in result["tickets"] if "Medication" in t["category"])
    assert pharmacy_ticket["explicit_deadline"] is not None
    assert "within 1 hour" in pharmacy_ticket["explicit_deadline"].lower()

    billing_ticket = next(t for t in result["tickets"] if "Billing" in t["category"])
    assert billing_ticket["explicit_deadline"] is not None
    assert "before 3 PM" in billing_ticket["explicit_deadline"]

def test_no_deadline_hallucination():
    """When caller does not state a deadline, explicit_deadline must be None (zero hallucination)."""
    transcript = "Patient in Room 102 would like extra blankets and a clean pillow."
    result = process_real_transcript(transcript)
    assert len(result["tickets"]) == 1
    assert result["tickets"][0]["explicit_deadline"] is None

def test_hindi_compound_multi_request():
    """Test multi-request extraction in Hindi with Devanagari script preservation."""
    transcript = (
        "मरीज के सीने में तेज दर्द है! "
        "इसके अलावा उनकी कल की अपॉइंटमेंट को रीशेड्यूल करना है। "
        "साथ ही 4 बजे से पहले बिलिंग की रसीद चाहिए।"
    )
    result = process_real_transcript(transcript, language="hi")
    assert result["emergency_detected"] is True
    assert len(result["tickets"]) == 3
    assert result["tickets"][0]["category"] == "Emergency and urgent clinical concerns"
    assert result["tickets"][1]["category"] == "Appointment rescheduling and cancellation"
    assert result["tickets"][2]["category"] == "Billing and payment queries"
    assert result["tickets"][2]["explicit_deadline"] is not None
    assert "4 बजे" in result["tickets"][2]["explicit_deadline"]

def test_kannada_compound_multi_request():
    """Test multi-request extraction in Kannada with Kannada script preservation."""
    transcript = (
        "ರೋಗಿಗೆ ಎದೆ ನೋವು ತುಂಬಾ ಜಾಸ್ತಿ ಇದೆ! "
        "ಹಾಗೆಯೇ ಅವರ ಬಿಪಿ ಮಾತ್ರೆಗಳ ಬಗ್ಗೆ ಫಾರ್ಮಸಿ ಜೊತೆ ಮಾತನಾಡಬೇಕು. "
        "ಜೊತೆಗೆ ಕೊಠಡಿಯಲ್ಲಿ ನೆಲದ ಮೇಲೆ ನೀರು ಬಿದ್ದಿದೆ ಸ್ವಚ್ಛತೆ ಮಾಡಬೇಕು."
    )
    result = process_real_transcript(transcript, language="kn")
    assert result["emergency_detected"] is True
    assert len(result["tickets"]) == 3
    assert result["tickets"][0]["category"] == "Emergency and urgent clinical concerns"
    assert result["tickets"][1]["category"] == "Medication, pharmacy and prescription queries"
    assert result["tickets"][2]["category"] == "Facilities, housekeeping and transport"

def test_negation_safeguard():
    """Negated symptoms must never trigger STAT_EMERGENCY."""
    for text, lang in [
        ("Patient denies chest pain and has no shortness of breath, but has mild rash.", "en"),
        ("मरीज को सीने में दर्द नहीं है, केवल हल्का सिरदर्द है।", "hi"),
        ("ರೋಗಿಗೆ ಎದೆ ನೋವು ಇಲ್ಲ, ಸ್ವಲ್ಪ ತಲೆನೋವು ಇದೆ.", "kn")
    ]:
        result = process_real_transcript(text, language=lang)
        assert result["emergency_detected"] is False
        for t in result["tickets"]:
            assert t["urgency"] != "STAT_EMERGENCY"
