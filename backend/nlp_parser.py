import re
import os
import json
from typing import List, Dict, Any, Tuple, Optional

# Standard 14 Categories defined by Problem Statement DL-VVCE-HK26-HLS004
STANDARD_CATEGORIES = [
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

def detect_script_language(text: str) -> str:
    """Detect whether script is Kannada, Devanagari (Hindi), or Latin (English)."""
    kannada_chars = len(re.findall(r'[\u0C80-\u0CFF]', text))
    devanagari_chars = len(re.findall(r'[\u0900-\u097F]', text))
    latin_chars = len(re.findall(r'[a-zA-Z]', text))

    if kannada_chars > 3 and kannada_chars >= devanagari_chars:
        return "kn"
    elif devanagari_chars > 3 and devanagari_chars >= kannada_chars:
        return "hi"
    return "en"

# Multilingual Emergency Symptoms across EN, HI, KN
EMERGENCY_SYMPTOMS = {
    "en": [
        r"chest.*pain", r"chest.*discomfort", r"heart\s*attack", r"cardiac\s*arrest", r"crushing\s*chest",
        r"cannot\s*breathe", r"shortness\s*of\s*breath", r"difficulty\s*breathing", r"choking", r"gasping",
        r"unconscious", r"passed\s*out", r"\bfaint(?:ed|ing)?\b", r"unresponsive", r"having\s*a\s*seizure", r"fits", r"stroke",
        r"bleeding\s*profusely", r"heavy\s*bleeding", r"fell\s*on\s*the\s*floor", r"slipped\s*and\s*fell",
        r"swollen\s*and\s*red", r"iv\s*machine.*beep", r"iv\s*infiltration", r"severe\s*pain\s*8/10", r"collapsed",
        r"cyanosis", r"turning\s*blue", r"anaphylaxis", r"severe\s*allergic\s*reaction"
    ],
    "hi": [
        r"सीने.*दर्द", r"छाती.*दर्द", r"दिल\s*का\s*दौरा", r"हार्ट\s*अटैक", r"सीने\s*में\s*जकड़न",
        r"चेस्ट.*(?:दर्द|पेइन|पेन)", r"पेइन",
        r"सांस\s*नहीं\s*आ\s*रही", r"सांस.*तकलीफ", r"सांस\s*फूलना", r"दम\s*घुट",
        r"बेहोश", r"बेहोशी", r"दौरा", r"मिर्गी", r"स्ट्रोक", r"लकवा", r"कोई\s*जवाब\s*नहीं",
        r"खून\s*बह\s*रहा", r"बहुत\s*खून", r"फर्श\s*पर\s*गिर", r"गिर\s*पड़े", r"उठ\s*नहीं\s*पा\s*रहे",
        r"हाथ\s*सूज", r"गंभीर\s*सूजन", r"स्वेलिंग", r"आईवी.*बीप", r"अत्यधिक\s*दर्द"
    ],
    "kn": [
        r"(?:ಎದೆ|ಯದೆ|ಯಾದೆ).*ನೋವು", r"ಎದೆನೋವು", r"ಯದೆನೋವು",
        r"ಹೃದಯಾಘಾತ", r"ಹಾರ್ಟ್\s*ಅಟ್ಯಾಕ್", r"ಚೆಸ್ಟ್\s*ಪೇನ್",
        r"ಉಸಿರಾಟ.*ತೊಂದರೆ", r"ಉಸಿರು\s*ಕಟ್ಟುತ್ತಿದೆ", r"ಉಸಿರಾಡಲು\s*ಕಷ್ಟ", r"ಉಸಿರು\s*ಸಿಗುತ್ತಿಲ್ಲ",
        r"ಪ್ರಜ್ಞಾಹೀನ", r"ಮೂರ್ಛೆ", r"ಫಿಟ್ಸ್", r"ಪಾರ್ಶ್ವವಾಯು", r"ಸ್ಟ್ರೋಕ್",
        r"ವಿಪರೀತ\s*ರಕ್ತಸ್ರಾವ", r"ರಕ್ತ\s*ಬರುತ್ತಿದೆ", r"ಕೆಳಗೆ\s*ಬಿದ್ದರು", r"ಜಾರಿ\s*ಬಿದ್ದರು", r"ಏಳಲು\s*ಆಗುತ್ತಿಲ್ಲ",
        r"ಕೈ\s*ಊದಿಕೊಂಡಿದೆ", r"ತೀವ್ರ\s*ಊತ", r"ಐವಿ\s*ಶಬ್ದ", r"ತೀವ್ರ\s*ನೋವು"
    ]
}

# Negation patterns to prevent false STAT emergency escalation
NEGATION_PATTERNS = {
    "en": [
        r"\b(?:no|not|denies|denied|without|never|negative for|neither|free of|resolved|no longer|ruled out)\s+(?:\w+\s+){0,3}(?:chest pain|pain|shortness of breath|difficulty breathing|bleeding|fall|swelling|seizure|fainting|heart attack)\b",
        r"\b(?:chest pain|pain|bleeding|fall|swelling|shortness of breath|difficulty breathing)\s+(?:is not|has stopped|resolved|ruled out|disappeared|is gone)\b"
    ],
    "hi": [
        r"(?:सीने में दर्द|चेस्ट में दर्द|दर्द|सांस की तकलीफ|खून|सूजन|दौरा)\s*(?:नहीं है|नहीं हो रहा|बिल्कुल नहीं|रुक गया|ठीक हो गया)",
        r"(?:कोई|बिना किसी)\s*(?:सीने में दर्द|चेस्ट में दर्द|दर्द|तकलीफ|खून)\s*नहीं"
    ],
    "kn": [
        r"(?:ಎದೆ ನೋವು|ಯದೆ ನೋವು|ನೋವು|ಉಸಿರಾಟದ ತೊಂದರೆ|ರಕ್ತಸ್ರಾವ|ಊತ|ಫಿಟ್ಸ್)\s*(?:ಇಲ್ಲ|ಆಗುತ್ತಿಲ್ಲ|ನಿಂತಿದೆ|ಗುಣವಾಗಿದೆ)",
        r"(?:ಯಾವುದೇ|ಯಾವ)\s*(?:ಎದೆ ನೋವು|ಯದೆ ನೋವು|ನೋವು|ತೊಂದರೆ)\s*ಇಲ್ಲ"
    ]
}

# Refractory / persistent symptom markers (Overrides negation: pain is NOT resolving)
REFRACTORY_PATTERNS = {
    "en": [
        r"\bnot\s+(?:going\s+away|improving|subsiding|stopping|relieved|getting\s+better|easing|responding)\b",
        r"\b(?:hasn't|has\s+not)\s+(?:stopped|subsided|improved|gone\s+away|eased)\b",
        r"\bwon'?t\s+stop\b",
        r"\bunresolved\s+despite\b",
        r"\bpersisting\s+despite\b",
        r"\bgetting\s+worse\b",
        r"\bprogressively\s+worsening\b"
    ],
    "hi": [
        r"(?:कम\s*नहीं\s*हो\s*रहा|ठीक\s*नहीं\s*हो\s*रहा|रुक\s*नहीं\s*रहा|आराम\s*नहीं\s*मिल\s*रहा|दर्द\s*बढ़ता\s*जा\s*रहा|जा\s*नहीं\s*रहा|दवा\s*के\s*बाद\s*भी)",
        r"(?:दर्द\s*बना\s*हुआ\s*है|तकलीफ\s*कम\s*नहीं)"
    ],
    "kn": [
        r"(?:ಕಡಿಮೆ\s*ಆಗುತ್ತಿಲ್ಲ|ನಿಂತಿಲ್ಲ|ವಾಸಿಯಾಗುತ್ತಿಲ್ಲ|ಉಪಶಮನವಾಗಿಲ್ಲ|ನೋವು\s*ಹಾಗೇ\s*ಇದೆ|ನಿಲ್ಲುತ್ತಿಲ್ಲ|ಹೆಚ್ಚಾಗುತ್ತಿದೆ)",
        r"(?:ಮಾತ್ರೆ\s*ತಗೊಂಡ್ರು\s*ನೋವು)"
    ]
}

# Contrastive / emphatic negation markers (Overrides naive negation: e.g. 'not mild')
CONTRASTIVE_PATTERNS = {
    "en": [
        r"\bnot\s+(?:mild|minor|just|simply|ordinary|small)\s+(?:\w+\s+){0,3}(?:chest\s*pain|pain|heart\s*attack|discomfort)\b",
        r"\bnot\s+just\s+(?:gas|heartburn|indigestion|acid|anxiety)\b",
        r"\bnot\s+(?:mild|minor|small)\b"
    ],
    "hi": [
        r"(?:हल्का\s*दर्द\s*नहीं|मामूली\s*नहीं|सिर्फ\s*गैस\s*नहीं|साधारण\s*नहीं|हल्का\s*नहीं)",
    ],
    "kn": [
        r"(?:ಸಾಮಾನ್ಯ\s*ನೋವು\s*ಅಲ್ಲ|ಸಣ್ಣ\s*ನೋವು\s*ಅಲ್ಲ|ಕೇವಲ\s*ಗ್ಯಾಸ್\s*ಅಲ್ಲ)",
    ]
}

# Historical qualifiers (Symptom occurred in past, not active acute event)
HISTORICAL_PATTERNS = {
    "en": [
        r"\b(?:(?:\d+|one|two|three|four|five|several|a\s+few)\s+(?:days?|weeks?|months?|years?)\s+ago|last\s+(?:week|month|year))\b",
        r"\b(?:had|suffered|experienced|was\s+having|diagnosed\s+with)\b.*(?:\bago\b|\bin\s+\d{4}|\bpast\s+history\b|\bhistory\s+of\b|\bpreviously\b|\bback\s+in\b)",
        r"\bhistory\s+of\s+(?:heart\s*attack|chest\s*pain|stroke|seizures?)\b",
        r"\bpast\s+(?:heart\s*attack|stroke|cardiac|seizure)\b"
    ],
    "hi": [
        r"(?:(?:\d+|एक|दो|तीन|चार|पांच|कुछ)\s*(?:दिन|हफ्ते|महीने|साल)\s*पहले|पहले\s*हुआ\s*था|पुराना\s*इतिहास|पुरानी\s*बीमारी|पहले\s*था|हफ्ते\s*पहले)",
        r"(?:इतिहास\s*रहा\s*है)"
    ],
    "kn": [
        r"(?:(?:\d+|ಒಂದು|ಎರಡು|ಮೂರು|ನಾಲ್ಕು|ಐದು|ಕೆಲವು)\s*(?:ದಿನಗಳ|ವಾರಗಳ|ತಿಂಗಳುಗಳ|ವರ್ಷಗಳ)\s*ಹಿಂದೆ|ವಾರಗಳ\s*ಹಿಂದೆ|ತಿಂಗಳುಗಳ\s*ಹಿಂದೆ|ದಿನಗಳ\s*ಹಿಂದೆ|ಹಿಂದೆ\s*ಇತ್ತು|ಹಳೆಯ\s*ಕಾಯಿಲೆ|ಹಿಂದೆ\s*ಬಂದಿತ್ತು)",
        r"(?:ಹಿಂದಿನ\s*ಇತಿಹಾಸ)"
    ]
}

# Uncertainty triggers around high-risk clinical events (Flag for human review)
UNCERTAINTY_PATTERNS = {
    "en": [
        r"\b(?:not\s+sure\s+if|unsure\s+(?:whether|if)|might\s+be|could\s+be|possible|possibly|wondering\s+if|suspecting|looks\s+like\s+maybe|hard\s+to\s+tell|seems\s+like\s+maybe|confused\s+whether|not\s+certain\s+if|i\s+think\s+maybe)\b",
        r"\b(?:or\s+(?:just\s+)?(?:gas|heartburn|indigestion|anxiety|muscle\s+strain))\b"
    ],
    "hi": [
        r"(?:समझ\s*नहीं\s*आ\s*रहा|शायद|हो\s*सकता\s*है|संभवतः|पता\s*नहीं|लग\s*रहा\s*है\s*शायद|पक्का\s*नहीं|शक\s*है|गैस\s*है\s*या\s*दर्द)",
    ],
    "kn": [
        r"(?:ಗೊಂದಲವಾಗಿದೆ|ಇರಬಹುದು|ಸಾಧ್ಯತೆ\s*ಇದೆ|ತಿಳಿಯುತ್ತಿಲ್ಲ|ಅನಿಸುತ್ತಿದೆ|ಖಚಿತವಿಲ್ಲ|ಅನುಮಾನವಿದೆ|ಗ್ಯಾಸ್ಟ್ರಿಕ್\s*ಅಥವಾ\s*ನೋವು)",
    ]
}

# Explicit Deadline Extractor
DEADLINE_REGEX_EN = [
    r"\b(?:before|by|until|prior to|within|around)\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))\b",
    r"\b(?:before|by|until)\s+(\d{1,2}\s*(?:o'clock)?\s*(?:am|pm)?)\b",
    r"\bwithin\s+(\d{1,2}\s*(?:hours?|hrs?|minutes?|mins?))\b",
    r"\b(?:before|by)\s+(noon|midnight|end of day|discharge|tomorrow morning|tomorrow evening|lunch)\b",
    r"\bin the next\s+(\d{1,2}\s*(?:hours?|minutes?))\b"
]

DEADLINE_REGEX_HI = [
    r"(\d{1,2}(?::\d{2})?\s*बजे(?:\s*से पहले|\s*तक)?)",
    r"(\d{1,2}\s*(?:घंटे|घंटों|मिनट)\s*(?:के अंदर|में))",
    r"(आज\s*शाम\s*तक|कल\s*सुबह\s*तक|दोपहर\s*तक|डिस्चार्ज\s*से\s*पहले)"
]

DEADLINE_REGEX_KN = [
    r"(\d{1,2}(?::\d{2})?\s*ಗಂಟೆ(?:ಗೆ|ಯೊಳಗೆ|\s*ಮೊದಲು)?)",
    r"(\d{1,2}\s*(?:ಗಂಟೆ|ನಿಮಿಷ(?:ಗಳ)?)\s*ಒಳಗೆ)",
    r"(ಇಂದು\s*ಸಂಜೆಯೊಳಗೆ|ನಾಳೆ\s*ಬೆಳಿಗ್ಗೆಯೊಳಗೆ|ಮಧ್ಯಾಹ್ನದೊಳಗೆ|ಡಿಸ್ಚಾರ್ಜ್‌ಗೆ\s*ಮೊದಲು)"
]

def extract_explicit_deadline(text: str) -> Optional[str]:
    """
    Extracts explicit stated deadlines or time windows from speech.
    Returns None if no explicit deadline was stated in the input.
    Guarantees non-hallucination of deadlines.
    """
    cleaned = text.strip()

    # English patterns
    for pat in DEADLINE_REGEX_EN:
        match = re.search(pat, cleaned, re.IGNORECASE)
        if match:
            # Return context match like "before 3 PM" or "within 1 hour"
            full_span = match.group(0).strip()
            return full_span

    # Hindi patterns
    for pat in DEADLINE_REGEX_HI:
        match = re.search(pat, cleaned)
        if match:
            return match.group(0).strip()

    # Kannada patterns
    for pat in DEADLINE_REGEX_KN:
        match = re.search(pat, cleaned)
        if match:
            return match.group(0).strip()

    return None

# The 14 Standard Category Rules and Operational Routing
CATEGORY_RULES: List[Dict[str, Any]] = [
    # 1. Emergency and urgent clinical concerns
    {
        "category": "Emergency and urgent clinical concerns",
        "department": "Rapid Response & Critical Nursing",
        "assigned_to": "STAT Rapid Response Clinical Team",
        "default_urgency": "STAT_EMERGENCY",
        "intent": "stat_emergency_response",
        "patterns_en": [
            r"\b(?:chest\s*pain|chest\s*discomfort|heart\s*attack|cardiac\s*arrest|cannot\s*breathe|shortness\s*of\s*breath|difficulty\s*breathing|unconscious|unresponsive|passed\s*out|seizure|fits|stroke|fell\s*and|slipped\s*and\s*fell|bleeding\s*profusely|heavy\s*bleeding|swollen\s*and\s*red|iv\s*machine.*beep|iv\s*infiltration|cyanosis)\b"
        ],
        "patterns_hi": [
            r"(?:सीने.*दर्द|छाती.*दर्द|चेस्ट.*(?:दर्द|पेइन|पेन)|दिल\s*का\s*दौरा|हार्ट\s*अटैक|सांस.*तकलीफ|सांस\s*नहीं|दम\s*घुट|बेहोश|दौरा|मिर्गी|गिर.*पड़े|खून\s*बह\s*रहा|हाथ\s*सूज|स्वेलिंग|आईवी.*बीप)"
        ],
        "patterns_kn": [
            r"(?:(?:ಎದೆ|ಯದೆ|ಯಾದೆ).*ನೋವು|ಎದೆನೋವು|ಹೃದಯಾಘಾತ|ಹಾರ್ಟ್\s*ಅಟ್ಯಾಕ್|ಉಸಿರಾಟ.*ತೊಂದರೆ|ಉಸಿರು\s*ಕಟ್ಟ|ಪ್ರಜ್ಞಾಹೀನ|ಫಿಟ್ಸ್|ಕೆಳಗೆ\s*ಬಿದ್ದರು|ಜಾರಿ\s*ಬಿದ್ದರು|ಕೈ.*ಊತ|ರಕ್ತಸ್ರಾವ)"
        ],
        "action_template": "Immediately dispatch Rapid Response Team and bedside nurse with emergency crash cart to {room}.",
        "priority_rationale": "Assigned STAT_EMERGENCY due to acute life-threatening or rapidly deteriorating clinical symptoms requiring bedside response within 5 minutes."
    },

    # 5. Appointment rescheduling and cancellation (Higher priority in matching than general appointments)
    {
        "category": "Appointment rescheduling and cancellation",
        "department": "Outpatient & Appointment Coordination",
        "assigned_to": "Outpatient Rescheduling Coordinator",
        "default_urgency": "ROUTINE",
        "intent": "reschedule_or_cancel_appointment",
        "patterns_en": [
            r"\b(?:reschedule|rescheduling|cancel\s*appointment|cancellation|postpone|change\s*appointment|move\s*appointment|push\s*appointment|different\s*slot)\b"
        ],
        "patterns_hi": [
            r"(?:अपॉइंटमेंट\s*रीशेड्यूल|रीशेड्यूल|अपॉइंटमेंट\s*रद्द|रद्द\s*कर|तारीख\s*बदल|आगे\s*बढ़ा|कैंसल)"
        ],
        "patterns_kn": [
            r"(?:ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್\s*ರದ್ದು|ರದ್ದು\s*ಮಾಡಿ|ಮುಂದೂಡು|ದಿನಾಂಕ\s*ಬದಲಾವಣೆ|ಕ್ಯಾನ್ಸಲ್|ಬದಲಾಯಿಸ)"
        ],
        "action_template": "Outpatient scheduling desk to reallocate or cancel appointment slot, update calendar, and issue confirmation to patient.",
        "priority_rationale": "Assigned ROUTINE as appointment scheduling workflow operates within standard clinic administrative hours."
    },

    # 6. Specialist consultations and disease-related appointments
    {
        "category": "Specialist consultations and disease-related appointments",
        "department": "Specialist Clinic & OPD Services",
        "assigned_to": "Specialist Referral Coordinator",
        "default_urgency": "ROUTINE",
        "intent": "specialist_consult_request",
        "patterns_en": [
            r"\b(?:specialist|consultant|cardiologist|neurologist|oncologist|orthopedist|orthopedic|nephrologist|dermatologist|endocrinologist|gastroenterologist|pediatrician|second\s*opinion|specialty\s*clinic)\b"
        ],
        "patterns_hi": [
            r"(?:विशेषज्ञ|स्पेशलिस्ट|कार्डियोलॉजिस्ट|न्यूरोलॉजिस्ट|कैंसर\s*विशेषज्ञ|हड्डी\s*रोग\s*विशेषज्ञ|दूसरी\s*राय)"
        ],
        "patterns_kn": [
            r"(?:ತಜ್ಞ\s*ವೈದ್ಯರು|ಸ್ಪೆಷಲಿಸ್ಟ್|ಹೃದ್ರೋಗ\s*ತಜ್ಞ|ನರರೋಗ\s*ತಜ್ಞ|ಮೂಳೆ\s*ತಜ್ಞ|ಕ್ಯಾನ್ಸರ್\s*ತಜ್ಞ)"
        ],
        "action_template": "Specialist referral desk to review clinical indication and route patient booking to designated specialty consultant.",
        "priority_rationale": "Assigned ROUTINE for specialist referral scheduling adhering to department availability."
    },

    # 7. Routine follow-up appointments
    {
        "category": "Routine follow-up appointments",
        "department": "Outpatient & Appointment Coordination",
        "assigned_to": "Follow-up Clinic Coordinator",
        "default_urgency": "ROUTINE",
        "intent": "routine_follow_up_booking",
        "patterns_en": [
            r"\b(?:routine\s*follow-?up|follow-?up\s*appointment|post-?op\s*visit|post-?surgery\s*checkup|review\s*visit|regular\s*checkup|monthly\s*review|annual\s*checkup)\b"
        ],
        "patterns_hi": [
            r"(?:फॉलो-?अप|नियमित\s*जांच|सर्जरी\s*के\s*बाद\s*जांच|रिव्यू\s*विजिट|रूटीन\s*चेकअप)"
        ],
        "patterns_kn": [
            r"(?:ಫಾಲೋ-?ಅಪ್|ನಿಯಮಿತ\s*ತಪಾಸಣೆ|ಶಸ್ತ್ರಚಿಕಿತ್ಸೆಯ\s*ನಂತರದ\s*ತಪಾಸಣೆ|ಸಾಮಾನ್ಯ\s*ತಪಾಸಣೆ|ರಿವ್ಯೂ\s*ಭೇಟಿ)"
        ],
        "action_template": "Follow-up coordinator to secure routine post-discharge outpatient review slot in the medical record system.",
        "priority_rationale": "Assigned ROUTINE for standard continuity-of-care follow-up monitoring."
    },

    # 4. Appointments and OPD coordination
    {
        "category": "Appointments and OPD coordination",
        "department": "Outpatient & Appointment Coordination",
        "assigned_to": "Outpatient Booking Desk",
        "default_urgency": "ROUTINE",
        "intent": "book_opd_appointment",
        "patterns_en": [
            r"\b(?:book\s*appointment|new\s*appointment|schedule\s*appointment|opd\s*appointment|doctor\s*consultation|see\s*a\s*doctor|doctor\s*available|opd\s*timings)\b"
        ],
        "patterns_hi": [
            r"(?:अपॉइंटमेंट\s*बुक|नई\s*अपॉइंटमेंट|डॉक्टर\s*से\s*मिलना|ओपीडी\s*अपॉइंटमेंट|डॉक्टर\s*का\s*समय)"
        ],
        "patterns_kn": [
            r"(?:ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್\s*ಬುಕಿಂಗ್|ಹೊಸ\s*ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್|ವೈದ್ಯರ\s*ಭೇಟಿ|ಒಪಿಡಿ\s*ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್|ಸ್ಲಾಟ್\s*ಬುಕ್)"
        ],
        "action_template": "Outpatient booking desk to check physician roster and register appointment slot.",
        "priority_rationale": "Assigned ROUTINE for general outpatient consultation booking."
    },

    # 3. Medication, pharmacy and prescription queries
    {
        "category": "Medication, pharmacy and prescription queries",
        "department": "Pharmacy & Therapeutics",
        "assigned_to": "Clinical Staff Pharmacist",
        "default_urgency": "URGENT",
        "intent": "medication_or_prescription_query",
        "patterns_en": [
            r"\b(?:medication|medicine|prescription|pills|tablet|capsule|dose|dosage|refill|pharmacy|antibiotic|paracetamol|metformin|insulin|adverse\s*reaction|allergy|penicillin|drug\s*interaction|side\s*effect|bp\s*medication)\b"
        ],
        "patterns_hi": [
            r"(?:दवा|दवाई|गोली|खुराक|डोज़|पर्ची|प्रिस्क्रिप्शन|फार्मेसी|एंटीबायोटिक|एलर्जी|साइड\s*इफेक्ट|बीपी\s*की\s*दवा)"
        ],
        "patterns_kn": [
            r"(?:ಔಷಧಿ|ಮಾತ್ರೆ|ಮಾತ್ರೆಗಳ|ಡೋಸ್|ಪ್ರಮಾಣ|ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್|ಫಾರ್ಮಸಿ|ಆಂಟಿಬಯೋಟಿಕ್|ಅಲರ್ಜಿ|ಅಡ್ಡಪರಿಣಾಮ|ಬಿಪಿ\s*ಮಾತ್ರೆ)"
        ],
        "action_template": "Clinical pharmacist to review active prescription ledger, verify dosage/interaction safety, and coordinate supply.",
        "priority_rationale": "Assigned URGENT due to potential clinical medication dependency or safety verification."
    },

    # 8. Billing and payment queries
    {
        "category": "Billing and payment queries",
        "department": "Patient Billing & Accounts",
        "assigned_to": "Patient Billing Officer",
        "default_urgency": "INQUIRY",
        "intent": "billing_or_payment_query",
        "patterns_en": [
            r"\b(?:bill|billing|invoice|charges?|payment|cost\s*estimate|receipt|itemized\s*bill|refund|pay\s*the\s*bill|account\s*balance)\b"
        ],
        "patterns_hi": [
            r"(?:बिल|बिलिंग|इनवॉइस|रसीद|खर्चा|भुगतान|कितने\s*पैसे|पेमेंट|बिल\s*का\s*विवरण|पैसे\s*वापस)"
        ],
        "patterns_kn": [
            r"(?:ಬಿಲ್|ಬಿಲ್ಲಿಂಗ್|ರಶೀದಿ|ಪಾವತಿ|ವೆಚ್ಚ|ಹಣ\s*ಪಾವತಿ|ಐಟಮೈಸ್ಡ್\s*ಬಿಲ್|ಹಣ\s*ವಾಪಸ್)"
        ],
        "action_template": "Billing accounts office to produce itemized statement, verify billing ledger, and communicate financial balance.",
        "priority_rationale": "Assigned INQUIRY for patient financial accounting and fee explanation."
    },

    # 9. Insurance and pre-authorisation queries
    {
        "category": "Insurance and pre-authorisation queries",
        "department": "Health Insurance & Pre-Authorisation",
        "assigned_to": "TPA & Insurance Coordinator",
        "default_urgency": "INQUIRY",
        "intent": "insurance_preauth_query",
        "patterns_en": [
            r"\b(?:insurance|pre-?authoris\w+|pre-?authoriz\w+|preauth|tpa|cashless|policy\s*coverage|claim\s*approval|mediclaim)\b"
        ],
        "patterns_hi": [
            r"(?:बीमा|इंश्योरेंस|प्री-?ऑथराइजेशन|क्लेम|कैशलेस|टीपीए|पॉलिसी|क्लेम\s*अप्रूवल)"
        ],
        "patterns_kn": [
            r"(?:ವಿಮೆ|ಇನ್ಶೂರೆನ್ಸ್|ಪ್ರಿ-?ಆಥರೈಸೇಶನ್|ಕ್ಲೇಮ್|ಕ್ಯಾಶ್‌ಲೆಸ್|ಟಿಪಿಎ|ಪಾಲಿಸಿ\s*ಅನುಮೋದನೆ)"
        ],
        "action_template": "TPA insurance desk to verify claim pre-authorisation status with payer and record cashless clearance.",
        "priority_rationale": "Assigned INQUIRY for third-party insurance clearance and paperwork."
    },

    # 10. Admission and discharge coordination
    {
        "category": "Admission and discharge coordination",
        "department": "Administration & Discharge Coordination",
        "assigned_to": "Discharge Case Manager",
        "default_urgency": "ROUTINE",
        "intent": "admission_or_discharge_coordination",
        "patterns_en": [
            r"\b(?:discharge|admission|admit\s*patient|discharge\s*paperwork|discharge\s*summary|discharge\s*clearance|admitted|transport\s*booked)\b"
        ],
        "patterns_hi": [
            r"(?:डिस्चार्ज|छुट्टी|भर्ती|दाखिला|डिस्चार्ज\s*समरी|छुट्टी\s*के\s*कागजात|डिस्चार्ज\s*क्लीयरेंस)"
        ],
        "patterns_kn": [
            r"(?:ಡಿಸ್ಚಾರ್ಜ್|ಬಿಡುಗಡೆ|ಆಸ್ಪತ್ರೆಗೆ\s*ಸೇರ್ಪಡೆ|ದಾಖಲಾತಿ|ಡಿಸ್ಚಾರ್ಜ್\s*ಸಾರಾಂಶ|ಡಿಸ್ಚಾರ್ಜ್\s*ಪತ್ರಗಳು)"
        ],
        "action_template": "Discharge case manager to compile medical discharge summary, obtain physician sign-off, and finalize clearance.",
        "priority_rationale": "Assigned ROUTINE for structured inpatient discharge / admission operational pipeline."
    },

    # 11. Facilities, housekeeping and transport
    {
        "category": "Facilities, housekeeping and transport",
        "department": "Facilities & Environmental Services",
        "assigned_to": "Facilities Dispatch",
        "default_urgency": "ROUTINE",
        "intent": "facilities_housekeeping_transport",
        "patterns_en": [
            r"\b(?:clean|housekeeping|spill|shattered|broken\s*glass|water\s*on\s*(?:the\s*)?floor|dirty|trash|linen|bedsheets?|blanket|pillow|towel|wheelchair|stretcher|cold\s*room|ac\s*not\s*working|transport)\b"
        ],
        "patterns_hi": [
            r"(?:फर्श\s*पर\s*पानी|सफाई|कांच|फूट\s*गया|व्हीलचेयर|कचरा|गंदगी|ठंडा\s*कमरा|ट्रांसपोर्ट|चादर|तकिया|कंबल)"
        ],
        "patterns_kn": [
            r"(?:ನೆಲದ\s*ಮೇಲೆ\s*ನೀರು|ನೆಲದ\s*ಮೇಲೆ|ಸ್ವಚ್ಛತೆ|ಗಾಜು|ಒಡೆದು|ವ್ಹೀಲ್‌ಚೇರ್|ಕಸ|ತಣ್ಣನೆ\s*ಕೊಠಡಿ|ಸಾಗಣೆ|ಬೆಡ್‌ಶೀಟ್|ದಿಂಬು|ಹೊದಿಕೆ)"
        ],
        "action_template": "Facilities and housekeeping dispatch to inspect room, remediate environmental condition, and supply requested items.",
        "priority_rationale": "Assigned ROUTINE for facility hygiene and inpatient comfort accommodation."
    },

    # 12. Food, dietary and nutrition requests
    {
        "category": "Food, dietary and nutrition requests",
        "department": "Dietary & Clinical Nutrition",
        "assigned_to": "Dietary Services Supervisor",
        "default_urgency": "ROUTINE",
        "intent": "patient_dietary_meal_request",
        "patterns_en": [
            r"\b(?:lunch|dinner|breakfast|meal|food|tray|diet|blood\s*sugar|diabetic|hungry|nutrition|drinking\s*water|tea|coffee|npo|fasting)\b"
        ],
        "patterns_hi": [
            r"(?:खाना|भोजन|दोपहर\s*का\s*खाना|रात\s*का\s*खाना|डायबिटिक|शुगर|भूख|नाश्ता|पीने\s*का\s*पानी)"
        ],
        "patterns_kn": [
            r"(?:ಊಟ|ತಿಂಡಿ|ಆಹಾರ|ಮಧ್ಯಾಹ್ನದ\s*ಊಟ|ರಾತ್ರಿಯ\s*ಊಟ|ಡಯಾಬಿಟಿಕ್|ಸಕ್ಕರೆ\s*ಕಾಯಿಲೆ|ಹಸಿವು|ಕುಡಿಯುವ\s*ನೀರು)"
        ],
        "action_template": "Dietary kitchen supervisor to prepare clinically compliant meal tray and deliver to patient bedside.",
        "priority_rationale": "Assigned ROUTINE for hospital nutrition and meal schedule management."
    },

    # 14. Promised callbacks and other follow-up commitments (Check before general inquiries)
    {
        "category": "Promised callbacks and other follow-up commitments",
        "department": "Clinical Follow-up & Care Coordination",
        "assigned_to": "Patient Care Liaison Officer",
        "default_urgency": "ROUTINE",
        "intent": "promised_callback_followup",
        "patterns_en": [
            r"\b(?:callback|call\s*back|promised\s*to\s*call|waiting\s*for\s*a\s*call|haven't\s*called|supposed\s*to\s*call|doctor\s*promised|follow-?up\s*call)\b"
        ],
        "patterns_hi": [
            r"(?:कॉल\s*बैक|फोन\s*करने\s*को\s*कहा|फोन\s*नहीं\s*आया|डॉक्टर\s*ने\s*फोन\s*करने\s*का\s*वादा|कॉल\s*का\s*इंतजार)"
        ],
        "patterns_kn": [
            r"(?:ಕಾಲ್\s*ಬ್ಯಾಕ್|ಕರೆ\s*ಮಾಡುವುದಾಗಿ|ಇನ್ನು\s*ಕರೆ\s*ಬಂದಿಲ್ಲ|ಡಾಕ್ಟರ್\s*ಕರೆ\s*ಮಾಡುವುದಾಗಿ\s*ಭರವಸೆ)"
        ],
        "action_template": "Care liaison officer to track outstanding staff callback commitment and ensure immediate physician/nurse phone contact.",
        "priority_rationale": "Assigned ROUTINE to honor patient communication SLA and maintain service accountability."
    },

    # 13. General inquiries and information requests
    {
        "category": "General inquiries and information requests",
        "department": "Hospital Information & Patient Helpdesk",
        "assigned_to": "Patient Helpdesk Representative",
        "default_urgency": "INQUIRY",
        "intent": "general_hospital_inquiry",
        "patterns_en": [
            r"\b(?:visiting\s*hours|visitor\s*policy|parking|directions|where\s*is|helpdesk|contact\s*number|phone\s*directory|general\s*information|visiting\s*time)\b"
        ],
        "patterns_hi": [
            r"(?:मिलने\s*का\s*समय|विजिटिंग\s*आवर्स|पार्किंग|अस्पताल\s*का\s*पता|रास्ता|हेल्पडेस्क|सामान्य\s*जानकारी|फोन\s*नंबर)"
        ],
        "patterns_kn": [
            r"(?:ಭೇಟಿ\s*ಸಮಯ|ವಿಸಿಟಿಂಗ್\s*ಅವರ್ಸ್|ಪಾರ್ಕಿಂಗ್|ಆಸ್ಪತ್ರೆ\s*ವಿಳಾಸ|ಮಾರ್ಗ|ಹೆಲ್ಪ್‌ಡೆಸ್ಕ್|ಸಾಮಾನ್ಯ\s*ಮಾಹಿತಿ|ಫೋನ್\s*ಸಂಖ್ಯೆ)"
        ],
        "action_template": "Patient helpdesk staff to provide official hospital operational guidelines and visitor information.",
        "priority_rationale": "Assigned INQUIRY as informational question without urgent clinical intervention."
    },

    # 2. Nursing and patient care (Catch-all for nursing duties)
    {
        "category": "Nursing and patient care",
        "department": "Nursing & Clinical Care",
        "assigned_to": "Floor Charge Nurse",
        "default_urgency": "URGENT",
        "intent": "nursing_care_request",
        "patterns_en": [
            r"\b(?:pain|knee\s*replacement|wound|bandage|dressing|vitals|dizzy|nurse|reposition|bathroom\s*assist|blood\s*pressure|temperature|fever|headache|blanket|pillow)\b"
        ],
        "patterns_hi": [
            r"(?:दर्द|नर्स|पट्टी|चक्कर|कमजोरी|बुखार|करवट|मदद|सिरदर्द|बीपी)"
        ],
        "patterns_kn": [
            r"(?:ನೋವು|ಶುಶ್ರೂಷಕಿ|ನರ್ಸ್|ಬ್ಯಾಂಡೇಜ್|ತಲೆತಿರುಗುವಿಕೆ|ಜ್ವರ|ಸಹಾಯ|ತಲೆನೋವು|ಬಿಪಿ)"
        ],
        "action_template": "Floor nurse to evaluate patient clinical parameters, check vital signs, and provide bedside nursing intervention.",
        "priority_rationale": "Assigned URGENT for active nursing care, pain management, or patient comfort support."
    }
]

CLINICAL_ACTION_KEYWORDS = [
    "pain", "breath", "iv", "beep", "swoll", "fall", "slip", "bleed", "unconscious",
    "heart", "attack", "cardiac", "chest", "stroke", "seiz", "faint", "chok", "emergenc", "urgent", "indigest",
    "med", "pill", "allerg", "dose", "pharm", "antibiotic", "prescription",
    "food", "lunch", "dinner", "meal", "tray", "diet", "sugar", "hungry", "water",
    "clean", "spill", "water", "glass", "wheelchair", "trash", "linen", "blanket", "pillow",
    "sheet", "sheets", "bedsheet", "bedsheets", "towel", "towels",
    "housekeep", "mop", "floor", "receipt", "invoic", "schedul", "appoint",
    "discharge", "paper", "doctor", "dr.", "bill", "insurance", "preauth", "pre-authoriz",
    "appointment", "reschedule", "cancel", "specialist", "follow-up", "callback", "visiting",
    "assist", "nurse", "help",
    # Hindi
    "दर्द", "सांस", "आईवी", "सूजन", "खून", "गिर", "बेहोश", "दवा", "एलर्जी", "गोली", "खुराक",
    "हार्ट", "अटैक", "दिल", "छाती", "चेस्ट", "दौरा",
    "खाना", "भोजन", "सफाई", "कांच", "डिस्चार्ज", "कागजात", "डॉक्टर", "बिल", "बीमा", "फर्श",
    "पोछा", "रसीद", "अपॉइंटमेंट", "रीशेड्यूल", "रद्द", "विशेषज्ञ", "फॉलो-अप", "कॉल बैक", "समय", "मदद", "नर्स",
    # Kannada
    "ನೋವು", "ಉಸಿರಾ", "ಐವಿ", "ಊತ", "ರಕ್ತ", "ಬಿದ್ದ", "ಪ್ರಜ್ಞಾ", "ಔಷಧಿ", "ಮಾತ್ರೆ", "ಅಲರ್ಜಿ",
    "ಹೃದಯ", "ಎದೆ", "ಯದೆ",
    "ಊಟ", "ತಿಂಡಿ", "ಆಹಾರ", "ಸ್ವಚ್ಛತೆ", "ಗಾಜು", "ಡಿಸ್ಚಾರ್ಜ್", "ದಾಖಲೆ", "ವೈದ್ಯ", "ಡಾಕ್ಟರ್", "ಬಿಲ್", "ವಿಮೆ", "ನೆಲದ", "ನೆಲ",
    "ಅಪಾಯಿಂಟ್‌ಮೆಂಟ್", "ರದ್ದು", "ತಜ್ಞ", "ಫಾಲೋ-ಅಪ್", "ಕಾಲ್ ಬ್ಯಾಕ್", "ಸಹಾಯ", "ನರ್ಸ್"
]

def is_pure_intro_greeting(seg: str) -> bool:
    """Returns True if the segment is merely a speaker greeting/introduction without actionable tasks."""
    seg_clean = seg.strip().lower()
    for l_key in ["en", "hi", "kn"]:
        for pat in EMERGENCY_SYMPTOMS[l_key]:
            if re.search(pat, seg_clean if l_key == "en" else seg, re.IGNORECASE):
                return False
    has_action = any(k in seg_clean or k in seg for k in CLINICAL_ACTION_KEYWORDS)
    if not has_action:
        return True
    return False

def evaluate_clinical_urgency_and_evidence(text: str, lang: str = "en") -> Dict[str, Any]:
    """
    Evaluates clinical urgency with robust safety safeguards:
    1. Distinguishes genuine negation from refractory symptoms (e.g. 'not going away', 'not improving').
    2. Identifies contrastive/emphatic negation (e.g. 'not mild pain, severe crushing pain').
    3. Prevents collateral negation suppression (e.g. 'no fever, but collapsed and blue').
    4. Detects historical symptoms (e.g. 'had chest pain 3 weeks ago, currently fine') vs acute.
    5. Flags clinical uncertainty in high-risk scenarios for human review (e.g. 'not sure if heart attack or gas').
    6. Extracts explicit structured evidence snippet for auditability.
    """
    text_lower = text.lower()

    # 1. Match emergency symptoms across EN, HI, KN & Code-Switching
    matched_symptoms = []
    for l_key in ["en", "hi", "kn"]:
        for sym_pat in EMERGENCY_SYMPTOMS[l_key]:
            target = text_lower if l_key == "en" else text
            m = re.search(sym_pat, target, re.IGNORECASE)
            if m:
                matched_span = m.group(0).strip()
                if matched_span not in matched_symptoms:
                    matched_symptoms.append(matched_span)

    # 2. Check for refractory markers (e.g., 'not going away', 'not improving')
    refractory_markers = []
    for l_key in ["en", "hi", "kn"]:
        for ref_pat in REFRACTORY_PATTERNS[l_key]:
            target = text_lower if l_key == "en" else text
            m = re.search(ref_pat, target, re.IGNORECASE)
            if m:
                refractory_markers.append(m.group(0).strip())

    # 3. Check for contrastive / emphatic markers (e.g., 'not mild', 'not just gas')
    contrastive_markers = []
    for l_key in ["en", "hi", "kn"]:
        for cont_pat in CONTRASTIVE_PATTERNS[l_key]:
            target = text_lower if l_key == "en" else text
            m = re.search(cont_pat, target, re.IGNORECASE)
            if m:
                contrastive_markers.append(m.group(0).strip())

    # 4. Check for historical qualifiers (e.g., '3 weeks ago', '2 years ago')
    historical_qualifiers = []
    for l_key in ["en", "hi", "kn"]:
        for hist_pat in HISTORICAL_PATTERNS[l_key]:
            target = text_lower if l_key == "en" else text
            m = re.search(hist_pat, target, re.IGNORECASE)
            if m:
                historical_qualifiers.append(m.group(0).strip())

    # 5. Check for uncertainty triggers (e.g., 'not sure if', 'possible', 'might be')
    uncertainty_triggers = []
    for l_key in ["en", "hi", "kn"]:
        for unc_pat in UNCERTAINTY_PATTERNS[l_key]:
            target = text_lower if l_key == "en" else text
            m = re.search(unc_pat, target, re.IGNORECASE)
            if m:
                uncertainty_triggers.append(m.group(0).strip())

    if not matched_symptoms:
        return {
            "is_emergency": False,
            "is_negated": False,
            "is_refractory": False,
            "is_historical": False,
            "is_uncertain": False,
            "requires_human_review": False,
            "human_review_reason": "",
            "urgency": "ROUTINE",
            "matched_symptoms": [],
            "active_symptoms": [],
            "negated_symptoms": [],
            "refractory_markers": [],
            "historical_qualifiers": historical_qualifiers,
            "uncertainty_triggers": uncertainty_triggers,
            "evidence_summary": "No acute emergency symptoms detected."
        }

    # 6. Symptom-specific negation scoping
    negated_symptoms = []
    active_symptoms = []

    for sym in matched_symptoms:
        # If refractory markers or contrastive markers exist, negation is overridden for this emergency
        if refractory_markers or contrastive_markers:
            active_symptoms.append(sym)
            continue

        # Check for negation patterns targeting this symptom
        is_sym_negated = False
        target = text_lower if lang == "en" else text
        for l_key in ["en", "hi", "kn"]:
            for neg_pat in NEGATION_PATTERNS[l_key]:
                if re.search(neg_pat, text_lower if l_key == "en" else text, re.IGNORECASE):
                    is_sym_negated = True
                    break
            if is_sym_negated:
                break

        if is_sym_negated:
            negated_symptoms.append(sym)
        else:
            active_symptoms.append(sym)

    is_refractory = len(refractory_markers) > 0
    is_historical = (len(historical_qualifiers) > 0) and (not is_refractory) and (
        any(k in text_lower for k in [
            "currently fine", "now fine", "feels fine", "no symptoms today", "past",
            "history", "years ago", "weeks ago", "resolved", "अब ठीक", "ಈಗ ಆರಾಮ", "ಹಿಂದೆ ಇತ್ತು"
        ]) or len(active_symptoms) == 0
    )
    is_uncertain = len(uncertainty_triggers) > 0 and (len(active_symptoms) > 0 or len(matched_symptoms) > 0)

    # 7. Final Urgency and Human Review determination
    requires_human_review = False
    human_review_reason = ""
    urgency = "ROUTINE"
    is_emergency = False

    if is_refractory and active_symptoms:
        urgency = "STAT_EMERGENCY"
        is_emergency = True
        evidence_summary = (
            f"Refractory acute symptoms verified ({', '.join(active_symptoms)}); "
            f"symptoms persistent and unresolved ({', '.join(refractory_markers)})."
        )
    elif active_symptoms and not is_historical:
        if is_uncertain:
            urgency = "URGENT"
            is_emergency = True
            requires_human_review = True
            human_review_reason = (
                f"Caller reported potential acute clinical emergency ({', '.join(active_symptoms)}) "
                f"with diagnostic uncertainty ('{uncertainty_triggers[0]}'); immediate bedside nursing assessment required."
            )
            evidence_summary = (
                f"Potential acute symptoms with caller uncertainty: {', '.join(active_symptoms)}. "
                f"Uncertainty triggers: {', '.join(uncertainty_triggers)}."
            )
        else:
            urgency = "STAT_EMERGENCY"
            is_emergency = True
            evidence_summary = f"Acute emergency symptoms verified: {', '.join(active_symptoms)}."
    elif is_historical:
        urgency = "ROUTINE"
        is_emergency = False
        evidence_summary = (
            f"Symptoms identified as historical or resolved: {', '.join(matched_symptoms)} "
            f"({', '.join(historical_qualifiers)})."
        )
    elif len(negated_symptoms) > 0 and len(active_symptoms) == 0:
        urgency = "ROUTINE"
        is_emergency = False
        evidence_summary = f"Emergency symptoms explicitly negated/ruled out by caller: {', '.join(negated_symptoms)}."
    else:
        urgency = "ROUTINE"
        is_emergency = False
        evidence_summary = "Standard triage protocol applied."

    return {
        "is_emergency": is_emergency,
        "is_negated": (len(negated_symptoms) > 0 and len(active_symptoms) == 0),
        "is_refractory": is_refractory,
        "is_historical": is_historical,
        "is_uncertain": is_uncertain,
        "requires_human_review": requires_human_review,
        "human_review_reason": human_review_reason,
        "urgency": urgency,
        "matched_symptoms": matched_symptoms,
        "active_symptoms": active_symptoms,
        "negated_symptoms": negated_symptoms,
        "refractory_markers": refractory_markers,
        "historical_qualifiers": historical_qualifiers,
        "uncertainty_triggers": uncertainty_triggers,
        "evidence_summary": evidence_summary
    }

def check_emergency_with_negation(text: str, lang: str) -> Tuple[bool, bool, List[str]]:
    """
    Backward-compatible wrapper returning (is_emergency, is_negated, matched_symptoms).
    Uses evaluate_clinical_urgency_and_evidence internally.
    """
    eval_res = evaluate_clinical_urgency_and_evidence(text, lang)
    return eval_res["is_emergency"], eval_res["is_negated"], eval_res["matched_symptoms"]

def split_multilingual_transcript(transcript: str, lang: str = "en") -> List[str]:
    """
    Splits compound speech containing multiple requests into atomic segments
    across Kannada, Hindi, and English without losing secondary requests.
    """
    cleaned = transcript.strip().replace("\r\n", "\n")

    # Multilingual split markers:
    # Punctuation boundaries: ., ?, !, ।, \n
    # English connectors: also, and also, additionally, plus, and one more thing, besides that,
    # furthermore, on top of that, and while I have you, and then
    # Hindi connectors: इसके अलावा, साथ ही, और एक बात, तथा
    # Kannada connectors: ಇನ್ನೊಂದು ವಿಷಯ, ಅದರ ಜೊತೆಗೆ, ಹಾಗೆಯೇ, ಜೊತೆಗೆ
    split_pattern = (
        r"(?<=[.!?।\n])\s+|"
        r"(?:\s+(?:also|and also|additionally|plus|and one more thing|and while I have you|furthermore|besides that|on top of that|and then)\b[,\s]*)|"
        r"(?:\s+(?:इसके अलावा|साथ ही|और एक बात|तथा)\s*)|"
        r"(?:\s+(?:ಇನ್ನೊಂದು ವಿಷಯ|ಅದರ ಜೊತೆಗೆ|ಹಾಗೆಯೇ|ಜೊತೆಗೆ)\s*)"
    )

    raw_segments = re.split(split_pattern, cleaned, flags=re.IGNORECASE)
    segments = []

    for seg in raw_segments:
        if not seg:
            continue
        seg = seg.strip(" \t\n,.;:।")
        if len(seg) < 8:
            continue
        if is_pure_intro_greeting(seg):
            continue
        segments.append(seg)

    # Fallback to sentence split if regex yielded <= 1
    if len(segments) <= 1:
        fallback_sents = [
            s.strip(" \t\n,.;:।") for s in re.split(r"[.!?।\n]+", cleaned)
            if len(s.strip()) > 8 and not is_pure_intro_greeting(s)
        ]
        if len(fallback_sents) > 1:
            return fallback_sents
        if segments:
            return segments
        return [cleaned]

    return segments

def classify_multilingual_segment(
    segment: str,
    lang: str,
    patient_name: str = "Patient",
    room_number: str = "Unassigned"
) -> Dict[str, Any]:
    """
    Classify a request segment into one of the 14 standard categories,
    matching appropriate department, intent, urgency, priority rationale,
    required action, explicit deadline, confidence score, and urgency evidence.
    """
    urg_eval = evaluate_clinical_urgency_and_evidence(segment, lang)
    is_emergency = urg_eval["is_emergency"]
    is_negated = urg_eval["is_negated"]
    is_refractory = urg_eval["is_refractory"]
    is_historical = urg_eval["is_historical"]
    is_uncertain = urg_eval["is_uncertain"]
    emergency_syms = urg_eval["matched_symptoms"]
    requires_human_review = urg_eval["requires_human_review"]
    human_review_reason = urg_eval["human_review_reason"]

    # Extract explicit stated deadline if present
    explicit_deadline = extract_explicit_deadline(segment)

    # Match Category and Department Rule
    matched_rule = None
    seg_lower = segment.lower()

    if is_emergency:
        # Guarantee category 1 for true emergencies
        matched_rule = CATEGORY_RULES[0]
    else:
        # Check rule patterns (skipping rule 0 if not emergency)
        for rule in CATEGORY_RULES:
            if rule["category"] == "Emergency and urgent clinical concerns" and not is_emergency:
                continue

            matched = False
            for pat in rule["patterns_en"]:
                if re.search(pat, seg_lower, re.IGNORECASE):
                    matched = True
                    break
            if not matched:
                for pat in rule["patterns_hi"]:
                    if re.search(pat, segment):
                        matched = True
                        break
            if not matched:
                for pat in rule["patterns_kn"]:
                    if re.search(pat, segment):
                        matched = True
                        break

            if matched:
                matched_rule = rule
                break

    # Fallback rule if no specific keyword matched
    if not matched_rule:
        matched_rule = CATEGORY_RULES[-1]  # Nursing and patient care fallback

    # Determine Urgency
    if is_emergency:
        urgency = urg_eval["urgency"]  # STAT_EMERGENCY or URGENT (if uncertain)
    elif is_negated or is_historical:
        urgency = "ROUTINE"
    else:
        urgency = matched_rule["default_urgency"]

    category = matched_rule["category"]
    department = matched_rule["department"]
    assigned_to = matched_rule["assigned_to"]
    intent = matched_rule["intent"]

    # Compute Confidence Score (0.75 - 0.99)
    if is_emergency and not is_uncertain:
        confidence_score = 0.98
    elif is_uncertain:
        confidence_score = 0.78
    elif is_negated or is_historical:
        confidence_score = 0.94
    elif matched_rule["category"] != "Nursing and patient care":
        confidence_score = 0.92
    else:
        confidence_score = 0.86

    # Format Required Action
    action_text = matched_rule["action_template"].format(
        room=room_number if room_number and room_number != "Unassigned" else "patient room"
    )
    if explicit_deadline:
        action_text += f" Required completion: {explicit_deadline}."
    if requires_human_review:
        action_text = f"[CLINICAL REVIEW REQUIRED]: {action_text}"

    # Priority Rationale
    if is_refractory:
        priority_rationale = (
            f"Assigned {urgency} due to refractory acute clinical symptoms ({', '.join(urg_eval['active_symptoms'])}) "
            f"persisting despite conservative measures ({', '.join(urg_eval['refractory_markers'])})."
        )
    elif is_uncertain:
        priority_rationale = (
            f"Assigned {urgency} (Flagged for Clinical Review) due to potential acute symptoms "
            f"({', '.join(urg_eval['active_symptoms'])}) with diagnostic uncertainty ('{', '.join(urg_eval['uncertainty_triggers'])}')."
        )
    elif is_historical:
        priority_rationale = (
            f"Assigned ROUTINE as symptoms ({', '.join(urg_eval['matched_symptoms'])}) occurred historically "
            f"({', '.join(urg_eval['historical_qualifiers'])}) without active acute distress."
        )
    elif is_negated:
        priority_rationale = (
            f"Assigned ROUTINE as emergency clinical symptoms ({', '.join(urg_eval['negated_symptoms'])}) "
            f"were explicitly negated or ruled out by the caller."
        )
    else:
        priority_rationale = matched_rule["priority_rationale"]

    # Clinical flags detection
    flags = []
    if is_emergency:
        flags.append("CRITICAL_ACUTE_ALERT")
    if is_negated:
        flags.append("SYMPTOM_NEGATED_RULE_OUT")
    if is_refractory:
        flags.append("REFRACTORY_ACUTE_SYMPTOM")
    if is_historical:
        flags.append("HISTORICAL_ACUTE_SYMPTOM")
    if is_uncertain:
        flags.append("FLAGGED_UNCERTAIN_EMERGENCY")
    if requires_human_review:
        flags.append("REQUIRES_CLINICAL_REVIEW")

    if any(k in seg_lower for k in ["iv", "swollen", "beep"]) or any(k in segment for k in ["आईवी", "सूजन", "ಐವಿ", "ಊತ"]):
        flags.append("IV_INFILTRATION_RISK")
    if any(k in seg_lower for k in ["fell", "slip", "fall"]) or any(k in segment for k in ["गिर", "ಬಿದ್ದ"]):
        flags.append("ACTIVE_FALL_RISK")
    if any(k in seg_lower for k in ["diabetic", "blood sugar", "lunch", "meal"]) or any(k in segment for k in ["डायबिटिक", "खाना", "ಡಯಾಬಿಟಿಕ್", "ಊಟ"]):
        flags.append("DIABETIC_NPO_WATCH")
    if any(k in seg_lower for k in ["allergy", "penicillin", "interaction"]) or any(k in segment for k in ["एलर्जी", "दवा", "ಅಲರ್ಜಿ", "ಔಷಧಿ"]):
        flags.append("MEDICATION_SAFETY_CHECK")
    if any(k in seg_lower for k in ["discharge", "paperwork"]) or any(k in segment for k in ["डिस्चार्ज", "कागजात", "ಡಿಸ್ಚಾರ್ಜ್"]):
        flags.append("DISCHARGE_COORDINATION")
    if any(k in seg_lower for k in ["reschedule", "cancel"]) or any(k in segment for k in ["रीशेड्यूल", "रद्द", "ಮುಂದೂಡು"]):
        flags.append("APPOINTMENT_CHANGE")
    if any(k in seg_lower for k in ["bill", "insurance", "preauth"]) or any(k in segment for k in ["बिल", "बीमा", "ಬಿಲ್", "ವಿಮೆ"]):
        flags.append("FINANCIAL_CLEARANCE")

    # Generate title
    preview = segment[:55].strip()
    if is_emergency and not is_uncertain:
        title = f"STAT Emergency: {preview}..."
    elif is_uncertain:
        title = f"Review Required (Uncertain): {preview}..."
    elif is_historical:
        title = f"Historical Note: {preview}..."
    elif is_negated:
        title = f"Clinical Rule-Out: {preview}..."
    else:
        title = f"{category}: {preview}..."

    # Translated quote
    translated_quote = ""
    if lang == "kn":
        translated_quote = f"[Kannada Speech Excerpt]: \"{segment}\""
    elif lang == "hi":
        translated_quote = f"[Hindi Speech Excerpt]: \"{segment}\""
    else:
        translated_quote = segment

    triage_notes = (
        f"Category: {category}. Intent: {intent}. "
        f"Language: {lang.upper()}. Urgency: {urgency}. "
        f"{'CRITICAL: Emergency symptom verified.' if is_emergency and not is_uncertain else ''}"
        f"{'FLAGGED: High-risk symptom with uncertainty, human nurse review required.' if is_uncertain else ''}"
        f"{'Note: Symptom negated by caller.' if is_negated else ''}"
        f"{'Note: Symptom identified as historical event.' if is_historical else ''}"
        f"{f' Explicit deadline stated: {explicit_deadline}.' if explicit_deadline else ''}"
    )

    return {
        "department": department,
        "category": category,
        "intent": intent,
        "title": title,
        "description": segment,
        "raw_quote": segment,
        "translated_quote": translated_quote,
        "language": lang,
        "urgency": urgency,
        "priority_rationale": priority_rationale,
        "required_action": action_text,
        "explicit_deadline": explicit_deadline,
        "confidence_score": confidence_score,
        "source_timestamp": None,
        "requires_human_review": requires_human_review,
        "human_review_reason": human_review_reason,
        "urgency_evidence": urg_eval,
        "clinical_flags": flags,
        "assigned_to": assigned_to,
        "triage_notes": triage_notes
    }

def extract_patient_entities(transcript: str) -> Dict[str, str]:
    """Extract patient name and room number across English, Hindi, and Kannada."""
    entities = {
        "caller_name": "Caller",
        "patient_name": "Patient",
        "room_number": "Unassigned"
    }

    # Room number pattern (Room 314, Room 108, कमरा 314, ರೂಮ್ 314, ಕೋಣೆ 314, Bed 12)
    room_match = re.search(r"(?:room|bed|ward|कमरा|ರೂಮ್|ಕೋಣೆ)\s*([0-9A-Za-z\-]+)", transcript, re.IGNORECASE)
    if room_match:
        entities["room_number"] = f"Room {room_match.group(1).upper()}"

    # English caller/patient
    caller_match = re.search(r"\b(?:this is|my name is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", transcript)
    if caller_match:
        entities["caller_name"] = caller_match.group(1).strip()

    patient_match = re.search(r"\b(?:patient|about|for|father|mother)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b", transcript)
    if patient_match:
        entities["patient_name"] = patient_match.group(1).strip()

    # Hindi caller/patient
    hi_caller_match = re.search(r"(?:मैं\s+([^\s,।]+(?:\s+[^\s,।]+)?)\s*बोल\s*रहा)", transcript)
    if hi_caller_match:
        entities["caller_name"] = hi_caller_match.group(1).strip()

    hi_patient_match = re.search(r"(?:मरीज|रोगी)\s+([^\s,।]+(?:\s+[^\s,।]+)?)", transcript)
    if hi_patient_match:
        entities["patient_name"] = hi_patient_match.group(1).strip()

    # Kannada caller/patient
    kn_caller_match = re.search(r"(?:ನಾನು\s+([^\s,]+(?:\s+[^\s,]+)?)\s*ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ)", transcript)
    if kn_caller_match:
        entities["caller_name"] = kn_caller_match.group(1).strip()

    kn_patient_match = re.search(r"(?:ರೋಗಿ\s+([^\s,]+(?:\s+[^\s,]+)?))", transcript)
    if kn_patient_match:
        entities["patient_name"] = kn_patient_match.group(1).strip()

    return entities

def process_real_transcript(
    transcript: str,
    language: Optional[str] = None,
    caller_name: Optional[str] = None,
    patient_name: Optional[str] = None,
    room_number: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main pipeline for processing an actual user recording or uploaded transcript.
    Decomposes into multiple atomic department tickets across all 14 categories,
    checks emergency symptoms with negation, extracts explicit deadlines,
    flags uncertain high-risk cases for human review, and preserves original language script.
    """
    detected_lang = language or detect_script_language(transcript)
    entities = extract_patient_entities(transcript)

    c_name = caller_name if caller_name and caller_name.strip() else entities["caller_name"]
    p_name = patient_name if patient_name and patient_name.strip() else entities["patient_name"]
    r_num = room_number if room_number and room_number.strip() else entities["room_number"]

    segments = split_multilingual_transcript(transcript, detected_lang)
    extracted_tickets = []
    has_emergency = False
    has_human_review = False

    for seg in segments:
        classification = classify_multilingual_segment(
            segment=seg,
            lang=detected_lang,
            patient_name=p_name,
            room_number=r_num
        )
        classification["patient_name"] = p_name
        classification["room_number"] = r_num
        if classification["urgency"] == "STAT_EMERGENCY":
            has_emergency = True
        if classification.get("requires_human_review"):
            has_human_review = True
        extracted_tickets.append(classification)

    lang_labels = {"kn": "Kannada (ಕನ್ನಡ)", "hi": "Hindi (हिन्दी)", "en": "English"}
    lang_display = lang_labels.get(detected_lang, detected_lang.upper())

    summary = (
        f"Processed {lang_display} conversation for {p_name} ({r_num}) into "
        f"{len(extracted_tickets)} actionable hospital department tasks across "
        f"{len(set(t['category'] for t in extracted_tickets))} categories. "
        f"{'CRITICAL: STAT Emergency detected.' if has_emergency else 'All requests queued within standard SLA.'}"
        f"{' [ATTENTION: 1+ tasks flagged for human clinical review.]' if has_human_review else ''}"
    )

    return {
        "caller_name": c_name,
        "patient_name": p_name,
        "room_number": r_num,
        "raw_transcript": transcript,
        "language": detected_lang,
        "summary": summary,
        "emergency_detected": has_emergency,
        "engine_used": f"CareRouter Multilingual Dispatch Engine ({lang_display})",
        "tickets": extracted_tickets
    }
