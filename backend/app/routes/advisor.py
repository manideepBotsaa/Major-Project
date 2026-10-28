"""Advisor chat, nudge and gamification endpoints."""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..errors import body, current_user, error, require_user
from ..extensions import db
from ..models import ChatSession
from ..security import rate_limiter
from ..services.advisor import engine
from ..services.advisor.providers import provider_status
from ..services.nudges import (
    gamification_summary,
    generate_nudges,
    nudge_effectiveness,
    respond_to_nudge,
)
from ..utils import today

advisor_bp = Blueprint("advisor", __name__)


@advisor_bp.get("/advisor/status")
@require_user
def advisor_status():
    user = current_user()
    return jsonify(
        {
            "llm": provider_status(current_app),
            "suggestions": engine.suggestions(user),
            "max_question_chars": engine.MAX_QUESTION_CHARS,
            "session_count": ChatSession.query.filter_by(user_id=user.id).count(),
        }
    )


@advisor_bp.get("/advisor/tools")
@require_user
def advisor_tools():
    return jsonify(engine.catalog())


@advisor_bp.get("/advisor/suggestions")
@require_user
def advisor_suggestions():
    return jsonify({"suggestions": engine.suggestions(current_user())})


@advisor_bp.get("/advisor/sessions")
@require_user
def advisor_sessions():
    return jsonify({"sessions": engine.list_sessions(current_user().id)})


@advisor_bp.post("/advisor/sessions")
@require_user
def create_advisor_session():
    user = current_user()
    data = body()
    title = str(data.get("title") or "New conversation").strip()[:160] or "New conversation"
    session = ChatSession(user_id=user.id, title=title)
    db.session.add(session)
    db.session.commit()
    return jsonify({"session": session.as_dict(include_messages=True)}), 201


@advisor_bp.get("/advisor/sessions/<int:session_id>")
@require_user
def advisor_session(session_id):
    try:
        return jsonify({"session": engine.get_session(current_user().id, session_id)})
    except ValueError as exc:
        return error(str(exc), 404, "not_found")


@advisor_bp.delete("/advisor/sessions/<int:session_id>")
@require_user
def delete_advisor_session(session_id):
    if not engine.delete_session(current_user().id, session_id):
        return error("Conversation not found", 404, "not_found")
    return jsonify({"ok": True})


@advisor_bp.post("/advisor/chat")
@require_user
def advisor_chat():
    user = current_user()
    limit = int(current_app.config.get("CHAT_RATE_LIMIT", 40))
    if not rate_limiter.allow(f"chat:{user.id}", limit, 3600):
        return error(
            "You have reached the hourly message limit. Please try again later.",
            429,
            "rate_limited",
        )
    data = body()
    question = str(data.get("message") or data.get("question") or "").strip()
    session_id = data.get("session_id")
    if session_id not in (None, ""):
        try:
            session_id = int(session_id)
        except (TypeError, ValueError):
            return error("session_id must be a number")
    else:
        session_id = None
    try:
        result = engine.answer(current_app._get_current_object(), user, question, session_id)
    except ValueError as exc:
        return error(str(exc))
    return jsonify(result)


@advisor_bp.post("/advisor/messages/<int:message_id>/feedback")
@require_user
def advisor_feedback(message_id):
    data = body()
    rating = data.get("rating")
    if rating is not None:
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return error("rating must be -1, 0 or 1")
        if rating not in {-1, 0, 1}:
            return error("rating must be -1, 0 or 1")
    try:
        message = engine.feedback(
            current_user().id, message_id, rating, str(data.get("comment") or "")
        )
    except ValueError as exc:
        return error(str(exc), 404, "not_found")
    return jsonify({"message": message})


# ---------------------------------------------------------------------------
# Just-in-time nudges and gamification
# ---------------------------------------------------------------------------
@advisor_bp.get("/nudges")
@require_user
def nudges():
    user = current_user()
    as_of = today()
    items = generate_nudges(user.id, as_of)
    return jsonify(
        {
            "nudges": items,
            "effectiveness": nudge_effectiveness(user.id),
            "gamification": gamification_summary(user.id),
        }
    )


@advisor_bp.post("/nudges/<int:nudge_id>/respond")
@require_user
def nudge_response(nudge_id):
    data = body()
    action = str(data.get("action") or "").strip().lower()
    try:
        result = respond_to_nudge(current_user().id, nudge_id, action)
    except ValueError as exc:
        return error(str(exc))
    return jsonify(result)


@advisor_bp.get("/nudges/effectiveness")
@require_user
def nudge_stats():
    return jsonify(nudge_effectiveness(current_user().id))


@advisor_bp.get("/gamification")
@require_user
def gamification():
    return jsonify(gamification_summary(current_user().id))
