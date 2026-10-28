"""Security primitives: field encryption, CSRF, and lightweight rate limits.

Sensitive free-text fields (transaction descriptions and notes) are encrypted
at rest with Fernet (AES-128-CBC + HMAC-SHA256).  Amounts, dates and
categories remain queryable so the analytics engine can work efficiently.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import threading
import time
from collections import defaultdict, deque
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

log = logging.getLogger(__name__)

_fernet: Fernet | None = None
_encryption_configured = False
_UNREADABLE = "[unreadable — encryption key changed]"


def configure_encryption(secret: str, key_material: str = "") -> None:
    """Initialise the process-wide Fernet instance.

    ``key_material`` may already be a valid Fernet key; otherwise a stable
    SHA-256 derived key is used.  This lets users supply a passphrase.
    """
    global _fernet, _encryption_configured
    material = (key_material or "").strip()
    if not material:
        material = f"clearpath-field-key::{secret}"
        log.warning(
            "FIELD_ENCRYPTION_KEY is not set; deriving a key from SECRET_KEY. "
            "Set a stable key before storing real data."
        )
    try:
        candidate = material.encode()
        if len(candidate) == 44 and candidate.endswith(b"="):
            _fernet = Fernet(candidate)
        else:
            digest = hashlib.sha256(material.encode("utf-8")).digest()
            _fernet = Fernet(base64.urlsafe_b64encode(digest))
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError("Could not initialise field encryption") from exc
    _encryption_configured = True


def encrypt_text(value: str) -> str:
    if not _encryption_configured or _fernet is None:
        raise RuntimeError("Encryption is not configured")
    return _fernet.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    if value is None:
        return ""
    if not _encryption_configured or _fernet is None:
        return value
    try:
        return _fernet.decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError):
        log.warning("Could not decrypt a stored field; returning sentinel")
        return _UNREADABLE


class EncryptedText(TypeDecorator):
    """SQLAlchemy type that transparently encrypts text at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        value = str(value)
        return encrypt_text(value)

    def process_result_value(self, value: Any, dialect) -> str | None:
        if value is None:
            return None
        return decrypt_text(value)


# ---------------------------------------------------------------------------
# Best-effort in-memory rate limiter (single process).  A production
# deployment should use Redis or a gateway-level limiter; documented in
# docs/THREAT_MODEL.md.
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return True
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


rate_limiter = RateLimiter()
