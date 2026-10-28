"""Application configuration.

All values can be overridden with environment variables (or a ``.env`` file
loaded by ``run.py``).  Defaults are deliberately safe for local development:
the app remains fully functional without any external API key.
"""
from __future__ import annotations

import os
from datetime import timedelta


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


class Config:
    # --- Core -----------------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "clearpath-local-development-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///finance.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    JSON_SORT_KEYS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    # --- Sessions / CSRF ------------------------------------------------
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=14)
    CSRF_ENABLED = _bool("CSRF_ENABLED", True)

    # --- CORS -----------------------------------------------------------
    FRONTEND_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "FRONTEND_ORIGIN", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    # --- Encryption at rest --------------------------------------------
    # A Fernet key (32 url-safe base64 bytes) or any long random passphrase.
    # If omitted, a key is derived from SECRET_KEY and a warning is emitted.
    FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")

    # --- Demo / onboarding ---------------------------------------------
    ALLOW_DEMO_LOGIN = _bool("ALLOW_DEMO_LOGIN", True)
    DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@clearpath.app")
    DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "DemoPass123!")
    AUTO_SEED_LITERACY = _bool("AUTO_SEED_LITERACY", True)

    # --- Advisor / LLM --------------------------------------------------
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower()  # auto|mock|gemini|openai
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_MAX_TOKENS = _int("LLM_MAX_TOKENS", 900)
    LLM_TIMEOUT_SECONDS = _int("LLM_TIMEOUT_SECONDS", 25)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")  # e.g. http://localhost:11434/v1
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_REQUIRE_NUMERIC_VERIFICATION = _bool("LLM_REQUIRE_NUMERIC_VERIFICATION", True)
    LLM_SEND_RAW_TRANSACTIONS = _bool("LLM_SEND_RAW_TRANSACTIONS", False)

    # --- Rate limits (per process, best-effort) -------------------------
    LOGIN_RATE_LIMIT = _int("LOGIN_RATE_LIMIT", 10)  # attempts / 15 min / IP
    CHAT_RATE_LIMIT = _int("CHAT_RATE_LIMIT", 40)  # messages / hour / user

    # --- Research / reproducibility ------------------------------------
    RESEARCH_AS_OF = os.getenv("RESEARCH_AS_OF", "").strip()


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    CSRF_ENABLED = False
    ALLOW_DEMO_LOGIN = True
    FIELD_ENCRYPTION_KEY = "test-only-key-not-for-production-use"
    RATELIMIT_ENABLED = False
