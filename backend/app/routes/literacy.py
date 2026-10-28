"""Financial literacy curriculum and quiz endpoints."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..errors import body, current_user, error, require_user
from ..services import literacy
from ..services.literacy import (
    LiteracyModuleNotFound,
    get_module,
    list_modules,
    mark_viewed,
    progress_summary,
    search_knowledge,
    submit_quiz,
)

literacy_bp = Blueprint("literacy", __name__)


@literacy_bp.get("/literacy/modules")
@require_user
def modules():
    return jsonify(list_modules(current_user().id))


@literacy_bp.get("/literacy/modules/<slug>")
@require_user
def module_detail(slug):
    user = current_user()
    try:
        data = get_module(user.id, slug)
        mark_viewed(user.id, slug)
    except LiteracyModuleNotFound as exc:
        return error(str(exc), 404, "not_found")
    return jsonify({"module": data})


@literacy_bp.post("/literacy/modules/<slug>/view")
@require_user
def module_view(slug):
    try:
        mark_viewed(current_user().id, slug)
    except LiteracyModuleNotFound as exc:
        return error(str(exc), 404, "not_found")
    return jsonify({"ok": True})


@literacy_bp.post("/literacy/modules/<slug>/quiz")
@require_user
def quiz(slug):
    data = body()
    answers = data.get("answers")
    if not isinstance(answers, list):
        return error("answers must be a list")
    try:
        result = submit_quiz(current_user().id, slug, answers)
    except LiteracyModuleNotFound as exc:
        return error(str(exc), 404, "not_found")
    except ValueError as exc:
        return error(str(exc))
    return jsonify(result)


@literacy_bp.get("/literacy/progress")
@require_user
def progress():
    return jsonify(progress_summary(current_user().id))


@literacy_bp.get("/literacy/search")
@require_user
def search():
    query = (request.args.get("q") or "").strip()
    if not query:
        return error("q is required")
    return jsonify({"results": search_knowledge(query, 5)})
