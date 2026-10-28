"""Authentication, profile, session and account endpoints."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from flask import Blueprint, current_app, jsonify, request, session

from ..categories import SUPPORTED_CURRENCIES
from ..errors import body, current_user, error, require_user
from ..extensions import db
from ..models import (
    ActivityEvent,
    Asset,
    Budget,
    ChatSession,
    Debt,
    Goal,
    LiteracyProgress,
    Transaction,
    User,
)
from ..security import rate_limiter
from ..utils import as_float, json_safe, money_str

auth_bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _client_key(prefix: str) -> str:
    return f"{prefix}:{request.remote_addr or 'unknown'}"


def _set_session(user: User) -> str:
    session.clear()
    session["user_id"] = user.id
    session["csrf_token"] = current_app.config["CSRF_TOKEN_FACTORY"](32)
    session.permanent = True
    return session["csrf_token"]


def _public_user(user: User) -> dict:
    return {"user": user.as_dict(), "csrf_token": session.get("csrf_token")}


@auth_bp.post("/auth/register")
def register():
    if not rate_limiter.allow(_client_key("register"), 6, 900):
        return error("Too many attempts. Please try again later.", 429, "rate_limited")
    data = body()
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    if not name or len(name) > 100:
        return error("Enter your name")
    if not EMAIL_RE.fullmatch(email):
        return error("Enter a valid email address")
    if len(password) < 10:
        return error("Password must be at least 10 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return error("Password must include at least one letter and one number")
    if User.query.filter_by(email=email).first():
        return error("An account with this email already exists", 409, "already_exists")
    user = User(name=name, email=email)
    user.set_password(password)
    income = as_float(data.get("monthly_income"))
    if income > 0:
        user.monthly_income = Decimal(str(round(income, 2)))
    db.session.add(user)
    db.session.commit()
    token = _set_session(user)
    return jsonify({**_public_user(user), "csrf_token": token}), 201


@auth_bp.post("/auth/login")
def login():
    if not rate_limiter.allow(_client_key("login"), int(current_app.config.get("LOGIN_RATE_LIMIT", 10)), 900):
        return error("Too many sign-in attempts. Please wait 15 minutes.", 429, "rate_limited")
    data = body()
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    if not user or not user.check_password(str(data.get("password", ""))):
        return error("Email or password is incorrect", 401, "invalid_credentials")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    token = _set_session(user)
    return jsonify({**_public_user(user), "csrf_token": token})


@auth_bp.post("/auth/demo")
def demo_login():
    if not current_app.config.get("ALLOW_DEMO_LOGIN", True):
        return error("Demo login is disabled", 403, "demo_disabled")
    if not rate_limiter.allow(_client_key("demo"), 10, 3600):
        return error("Too many demo attempts. Please try again later.", 429, "rate_limited")
    email = current_app.config["DEMO_EMAIL"]
    user = User.query.filter_by(email=email).first()
    if not user:
        from ..seed import seed_demo

        seed_demo(current_app._get_current_object())
        user = User.query.filter_by(email=email).first()
    if not user:
        return error("Demo data is not available. Run 'flask seed-demo'.", 404, "demo_unavailable")
    user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.commit()
    token = _set_session(user)
    return jsonify({**_public_user(user), "csrf_token": token, "demo": True})


@auth_bp.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@auth_bp.get("/auth/me")
@require_user
def me():
    if not session.get("csrf_token"):
        session["csrf_token"] = current_app.config["CSRF_TOKEN_FACTORY"](32)
    return jsonify(_public_user(current_user()))


@auth_bp.patch("/profile")
@require_user
def update_profile():
    data = body()
    user = current_user()
    if "name" in data:
        name = str(data["name"]).strip()
        if not name or len(name) > 100:
            return error("Enter a valid name")
        user.name = name
    if "currency" in data:
        if data["currency"] not in SUPPORTED_CURRENCIES:
            return error("Unsupported currency")
        user.currency = data["currency"]
    if "language" in data and data["language"] in {"en", "hi", "te"}:
        user.language = data["language"]
    if "risk_profile" in data and data["risk_profile"] in {"conservative", "moderate", "aggressive"}:
        user.risk_profile = data["risk_profile"]
    if "monthly_income" in data:
        value = data["monthly_income"]
        user.monthly_income = None if value in (None, "") else Decimal(str(round(as_float(value), 2)))
    if "onboarded" in data:
        user.onboarded = bool(data["onboarded"])
    db.session.commit()
    return jsonify(_public_user(user))


@auth_bp.post("/profile/password")
@require_user
def change_password():
    data = body()
    user = current_user()
    if not user.check_password(str(data.get("current_password", ""))):
        return error("Current password is incorrect", 401, "invalid_credentials")
    new_password = str(data.get("new_password", ""))
    if len(new_password) < 10 or not re.search(r"[A-Za-z]", new_password) or not re.search(r"\d", new_password):
        return error("New password must be at least 10 characters and include a letter and a number")
    user.set_password(new_password)
    db.session.commit()
    return jsonify({"ok": True, "message": "Password updated"})


@auth_bp.get("/account/export")
@require_user
def export_account():
    user = current_user()
    goals = Goal.query.filter_by(user_id=user.id).all()
    sessions = ChatSession.query.filter_by(user_id=user.id).all()
    payload = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user.as_dict(),
        "transactions": [t.as_dict() for t in Transaction.query.filter_by(user_id=user.id).order_by(Transaction.transaction_date).all()],
        "budgets": [b.as_dict() for b in Budget.query.filter_by(user_id=user.id).order_by(Budget.month).all()],
        "goals": [
            {
                **g.as_dict(),
                "contributions": [c.as_dict() for c in g.contributions],
            }
            for g in goals
        ],
        "debts": [d.as_dict() for d in Debt.query.filter_by(user_id=user.id).all()],
        "assets": [a.as_dict() for a in Asset.query.filter_by(user_id=user.id).all()],
        "chat_sessions": [s.as_dict(include_messages=True) for s in sessions],
        "literacy_progress": [
            {
                "module_id": p.module_id,
                "status": p.status,
                "attempts": p.attempts,
                "best_score": p.best_score,
                "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            }
            for p in LiteracyProgress.query.filter_by(user_id=user.id).all()
        ],
        "activity": [a.as_dict() for a in ActivityEvent.query.filter_by(user_id=user.id).all()],
    }
    response = jsonify(json_safe(payload))
    response.headers["Content-Disposition"] = "attachment; filename=clearpath-export.json"
    return response


@auth_bp.delete("/account")
@require_user
def delete_account():
    user = current_user()
    if user.email == current_app.config.get("DEMO_EMAIL"):
        return error("The demo account cannot be deleted.", 403, "demo_account")
    data = body()
    if not user.check_password(str(data.get("password", ""))):
        return error("Enter your password to delete the account", 401, "invalid_credentials")
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return jsonify({"ok": True, "message": "Account deleted"})
