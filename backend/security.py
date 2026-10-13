import re
from pathlib import Path
from typing import Any, Optional
from fastapi import HTTPException

# Permitted audio extensions
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".webm", ".mp3", ".m4a", ".ogg", ".flac", ".aac"}

# Regex patterns for sensitive identifiers
# 10-digit Indian phone numbers (with or without +91 / 0)
PHONE_REGEX = re.compile(r'(?:\+?91[\s\-]?)?(?:[6-9]\d{9})')
# 12-digit Aadhaar / National ID pattern (xxxx xxxx xxxx or xxxxxxxxxxxx)
AADHAAR_REGEX = re.compile(r'\b\d{4}[\s\-]\d{4}[\s\-]\d{4}\b')

# Dangerous prefixes for CSV formula injection (OWASP standard)
CSV_INJECTION_PREFIXES = ('=', '+', '-', '@', '\t', '\r')

def mask_phone_number(phone: Optional[str]) -> str:
    """
    Masks a phone number to preserve privacy while keeping prefix for identification.
    Example: '+91 9876543210' -> '+91 98765 XXXXX'
    """
    if not phone or not phone.strip():
        return ""
    cleaned = phone.strip()
    digits = re.sub(r'\D', '', cleaned)

    # Normalize Indian numbers: strip leading country code 91 or 0 if 12 or 11 digits
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]

    if len(digits) >= 10:
        # Keep first 5 digits, mask remaining
        prefix = digits[:5]
        return f"+91 {prefix} XXXXX"
    elif len(digits) >= 4:
        return f"***{digits[-4:]}"
    return "***"

def redact_pii_text(text: str, patient_name: Optional[str] = None) -> str:
    """
    Redacts phone numbers, national IDs, and optional patient name in clinical text.
    """
    if not text:
        return ""

    redacted = text

    # Redact patient name if provided
    if patient_name and patient_name.strip() and patient_name.strip().lower() not in ("unknown patient", "unknown caller"):
        redacted = re.sub(re.escape(patient_name.strip()), "[PATIENT-NAME-REDACTED]", redacted, flags=re.IGNORECASE)

    # Redact Aadhaar / National IDs (12-digit format xxxx xxxx xxxx or 12 continuous digits)
    redacted = AADHAAR_REGEX.sub("[ID-REDACTED]", redacted)

    # Redact Indian phone numbers
    def _mask_match(match):
        val = match.group(0)
        digits = re.sub(r'\D', '', val)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        if len(digits) >= 10:
            return f"+91 {digits[:5]} XXXXX"
        return "[PHONE-REDACTED]"

    redacted = PHONE_REGEX.sub(_mask_match, redacted)
    return redacted

def sanitize_csv_cell(value: Any) -> str:
    """
    Neutralizes CSV formula injection (OWASP CSV Injection).
    If a string begins with '=', '+', '-', '@', '\\t', or '\\r',
    it is prepended with a single quote to prevent code/formula execution in Excel/Calc.
    """
    if value is None:
        return ""
    str_val = str(value)
    if not str_val:
        return ""

    # Check raw string or stripped string for formula triggers
    if str_val.startswith(('\t', '\r')) or str_val.lstrip().startswith(('=', '+', '-', '@')):
        return f"'{str_val}"
    return str_val

def validate_safe_audio_filename(filename: str, base_dir: Path) -> Path:
    """
    Validates that a filename is secure, prevents path traversal, and ensures it points
    to an authorized audio file within base_dir.
    Raises HTTPException 400 or 403 on violation.
    """
    if not filename or not filename.strip():
        raise HTTPException(status_code=400, detail="Audio filename cannot be empty")

    raw_name = filename.strip()

    # Reject null bytes
    if "\x00" in raw_name:
        raise HTTPException(status_code=400, detail="Prohibited null byte in filename")

    # Reject explicit directory traversal sequences
    if ".." in raw_name or "/" in raw_name or "\\" in raw_name:
        raise HTTPException(status_code=400, detail="Path traversal sequences are strictly prohibited")

    # Only allow safe characters (alphanumeric, hyphens, underscores, dots)
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', raw_name):
        raise HTTPException(status_code=400, detail="Filename contains prohibited characters")

    # Check extension
    ext = Path(raw_name).suffix.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Prohibited file format '{ext}'. Only authorized audio files ({', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}) are accessible."
        )

    # Resolve destination and verify containment inside base_dir
    safe_base = base_dir.resolve()
    target_path = (safe_base / raw_name).resolve()

    try:
        # Check containment
        target_path.relative_to(safe_base)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access to path outside audio directory is denied")

    return target_path
