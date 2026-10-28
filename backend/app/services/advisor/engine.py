"""Advisor orchestration: plan -> tools -> composition -> verification -> storage."""
from __future__ import annotations

import time
from datetime import date

from ...extensions import db
from ...models import ChatMessage, ChatSession, utcnow
from ...utils import json_safe, today
from . import tools as tool_registry
from .composer import compose
from .planner import plan_query
from .providers import get_provider, provider_status

MAX_QUESTION_CHARS = 1200


def _compact_trace(results: list[dict]) -> list[dict]:
    trace = []
    for result in results:
        item = {key: value for key, value in result.items() if key != "knowledge"}
        item["knowledge"] = [
            {"id": chunk.get("id"), "title": chunk.get("title"), "heading": chunk.get("heading")}
            for chunk in result.get("knowledge") or []
        ]
        trace.append(json_safe(item))
    return trace


def answer(app, user, question: str, session_id: int | None = None, as_of: date | None = None) -> dict:
    started = time.monotonic()
    question = (question or "").strip()
    if not question:
        raise ValueError("Ask a question first")
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"Please keep the question under {MAX_QUESTION_CHARS} characters")
    as_of = as_of or today()

    session = None
    if session_id:
        session = ChatSession.query.filter_by(id=session_id, user_id=user.id).first()
        if not session:
            raise ValueError("Conversation not found")
    if session is None:
        title = question.replace("\n", " ")[:80]
        session = ChatSession(user_id=user.id, title=title)
        db.session.add(session)
        db.session.flush()

    user_message = ChatMessage(session_id=session.id, role="user", content=question)
    db.session.add(user_message)
    db.session.commit()

    plan = plan_query(app, user, question, as_of)
    results: list[dict] = []
    errors = []
    for call in plan.calls[:3]:
        try:
            result = tool_registry.execute(call.tool, user, call.args, as_of)
            results.append(result.as_dict())
        except Exception as exc:
            errors.append({"tool": call.tool, "error": str(exc)[:200]})
    if not results:
        try:
            fallback = tool_registry.execute("financial_overview", user, {}, as_of)
            results.append(fallback.as_dict())
        except Exception:
            pass
    if errors:
        plan.rationale = (plan.rationale + f" | tool errors: {errors[:2]}")[:500]

    composed = compose(app, user, question, plan, results, as_of)
    total_latency = int((time.monotonic() - started) * 1000)
    message = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=composed["answer"],
        tool_trace=_compact_trace(composed["tool_results"]),
        citations=json_safe(composed["citations"]),
        verification=json_safe(composed["verification"]),
        provider=composed["provider"],
        latency_ms=total_latency,
        created_at=utcnow(),
    )
    db.session.add(message)
    session.updated_at = message.created_at
    db.session.commit()

    return {
        "session": session.as_dict(),
        "message": message.as_dict(),
        "tool_results": json_safe(composed["tool_results"]),
        "citations": json_safe(composed["citations"]),
        "verification": json_safe(composed["verification"]),
        "planner": plan.as_dict(),
        "provider": composed["provider"],
        "model": composed["model"],
        "latency_ms": total_latency,
    }


def list_sessions(user_id: int) -> list[dict]:
    sessions = (
        ChatSession.query.filter_by(user_id=user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(30)
        .all()
    )
    return [s.as_dict() for s in sessions]


def get_session(user_id: int, session_id: int) -> dict:
    session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        raise ValueError("Conversation not found")
    return session.as_dict(include_messages=True)


def delete_session(user_id: int, session_id: int) -> bool:
    session = ChatSession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        return False
    db.session.delete(session)
    db.session.commit()
    return True


def feedback(user_id: int, message_id: int, rating: int | None, comment: str = "") -> dict:
    message = (
        ChatMessage.query.join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .filter(ChatMessage.id == message_id, ChatSession.user_id == user_id)
        .first()
    )
    if not message:
        raise ValueError("Message not found")
    if rating not in {-1, 0, 1, None}:
        raise ValueError("Rating must be -1, 0, or 1")
    message.rating = rating
    message.feedback = (comment or "")[:500]
    db.session.commit()
    return message.as_dict()


def suggestions(user) -> list[str]:
    from ..analytics import net_worth, savings_capacity
    from ..budgeting import budget_status
    from ..goals import goal_overview

    prompts = []
    goals = goal_overview(user.id)
    if goals["goals"]:
        top = goals["goals"][0]
        prompts.append(f"Am I on track for {top['name']}?")
    budget = budget_status(user.id, today().replace(day=1))
    if budget["categories"]:
        watch = next((c for c in budget["categories"] if c["state"] != "on_track"), budget["categories"][0])
        prompts.append(f"How is my {watch['category']} budget doing?")
    capacity = savings_capacity(user.id, 3)
    prompts.append("How much can I save in 6 months?")
    prompts.append("Can I afford a ₹25,000 purchase?")
    prompts.append("How do I become debt-free faster?")
    prompts.append("Where did my money go this month?")
    prompts.append("Explain emergency funds like I'm new to this.")
    net = net_worth(user.id)
    if float(net["net_worth"]) < 0:
        prompts.append("What should I fix first to improve my financial health?")
    seen = []
    for prompt in prompts:
        if prompt not in seen:
            seen.append(prompt)
    return seen[:6]


def catalog() -> dict:
    return {
        "tools": tool_registry.catalog(),
        "principles": [
            "Every number is computed by a deterministic tool.",
            "Language models may explain, but may not perform arithmetic.",
            "Unsupported numeric claims are rejected by a verifier.",
            "User data stays local unless an external LLM provider is explicitly configured.",
        ],
    }
