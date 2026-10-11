import re
import os
import json
from typing import List, Dict, Any, Tuple, Optional

# Detect language from text characters if not specified
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

# Multilingual Emergency Symptoms and Negation Rules
EMERGENCY_SYMPTOMS = {
    "en": [
        "chest pain", "chest discomfort", "heart attack", "crushing chest", "cardiac arrest",
        "cannot breathe", "shortness of breath", "difficulty breathing", "choking", "gasping",
        "unconscious", "passed out", "fainted", "unresponsive", "having a seizure", "fits", "stroke",
        "bleeding profusely", "heavy bleeding", "fell on the floor", "slipped and fell",
        "swollen and red", "iv machine.*beep", "iv infiltration", "severe pain 8/10", "collapsed"
    ],
    "hi": [
        "सीने में दर्द", "छाती में दर्द", "दिल का दौरा", "हार्ट अटैक", "सीने में जकड़न",
        "सांस नहीं आ रही", "सांस लेने में तकलीफ", "सांस फूलना", "दम घुट रहा",
        "बेहोश", "बेहोशी", "दौरा", "मिर्गी", "स्ट्रोक", "लकवा", "कोई जवाब नहीं",
        "खून बह रहा", "बहुत खून", "फर्श पर गिर", "गिर पड़े", "उठ नहीं पा रहे",
        "हाथ सूज गया", "गंभीर सूजन", "आईवी बीप", "अत्यधिक दर्द"
    ],
    "kn": [
        "ಎದೆ ನೋವು", "ಎದೆಯಲ್ಲಿ ನೋವು", "ಹೃದಯಾಘಾತ", "ಹಾರ್ಟ್ ಅಟ್ಯಾಕ್",
        "ಉಸಿರಾಟದ ತೊಂದರೆ", "ಉಸಿರು ಕಟ್ಟುತ್ತಿದೆ", "ಉಸಿರಾಡಲು ಕಷ್ಟ", "ಉಸಿರು ಸಿಗುತ್ತಿಲ್ಲ",
        "ಪ್ರಜ್ಞಾಹೀನ", "ಮೂರ್ಛೆ", "ಫಿಟ್ಸ್", "ಪಾರ್ಶ್ವವಾಯು", "ಸ್ಟ್ರೋಕ್",
        "ವಿಪರೀತ ರಕ್ತಸ್ರಾವ", "ರಕ್ತ ಬರುತ್ತಿದೆ", "ಕೆಳಗೆ ಬಿದ್ದರು", "ಜಾರಿ ಬಿದ್ದರು", "ಏಳಲು ಆಗುತ್ತಿಲ್ಲ",
        "ಕೈ ಊದಿಕೊಂಡಿದೆ", "ತೀವ್ರ ಊತ", "ಐವಿ ಶಬ್ದ", "ತೀವ್ರ ನೋವು"
    ]
}

NEGATION_PATTERNS = {
    "en": [
        r"\b(?:no|not|denies|denied|without|never|negative for|neither)\s+(?:\w+\s+){0,3}(?:chest pain|pain|shortness of breath|bleeding|fall|swelling)\b",
        r"\b(?:chest pain|pain|bleeding|fall|swelling)\s+(?:is not|has stopped|resolved|ruled out)\b"
    ],
    "hi": [
        r"(?:सीने में दर्द|दर्द|सांस की तकलीफ|खून|सूजन)\s*(?:नहीं है|नहीं हो रहा|बिल्कुल नहीं|रुक गया)",
        r"(?:कोई|बिना किसी)\s*(?:सीने में दर्द|दर्द|तकलीफ|खून)\s*नहीं"
    ],
    "kn": [
        r"(?:ಎದೆ ನೋವು|ನೋವು|ಉಸಿರಾಟದ ತೊಂದರೆ|ರಕ್ತಸ್ರಾವ|ಊತ)\s*(?:ಇಲ್ಲ|ಆಗುತ್ತಿಲ್ಲ|ನಿಂತಿದೆ)",
        r"(?:ಯಾವುದೇ|ಯಾವ)\s*(?:ಎದೆ ನೋವು|ನೋವು|ತೊಂದರೆ)\s*ಇಲ್ಲ"
    ]
}

DEPARTMENT_PATTERNS = [
    {
        "department": "Rapid Response & Critical Nursing",
        "patterns_en": [
            r"\b(?:chest.*pain|heart attack|cannot breathe|shortness of breath|difficulty breathing|unconscious|seizure|stroke|fell|slipped and fell|swollen.*red|iv.*beep)\b"
        ],
        "patterns_hi": [
            r"(?:सीने.*दर्द|छाती.*दर्द|दिल का दौरा|हार्ट अटैक|सांस.*तकलीफ|सांस नहीं|दम घुट|बेहोश|दौरा|मिर्गी|गिर.*पड़े|खून बह रहा|हाथ सूज)"
        ],
        "patterns_kn": [
            r"(?:ಎದೆ.*ನೋವು|ಹೃದಯಾಘಾತ|ಹಾರ್ಟ್ ಅಟ್ಯಾಕ್|ಉಸಿರಾಟ.*ತೊಂದರೆ|ಉಸಿರು ಕಟ್ಟ|ಪ್ರಜ್ಞಾಹೀನ|ಫಿಟ್ಸ್|ಕೆಳಗೆ ಬಿದ್ದರು|ಜಾರಿ ಬಿದ್ದರು|ಕೈ.*ಊತ)"
        ],
        "default_urgency": "STAT_EMERGENCY",
        "assigned_to": "STAT Rapid Response Clinical Team"
    },
    {
        "department": "Nursing & Clinical Care",
        "patterns_en": [
            r"\b(?:pain|knee replacement|crying|wound|bandage|dressing|vitals|dizzy|nurse|reposition|bathroom assist)\b"
        ],
        "patterns_hi": [
            r"(?:दर्द|नर्स|पट्टी|चक्कर|कमजोरी|बुखार|करवट|मदद)"
        ],
        "patterns_kn": [
            r"(?:ನೋವು|ಶುಶ್ರೂಷಕಿ|ನರ್ಸ್|ಬ್ಯಾಂಡೇಜ್|ತಲೆತಿರುಗುವಿಕೆ|ಜ್ವರ|ಸಹಾಯ)"
        ],
        "default_urgency": "URGENT",
        "assigned_to": "Floor Charge Nurse"
    },
    {
        "department": "Pharmacy & Therapeutics",
        "patterns_en": [
            r"\b(?:allergy|penicillin|antibiotic|dose|interaction|medication|prescription|pills|refill|pharmacy)\b"
        ],
        "patterns_hi": [
            r"(?:दवा|दवाई|एलर्जी|गोली|एंटीबायोटिक|खुराक|फार्मेसी|प्रिस्क्रिप्शन)"
        ],
        "patterns_kn": [
            r"(?:ಔಷಧಿ|ಮಾತ್ರೆ|ಅಲರ್ಜಿ|ಆಂಟಿಬಯೋಟಿಕ್|ಡೋಸ್|ಫಾರ್ಮಸಿ|ಪ್ರಿಸ್ಕ್ರಿಪ್ಷನ್)"
        ],
        "default_urgency": "URGENT",
        "assigned_to": "Clinical Staff Pharmacist"
    },
    {
        "department": "Facilities & Environmental Services",
        "patterns_en": [
            r"\b(?:shattered|glass|water.*floor|spill|slick|clean|housekeeping|linen|sheets|trash|cold room|wheelchair|transport)\b"
        ],
        "patterns_hi": [
            r"(?:फर्श पर पानी|फर्श|सफाई|कांच|फूट गया|व्हीलचेयर|कचरा|गंदगी|ठंडा कमरा|ट्रांसपोर्ट)"
        ],
        "patterns_kn": [
            r"(?:ನೆಲದ ಮೇಲೆ ನೀರು|ನೆಲದ ಮೇಲೆ|ಸ್ವಚ್ಛತೆ|ಗಾಜು|ಒಡೆದು|ವ್ಹೀಲ್‌ಚೇರ್|ಕಸ|ತಣ್ಣನೆ ಕೊಠಡಿ|ಸಾಗಣೆ)"
        ],
        "default_urgency": "ROUTINE",
        "assigned_to": "Facilities Dispatch"
    },
    {
        "department": "Dietary & Clinical Nutrition",
        "patterns_en": [
            r"\b(?:lunch|dinner|breakfast|meal|food|tray|diet|blood sugar|diabetic|hungry|nutrition|drinking water)\b"
        ],
        "patterns_hi": [
            r"(?:खाना|भोजन|दोपहर का खाना|डायबिटिक|शुगर|भूख|नाश्ता|पीने का पानी)"
        ],
        "patterns_kn": [
            r"(?:ಊಟ|ತಿಂಡಿ|ಆಹಾರ|ಡಯಾಬಿಟಿಕ್|ಸಕ್ಕರೆ ಕಾಯಿಲೆ|ಹಸಿವು|ಕುಡಿಯುವ ನೀರು)"
        ],
        "default_urgency": "ROUTINE",
        "assigned_to": "Dietary Services Supervisor"
    },
    {
        "department": "Administration & Discharge Coordination",
        "patterns_en": [
            r"\b(?:discharge|paperwork|doctor|dr\.\s*\w+|transport booked|billing|insurance|pre-authoriz|payment)\b"
        ],
        "patterns_hi": [
            r"(?:डिस्चार्ज|छुट्टी|कागजात|डॉक्टर से बात|बिल|बीमा|इंश्योरेंस|भुगतान)"
        ],
        "patterns_kn": [
            r"(?:ಡಿಸ್ಚಾರ್ಜ್|ದಾಖಲೆಗಳು|ವೈದ್ಯರು|ಡಾಕ್ಟರ್|ಬಿಲ್|ವಿಮೆ|ಇನ್ಶೂರೆನ್ಸ್|ಪಾವತಿ)"
        ],
        "default_urgency": "INQUIRY",
        "assigned_to": "Discharge Case Manager"
    }
]

CLINICAL_ACTION_KEYWORDS = [
    "pain", "breath", "iv", "beep", "swoll", "fall", "slip", "bleed", "unconscious",
    "med", "pill", "allerg", "dose", "pharm", "antibiotic",
    "food", "lunch", "dinner", "meal", "tray", "diet", "sugar",
    "clean", "spill", "water", "glass", "wheelchair", "trash",
    "discharge", "paper", "doctor", "dr.", "bill", "insurance",
    # Hindi
    "दर्द", "सांस", "आईवी", "सूजन", "खून", "गिर", "बेहोश", "दवा", "एलर्जी", "गोली",
    "खाना", "भोजन", "सफाई", "कांच", "डिस्चार्ज", "कागजात", "डॉक्टर", "बिल", "बीमा", "फर्श",
    # Kannada
    "ನೋವು", "ಉಸಿರಾ", "ಐವಿ", "ಊತ", "ರಕ್ತ", "ಬಿದ್ದ", "ಪ್ರಜ್ಞಾ", "ಔಷಧಿ", "ಮಾತ್ರೆ", "ಅಲರ್ಜಿ",
    "ಊಟ", "ತಿಂಡಿ", "ಆಹಾರ", "ಸ್ವಚ್ಛತೆ", "ಗಾಜು", "ಡಿಸ್ಚಾರ್ಜ್", "ದಾಖಲೆ", "ವೈದ್ಯ", "ಡಾಕ್ಟರ್", "ಬಿಲ್", "ವಿಮೆ", "ನೆಲದ"
]

def is_pure_intro_greeting(seg: str) -> bool:
    """Returns True if the segment is merely a speaker greeting/introduction without actionable tasks."""
    seg_clean = seg.strip().lower()
    has_action = any(k in seg_clean or k in seg for k in CLINICAL_ACTION_KEYWORDS)
    if not has_action:
        return True
    return False

def check_emergency_with_negation(text: str, lang: str) -> Tuple[bool, bool, List[str]]:
    """
    Check if text contains serious emergency symptoms and verify whether they are negated.
    Returns: (is_emergency, is_negated, matched_symptoms)
    """
    text_lower = text.lower()
    matched = []

    # Check symptom keywords across all languages
    for l_key in ["en", "hi", "kn"]:
        for sym in EMERGENCY_SYMPTOMS[l_key]:
            if re.search(r"\b" + sym + r"\b" if l_key == "en" else sym, text_lower if l_key == "en" else text, re.IGNORECASE):
                matched.append(sym)

    if not matched:
        return False, False, []

    # Check for negation
    is_negated = False
    for l_key in ["en", "hi", "kn"]:
        for neg_pat in NEGATION_PATTERNS[l_key]:
            if re.search(neg_pat, text_lower if l_key == "en" else text, re.IGNORECASE):
                is_negated = True
                break
        if is_negated:
            break

    if is_negated:
        return False, True, matched

    return True, False, matched

def split_multilingual_transcript(transcript: str, lang: str = "en") -> List[str]:
    """
    Splits compound speech containing multiple requests into atomic segments
    across Kannada, Hindi, and English.
    """
    cleaned = transcript.strip().replace("\r\n", "\n")

    # Multilingual split markers:
    # English: also, and also, additionally, plus, and one more thing, besides that, etc.
    # Hindi: और, इसके अलावा, साथ ही, और एक बात, भी, कृपया
    # Kannada: ಮತ್ತು, ಹಾಗೆಯೇ, ಜೊತೆಗೆ, ಇನ್ನೊಂದು ವಿಷಯ, ಕೂಡ, ದಯವಿಟ್ಟು
    # Plus punctuation boundaries: ., ?, !, ।, \n
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
        # Filter purely conversational greetings with no medical content
        if is_pure_intro_greeting(seg):
            continue
        segments.append(seg)

    # Fallback to newline or sentence split if regex yielded 1 or 0
    if len(segments) <= 1:
        fallback_sents = [
            s.strip(" \t\n,.;:।") for s in re.split(r"[.!?।\n]+", cleaned)
            if len(s.strip()) > 10 and not is_pure_intro_greeting(s)
        ]
        if fallback_sents:
            return fallback_sents
        return [cleaned]

    return segments

def classify_multilingual_segment(segment: str, lang: str) -> Dict[str, Any]:
    """Classify a request segment into department, urgency, title, and clinical flags."""
    is_emergency, is_negated, emergency_syms = check_emergency_with_negation(segment, lang)

    # Initial Urgency
    if is_emergency:
        urgency = "STAT_EMERGENCY"
    elif is_negated:
        urgency = "ROUTINE"
    else:
        urgency = "ROUTINE"

    # Match Department
    matched_dept = "Nursing & Clinical Care"
    assigned_to = "Floor Charge Nurse"

    seg_lower = segment.lower()
    for rule in DEPARTMENT_PATTERNS:
        # Check patterns for all languages
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
            matched_dept = rule["department"]
            assigned_to = rule["assigned_to"]
            if rule["default_urgency"] == "STAT_EMERGENCY" and not is_negated:
                urgency = "STAT_EMERGENCY"
            elif rule["default_urgency"] == "URGENT" and urgency != "STAT_EMERGENCY":
                urgency = "URGENT"
            elif rule["default_urgency"] == "INQUIRY" and urgency == "ROUTINE":
                urgency = "INQUIRY"
            break

    # Clinical flags detection
    flags = []
    if is_emergency:
        flags.append("CRITICAL_ACUTE_ALERT")
    if is_negated:
        flags.append("SYMPTOM_NEGATED_RULE_OUT")

    if any(k in seg_lower for k in ["iv", "swollen", "beep"]) or any(k in segment for k in ["आईवी", "सूजन", "ಐವಿ", "ಊತ"]):
        flags.append("IV_INFILTRATION_RISK")
    if any(k in seg_lower for k in ["fell", "slip", "fall"]) or any(k in segment for k in ["गिर", "ಬಿದ್ದ"]):
        flags.append("ACTIVE_FALL_RISK")
    if any(k in seg_lower for k in ["diabetic", "blood sugar", "lunch", "meal"]) or any(k in segment for k in ["डायबिटिक", "खाना", "ಡಯಾಬಿಟಿಕ್", "ಊಟ"]):
        flags.append("DIABETIC_NPO_WATCH")
    if any(k in seg_lower for k in ["allergy", "penicillin", "interaction"]) or any(k in segment for k in ["एलर्जी", "दवा", "ಅಲರ್ಜಿ", "ಔಷಧಿ"]):
        flags.append("MEDICATION_SAFETY_CHECK")
    if any(k in seg_lower for k in ["discharge", "transport", "dr."]) or any(k in segment for k in ["डिस्चार्ज", "कागजात", "ಡಿಸ್ಚಾರ್ಜ್"]):
        flags.append("DISCHARGE_COORDINATION")

    # Generate bilingual/English Title & Description for Clinical Action
    preview = segment[:60].strip()
    if is_emergency:
        title = f"STAT Emergency: {preview}..."
    elif is_negated:
        title = f"Clinical Note: Negated Symptom Check ({preview}...)"
    elif "Pharmacy" in matched_dept:
        title = f"Pharmacy & Medication: {preview}..."
    elif "Dietary" in matched_dept:
        title = f"Dietary Nutrition Request: {preview}..."
    elif "Facilities" in matched_dept:
        title = f"Facilities / Transport Request: {preview}..."
    elif "Administration" in matched_dept:
        title = f"Administrative & Discharge Task: {preview}..."
    else:
        title = f"Nursing Care Task: {preview}..."

    # Translated quote placeholder (if in Kannada or Hindi)
    translated_quote = ""
    if lang == "kn":
        translated_quote = f"[Kannada Speech Excerpt]: \"{segment}\""
    elif lang == "hi":
        translated_quote = f"[Hindi Speech Excerpt]: \"{segment}\""
    else:
        translated_quote = segment

    triage_notes = (
        f"Language detected: {lang.upper()}. "
        f"Urgency triaged as {urgency}. "
        f"{'CRITICAL: Emergency symptom identified.' if is_emergency else ''}"
        f"{'Note: Symptom negated by caller.' if is_negated else ''}"
    )

    return {
        "department": matched_dept,
        "title": title,
        "description": segment,
        "raw_quote": segment,
        "translated_quote": translated_quote,
        "language": lang,
        "urgency": urgency,
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

    # Room number pattern (Room 314, Room 108, कमरा 314, ರೂಮ್ 314, ಕೋಣೆ 314)
    room_match = re.search(r"(?:room|bed|ward|कमरा|ರೂಮ್|ಕೋಣೆ)\s*([0-9A-Za-z\-]+)", transcript, re.IGNORECASE)
    if room_match:
        entities["room_number"] = f"Room {room_match.group(1).upper()}"

    # English caller/patient
    caller_match = re.search(r"\bthis is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", transcript)
    if caller_match:
        entities["caller_name"] = caller_match.group(1).strip()

    patient_match = re.search(r"\b(?:patient|about|for|father|mother)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)\b", transcript)
    if patient_match:
        entities["patient_name"] = patient_match.group(1).strip()

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
    Decomposes into multiple atomic department tickets, checks emergency symptoms with negation,
    and preserves original language script.
    """
    detected_lang = language or detect_script_language(transcript)
    entities = extract_patient_entities(transcript)

    c_name = caller_name if caller_name and caller_name.strip() else entities["caller_name"]
    p_name = patient_name if patient_name and patient_name.strip() else entities["patient_name"]
    r_num = room_number if room_number and room_number.strip() else entities["room_number"]

    segments = split_multilingual_transcript(transcript, detected_lang)
    extracted_tickets = []
    has_emergency = False

    for seg in segments:
        classification = classify_multilingual_segment(seg, detected_lang)
        classification["patient_name"] = p_name
        classification["room_number"] = r_num
        if classification["urgency"] == "STAT_EMERGENCY":
            has_emergency = True
        extracted_tickets.append(classification)

    lang_labels = {"kn": "Kannada (ಕನ್ನಡ)", "hi": "Hindi (हिन्दी)", "en": "English"}
    lang_display = lang_labels.get(detected_lang, detected_lang.upper())

    summary = (
        f"Processed {lang_display} conversation for {p_name} ({r_num}) into "
        f"{len(extracted_tickets)} actionable hospital department tasks. "
        f"{'CRITICAL: STAT Emergency detected.' if has_emergency else 'All requests queued within standard SLA.'}"
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
