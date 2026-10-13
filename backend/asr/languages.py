"""Language metadata shared by the ASR providers and the UI."""

# Display names for every code any provider may return.
LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi — हिन्दी", "kn": "Kannada — ಕನ್ನಡ", "ta": "Tamil — தமிழ்",
    "te": "Telugu — తెలుగు", "bn": "Bengali — বাংলা", "mr": "Marathi — मराठी",
    "gu": "Gujarati — ગુજરાતી", "ml": "Malayalam — മലയാളം", "pa": "Punjabi — ਪੰਜਾਬੀ",
    "or": "Odia — ଓଡ଼ିଆ", "as": "Assamese — অসমীয়া", "ur": "Urdu — اردو", "ne": "Nepali — नेपाली",
    "sa": "Sanskrit — संस्कृतम्", "sd": "Sindhi", "ks": "Kashmiri", "kok": "Konkani",
    "mai": "Maithili", "doi": "Dogri", "brx": "Bodo", "mni": "Manipuri", "sat": "Santali",
    "uncertain": "Language uncertain",
}

# The 22 codes listed on the ai4bharat/indic-conformer-600m-multilingual model card.
# English is NOT among them; English audio must go to a different engine.
INDIC_CONFORMER_LANGUAGES = frozenset({
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "kok", "ks", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
})

AUTO_VALUES = {"", "auto", "detect", "auto-detect", "uncertain", "none"}

_ALIASES = {
    "english": "en", "hindi": "hi", "kannada": "kn", "tamil": "ta", "telugu": "te",
    "bengali": "bn", "bangla": "bn", "marathi": "mr", "gujarati": "gu", "malayalam": "ml",
    "punjabi": "pa", "odia": "or", "oriya": "or", "assamese": "as", "urdu": "ur",
}


def normalize_language(value):
    """Return a lower-case language code, or None for auto-detect."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in AUTO_VALUES:
        return None
    return _ALIASES.get(v, v)


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code, code.upper())
