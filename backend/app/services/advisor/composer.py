"""Answer composition and numeric verification orchestration."""
from __future__ import annotations

import json
import logging
from datetime import date

from ...utils import json_safe
from .providers import LLMError, get_provider
from .verifier import verify_answer

log = logging.getLogger(__name__)

DISCLAIMER = (
    "Clearpath is an educational planning tool, not a SEBI-registered investment adviser or a lender. "
    "Projections are estimates, not guarantees."
)


def collect_citations(results: list[dict]) -> list[dict]:
    citations = []
    seen = set()
    for result in results:
        for chunk in result.get("knowledge") or []:
            key = (chunk.get("module_slug"), chunk.get("heading"))
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "id": f"K{len(citations) + 1}",
                    "title": chunk.get("title") or chunk.get("module_title"),
                    "heading": chunk.get("heading"),
                    "text": chunk.get("text", "")[:700],
                    "module_slug": chunk.get("module_slug"),
                    "level": chunk.get("level"),
                    "score": chunk.get("score"),
                }
            )
            if len(citations) >= 5:
                return citations
    return citations


def _learn_more(citations: list[dict]) -> str:
    if not citations:
        return ""
    lines = [f"- [{c['id']}] {c['title']}" + (f" — {c['heading']}" if c.get("heading") else "") for c in citations[:3]]
    return "\n\n**Learn more**\n" + "\n".join(lines)


def deterministic_answer(user, question: str, plan, results: list[dict], citations: list[dict]) -> str:
    if not results:
        return (
            "I can help with budgets, affordability, debt, goals, forecasts and financial concepts. "
            "Try asking something like “Can I afford a ₹40,000 phone?” or “Where did my money go last month?”"
        )
    parts = []
    if plan.clarification:
        parts.append(plan.clarification)
    if len(results) == 1:
        result = results[0]
        parts.append(f"**{result['headline']}**")
        if result.get("display"):
            parts.append("\n".join(f"- {line}" for line in result["display"][:8]))
        if result.get("interpretation"):
            parts.append(result["interpretation"])
    else:
        for result in results:
            section = [f"**{result['label']}**", result["headline"]]
            if result.get("display"):
                section.append("\n".join(f"- {line}" for line in result["display"][:5]))
            if result.get("interpretation"):
                section.append(result["interpretation"])
            parts.append("\n\n".join(section))
    assumptions = []
    for result in results:
        for item in result.get("assumptions") or []:
            if item not in assumptions:
                assumptions.append(item)
    if assumptions:
        parts.append("**Assumptions**\n" + "\n".join(f"- {item}" for item in assumptions[:4]))
    learn = _learn_more(citations)
    if learn:
        parts.append(learn.strip())
    parts.append(DISCLAIMER)
    return "\n\n".join(part for part in parts if part).strip()


def _redact_for_llm(results: list[dict]) -> list[dict]:
    cleaned = json.loads(json.dumps(json_safe(results)))
    for result in cleaned:
        if result.get("tool") == "recent_transactions":
            for tx in (result.get("facts") or {}).get("transactions", []):
                tx["description"] = "[redacted]"
                tx["notes"] = ""
            result["display"] = [
                line.split("·")[0] + "· [description redacted] ·" + line.split("·")[-1]
                for line in result.get("display", [])
            ]
        result.pop("knowledge", None)
    return cleaned


def llm_answer(provider, user, question: str, plan, results: list[dict], citations: list[dict], unsupported=None) -> str:
    system = (
        "You are Clearpath, a calm and precise personal-finance explainer. "
        "You will receive TOOL_RESULTS computed by a deterministic financial engine. "
        "Absolute rules: (1) use only numbers that appear in TOOL_RESULTS; never calculate, estimate or invent a number; "
        "(2) do not recommend specific securities, funds or stocks; (3) do not promise returns; "
        "(4) explain the trade-off and give one concrete next action; (5) cite educational passages as [K1], [K2]; "
        "(6) use Markdown, 120-200 words, and end with a one-sentence educational disclaimer. "
        "If the data is insufficient, say so plainly instead of guessing."
    )
    payload = {
        "question": question,
        "today": date.today().isoformat(),
        "currency": user.currency,
        "planner": plan.as_dict(),
        "tool_results": _redact_for_llm(results),
        "citations": [
            {"id": c["id"], "title": c["title"], "heading": c["heading"], "text": c["text"]}
            for c in citations
        ],
    }
    user_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if unsupported:
        user_text += (
            "\n\nYour previous answer contained numbers that are not supported by TOOL_RESULTS: "
            + ", ".join(str(item.get("text")) for item in unsupported[:8])
            + ". Rewrite the answer using only supported numbers. Do not mention this correction."
        )
    return provider.complete(system, user_text)


def compose(app, user, question: str, plan, results: list[dict], as_of: date) -> dict:
    citations = collect_citations(results)
    deterministic = deterministic_answer(user, question, plan, results, citations)
    extra = [
        as_of.isoformat(),
        as_of.year,
        as_of.month,
        as_of.day,
        user.currency,
        [c.get("title") for c in citations],
        [c.get("heading") for c in citations],
        [c.get("text") for c in citations],
    ]
    provider = get_provider(app)
    attempts = 0
    if provider.available():
        try:
            response = llm_answer(provider, user, question, plan, results, citations)
            answer = response.text.strip()
            attempts = 1
            verification = verify_answer(answer, results, extra)
            if not verification["passed"]:
                retry = llm_answer(
                    provider, user, question, plan, results, citations, verification["unsupported"]
                )
                answer = retry.text.strip()
                attempts = 2
                verification = verify_answer(answer, results, extra)
                response = retry
            if verification["passed"] and answer:
                return {
                    "answer": answer,
                    "provider": response.provider,
                    "model": response.model,
                    "latency_ms": response.latency_ms,
                    "verification": {**verification, "attempts": attempts, "mode": "llm"},
                    "citations": citations,
                    "tool_results": results,
                    "planner": plan.as_dict(),
                }
            log.warning("LLM answer failed numeric verification; using deterministic fallback")
        except LLMError as exc:
            log.warning("LLM composition failed: %s", exc)
    verification = verify_answer(deterministic, results, extra)
    return {
        "answer": deterministic,
        "provider": "mock",
        "model": "clearpath-rules",
        "latency_ms": 0,
        "verification": {**verification, "attempts": attempts, "mode": "deterministic"},
        "citations": citations,
        "tool_results": results,
        "planner": plan.as_dict(),
    }
