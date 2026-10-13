import pytest
import os
import sys
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import Base, get_db
from main import app
from nlp_parser import evaluate_clinical_urgency_and_evidence, process_real_transcript

# Setup test in-memory SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_database():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)

client = TestClient(app)

# 1. Refractory Acute Symptoms (False Negation Prevention)
def test_refractory_symptom_not_suppressed_english():
    """Phrases like 'not going away' or 'not improving' must NOT suppress acute emergencies."""
    text = "Arthur in Room 314 has chest pain that is not going away despite medication."
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="en")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_refractory"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"
    assert len(eval_res["refractory_markers"]) > 0

def test_refractory_symptom_not_suppressed_hindi():
    """Hindi refractory symptoms like 'कम नहीं हो रहा' must NOT be suppressed."""
    text = "मरीज के सीने में बहुत दर्द है और दवा के बाद भी कम नहीं हो रहा है।"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="hi")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_refractory"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"

def test_refractory_symptom_not_suppressed_kannada():
    """Kannada refractory symptoms like 'ಕಡಿಮೆ ಆಗುತ್ತಿಲ್ಲ' must NOT be suppressed."""
    text = "ರೋಗಿಗೆ ಎದೆ ನೋವು ಇದೆ ಮತ್ತು ಮಾತ್ರೆ ತಗೊಂಡ್ರು ಕಡಿಮೆ ಆಗುತ್ತಿಲ್ಲ।"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="kn")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_refractory"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"

# 2. Contrastive / Emphatic Negation (False Negation Prevention)
def test_contrastive_emphatic_negation_english():
    """'Not mild chest pain' is emphatic affirmation, NOT negation."""
    text = "This is not mild chest pain, the patient is clutching his chest in agony!"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="en")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"

def test_contrastive_emphatic_negation_hindi():
    """'हल्का दर्द नहीं है' is emphatic affirmation of severe emergency."""
    text = "यह कोई हल्का दर्द नहीं है, मरीज को दिल का दौरा पड़ रहा है!"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="hi")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"

def test_contrastive_emphatic_negation_kannada():
    """'ಸಾಮಾನ್ಯ ನೋವು ಅಲ್ಲ' is emphatic affirmation."""
    text = "ಇದು ಸಾಮಾನ್ಯ ನೋವು ಅಲ್ಲ, ರೋಗಿಗೆ ತೀವ್ರ ಎದೆ ನೋವು ಇದೆ!"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="kn")
    assert eval_res["is_emergency"] is True
    assert eval_res["is_negated"] is False
    assert eval_res["urgency"] == "STAT_EMERGENCY"

# 3. Collateral Negation Protection (Multi-Symptom Scoping)
def test_collateral_negation_protection_english():
    """Negating fever or headache must NOT suppress unconsciousness or breathing failure."""
    text = "Patient has no fever or headache, but is unresponsive and cannot breathe!"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="en")
    assert eval_res["is_emergency"] is True
    assert eval_res["urgency"] == "STAT_EMERGENCY"
    assert any("cannot breathe" in s or "unresponsive" in s for s in eval_res["active_symptoms"])

def test_collateral_negation_protection_hindi():
    """Negating nausea must not suppress unconsciousness."""
    text = "मरीज को उल्टी नहीं है, लेकिन फर्श पर गिर पड़े और बेहोश हैं।"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="hi")
    assert eval_res["is_emergency"] is True
    assert eval_res["urgency"] == "STAT_EMERGENCY"
    assert any("बेहोश" in s for s in eval_res["active_symptoms"])

def test_collateral_negation_protection_kannada():
    """Negating fever must not suppress seizure or unconsciousness."""
    text = "ಜ್ವರ ಇಲ್ಲ, ಆದರೆ ರೋಗಿ ಪ್ರಜ್ಞಾಹೀನರಾಗಿದ್ದಾರೆ ಮತ್ತು ಫಿಟ್ಸ್ ಬಂದಿದೆ।"
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang="kn")
    assert eval_res["is_emergency"] is True
    assert eval_res["urgency"] == "STAT_EMERGENCY"
    assert any("ಪ್ರಜ್ಞಾಹೀನ" in s or "ಫಿಟ್ಸ್" in s for s in eval_res["active_symptoms"])

# 4. Historical Symptoms vs Acute Emergency
def test_historical_symptom_handling_english():
    """Historical symptoms from weeks ago must NOT trigger STAT_EMERGENCY."""
    text = "Patient had chest pain 3 weeks ago while walking, but currently feels fine and has no symptoms today."
    res = process_real_transcript(text, language="en")
    assert res["emergency_detected"] is False
    assert len(res["tickets"]) == 1
    t = res["tickets"][0]
    assert t["urgency"] != "STAT_EMERGENCY"
    assert "HISTORICAL_ACUTE_SYMPTOM" in t["clinical_flags"]
    assert "historical" in t["priority_rationale"].lower()

def test_historical_symptom_handling_hindi():
    """10 दिन पहले सीने में दर्द हुआ था, अब ठीक हैं -> Historical, not acute emergency."""
    text = "मरीज को 10 दिन पहले सीने में दर्द हुआ था, अब ठीक हैं और रूटीन चेकअप के लिए पूछ रहे हैं।"
    res = process_real_transcript(text, language="hi")
    assert res["emergency_detected"] is False
    t = res["tickets"][0]
    assert t["urgency"] != "STAT_EMERGENCY"
    assert "HISTORICAL_ACUTE_SYMPTOM" in t["clinical_flags"]

def test_historical_symptom_handling_kannada():
    """ಎರಡು ವಾರಗಳ ಹಿಂದೆ ಎದೆ ನೋವು ಇತ್ತು -> Historical."""
    text = "ರೋಗಿಗೆ ಎರಡು ವಾರಗಳ ಹಿಂದೆ ಎದೆ ನೋವು ಇತ್ತು, ಈಗ ಆರಾಮಾಗಿದ್ದಾರೆ ಮತ್ತು ಫಾಲೋ-ಅಪ್ ಭೇಟಿಗೆ ಕರೆ ಮಾಡಿದ್ದಾರೆ।"
    res = process_real_transcript(text, language="kn")
    assert res["emergency_detected"] is False
    t = res["tickets"][0]
    assert t["urgency"] != "STAT_EMERGENCY"
    assert "HISTORICAL_ACUTE_SYMPTOM" in t["clinical_flags"]

# 5. Clinical Uncertainty & Human Review Flagging
def test_uncertainty_handling_and_human_review_flag_english():
    """Uncertainty around high-risk clinical symptoms must be flagged for human review."""
    text = "Not sure if Arthur is having a heart attack or severe gas, he is sweating profusely."
    res = process_real_transcript(text, language="en")
    t = res["tickets"][0]
    assert t["requires_human_review"] is True
    assert "REQUIRES_CLINICAL_REVIEW" in t["clinical_flags"]
    assert "FLAGGED_UNCERTAIN_EMERGENCY" in t["clinical_flags"]
    assert len(t["human_review_reason"]) > 5
    assert "uncertainty" in t["human_review_reason"].lower()

def test_uncertainty_handling_and_human_review_flag_hindi():
    """Hindi uncertainty 'समझ नहीं आ रहा कि दिल का दौरा है या गैस' must be flagged for human review."""
    text = "समझ नहीं आ रहा कि मरीज को दिल का दौरा पड़ रहा है या गैस है, पक्का नहीं पता।"
    res = process_real_transcript(text, language="hi")
    t = res["tickets"][0]
    assert t["requires_human_review"] is True
    assert "REQUIRES_CLINICAL_REVIEW" in t["clinical_flags"]
    assert "FLAGGED_UNCERTAIN_EMERGENCY" in t["clinical_flags"]

def test_uncertainty_handling_and_human_review_flag_kannada():
    """Kannada uncertainty 'ಎದೆ ನೋವು ಇರಬಹುದು ಅಥವಾ ಗ್ಯಾಸ್ಟ್ರಿಕ್ ಇರಬಹುದು' must be flagged for review."""
    text = "ರೋಗಿಗೆ ಎದೆ ನೋವು ಇರಬಹುದು ಅಥವಾ ಗ್ಯಾಸ್ಟ್ರಿಕ್ ಇರಬಹುದು, ಗೊಂದಲವಾಗಿದೆ ಬಂದು ನೋಡಿ।"
    res = process_real_transcript(text, language="kn")
    t = res["tickets"][0]
    assert t["requires_human_review"] is True
    assert "REQUIRES_CLINICAL_REVIEW" in t["clinical_flags"]
    assert "FLAGGED_UNCERTAIN_EMERGENCY" in t["clinical_flags"]

# 6. Mixed-Language Code Switching (Hinglish and Kanglish)
def test_mixed_language_hinglish_emergency():
    """Code-switched Hinglish ('chest pain ho raha hai') triggers emergency."""
    text = "Patient ko sudden chest pain ho raha hai aur breathing problem hai!"
    res = process_real_transcript(text, language="hi")
    assert res["emergency_detected"] is True
    assert res["tickets"][0]["urgency"] == "STAT_EMERGENCY"

def test_mixed_language_hinglish_with_negation():
    """Code-switched Hinglish with negation ('fever nahi hai, but patient faint ho gaya')."""
    text = "Fever nahi hai, but patient room me faint ho gaya aur uth nahi pa rahe!"
    res = process_real_transcript(text, language="hi")
    assert res["emergency_detected"] is True
    assert res["tickets"][0]["urgency"] == "STAT_EMERGENCY"

def test_mixed_language_kanglish_emergency():
    """Code-switched Kanglish ('chest pain aagide and breathing problem ide')."""
    text = "Patient ge sudden chest pain aagide and breathing problem ide!"
    res = process_real_transcript(text, language="kn")
    assert res["emergency_detected"] is True
    assert res["tickets"][0]["urgency"] == "STAT_EMERGENCY"

def test_mixed_language_kanglish_with_negation():
    """Code-switched Kanglish with partial negation ('BP high illa, but severe chest pain ide')."""
    text = "BP high illa, but severe chest pain ide!"
    res = process_real_transcript(text, language="kn")
    assert res["emergency_detected"] is True
    assert res["tickets"][0]["urgency"] == "STAT_EMERGENCY"

# 7. Endpoint & SQLite Persistence of Evidence and Human Review Flag
def test_api_endpoint_persists_urgency_evidence_and_review_flag():
    """Verify endpoint saves requires_human_review and urgency_evidence to SQLite and exposes via API."""
    payload = {
        "caller_name": "Nurse Nancy",
        "patient_name": "Robert Miller",
        "room_number": "Room 512",
        "raw_transcript": (
            "Not sure if Robert is having a heart attack or severe indigestion in Room 512. "
            "Also we need fresh bedsheets."
        ),
        "language": "en"
    }
    resp = client.post("/api/calls/process-transcript", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    tickets = data["extracted_tickets"]
    assert len(tickets) >= 2
    t1 = tickets[0]

    assert t1["requires_human_review"] is True
    assert "REQUIRES_CLINICAL_REVIEW" in t1["clinical_flags"]
    assert t1["urgency_evidence"] is not None
    assert "matched_symptoms" in t1["urgency_evidence"]
    assert len(t1["urgency_evidence"]["matched_symptoms"]) > 0

    # Verify query by requires_human_review filter
    filtered_resp = client.get("/api/tickets?requires_human_review=true")
    assert filtered_resp.status_code == 200
    filtered_tickets = filtered_resp.json()
    assert len(filtered_tickets) >= 1
    assert any(t["id"] == t1["id"] for t in filtered_tickets)
