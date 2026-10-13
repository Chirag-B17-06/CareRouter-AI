"""Environment-driven configuration.

Settings are read from the environment on each call to ``get_settings()`` so tests
(and operators using a process manager) can change them without import-order issues.
No secrets have defaults; see ``.env.example`` for the variable list.
"""
import os
import secrets
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("carerouter.config")

try:  # optional: read backend/.env when present (real environment variables always win)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)
except ImportError:
    pass

_EPHEMERAL_JWT_SECRET: Optional[str] = None


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s; using default %s", name, default)
        return default


def _list(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return [p.strip() for p in raw.split(",") if p.strip()]


@dataclass(frozen=True)
class Settings:
    app_env: str
    jwt_secret: str
    access_token_minutes: int
    cors_allowed_origins: List[str]
    hospital_timezone: str
    # Rate limiting (per client IP, in-process; use a gateway/Redis limiter when scaling out)
    rate_limit_per_minute: int
    login_max_failures: int
    login_lockout_minutes: int
    # Audio / ASR
    asr_max_upload_mb: int
    asr_max_duration_seconds: int
    asr_workers: int
    asr_provider_order: List[str]
    indic_asr_enabled: bool
    indic_asr_model_id: str
    indic_asr_decoding: str
    audio_retention_hours: int
    # Extraction
    extraction_provider: str
    external_llm_allowed: bool
    llm_api_base: str
    llm_api_key: Optional[str]
    llm_model: str
    llm_timeout_seconds: int
    # Appointments
    appointment_auto_confirm: bool
    reminder_hours_before: int
    # Bootstrap
    bootstrap_admin_username: Optional[str]
    bootstrap_admin_password: Optional[str]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


def _resolve_jwt_secret(app_env: str) -> str:
    global _EPHEMERAL_JWT_SECRET
    secret = os.getenv("JWT_SECRET")
    if secret and len(secret) >= 32:
        return secret
    if app_env == "production":
        raise RuntimeError("JWT_SECRET (>= 32 characters) must be set when APP_ENV=production")
    if _EPHEMERAL_JWT_SECRET is None:
        _EPHEMERAL_JWT_SECRET = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET is not set; using an ephemeral per-process secret. "
            "All sessions are invalidated on restart. Set JWT_SECRET for any shared deployment."
        )
    return _EPHEMERAL_JWT_SECRET


def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    return Settings(
        app_env=app_env,
        jwt_secret=_resolve_jwt_secret(app_env),
        access_token_minutes=_int("ACCESS_TOKEN_MINUTES", 30),
        cors_allowed_origins=_list(
            "CORS_ALLOWED_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"]
        ),
        hospital_timezone=os.getenv("HOSPITAL_TIMEZONE", "Asia/Kolkata"),
        rate_limit_per_minute=_int("RATE_LIMIT_PER_MINUTE", 120),
        login_max_failures=_int("LOGIN_MAX_FAILURES", 5),
        login_lockout_minutes=_int("LOGIN_LOCKOUT_MINUTES", 15),
        asr_max_upload_mb=_int("ASR_MAX_UPLOAD_MB", 25),
        asr_max_duration_seconds=_int("ASR_MAX_DURATION_SECONDS", 600),
        asr_workers=max(1, _int("ASR_WORKERS", 1)),
        asr_provider_order=_list("ASR_PROVIDER_ORDER", ["indic_conformer", "whisper"]),
        indic_asr_enabled=_bool("INDIC_ASR_ENABLED", False),
        indic_asr_model_id=os.getenv("INDIC_ASR_MODEL_ID", "ai4bharat/indic-conformer-600m-multilingual"),
        indic_asr_decoding=os.getenv("INDIC_ASR_DECODING", "ctc").strip().lower(),
        audio_retention_hours=_int("AUDIO_RETENTION_HOURS", 0),
        extraction_provider=os.getenv("EXTRACTION_PROVIDER", "rules").strip().lower(),
        external_llm_allowed=_bool("EXTERNAL_LLM_ALLOWED", False),
        llm_api_base=os.getenv("LLM_API_BASE", "https://api.anthropic.com"),
        llm_api_key=os.getenv("LLM_API_KEY") or None,
        llm_model=os.getenv("LLM_MODEL", ""),
        llm_timeout_seconds=_int("LLM_TIMEOUT_SECONDS", 30),
        appointment_auto_confirm=_bool("APPOINTMENT_AUTO_CONFIRM", True),
        reminder_hours_before=_int("REMINDER_HOURS_BEFORE", 24),
        bootstrap_admin_username=os.getenv("BOOTSTRAP_ADMIN_USERNAME") or None,
        bootstrap_admin_password=os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or None,
    )
