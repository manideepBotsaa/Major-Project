"""HTTP helpers shared by blueprints."""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import jsonify, request, session

from .extensions import db
from .models import User
from .utils import json_safe


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "bad_request", details: Any = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.details = details


def require_user(fn: Callable):
    """Attach the signed-in user to ``request.current_user`` or return 401."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if not user:
            return jsonify({"error": "Authentication required", "code": "auth_required"}), 401
        request.current_user = user  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    return wrapped


def body() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {}
    return data


def ok(data: dict | None = None, status: int = 200):
    payload = {"ok": True}
    if data:
        payload.update(json_safe(data))
    return jsonify(payload), status


def error(message: str, status: int = 400, code: str = "bad_request", **extra):
    return jsonify({"error": message, "code": code, **json_safe(extra)}), status


def current_user() -> User:
    return request.current_user  # type: ignore[attr-defined]
