"""Numeric-claim verification.

An LLM answer is accepted only if every number it states can be traced to a
tool output.  This is the core reliability mechanism of the advisor: the
language model may explain and prioritise, but it may not perform arithmetic
or invent figures.
"""
from __future__ import annotations

import re
from typing import Any

_CITATION_RE = re.compile(r"\[(?:T|K)\d+\]")
_ENUM_RE = re.compile(r"(?m)^\s*(?:\d{1,2}[.)]|[-*])\s+")
_NUMBER_RE = re.compile(
    r"(?P<currency>₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>k|lakh|lac|lakhs|crore|cr|m|million|%)?",
    re.IGNORECASE,
)


def _numeric(value: Any, out: list[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, str):
        for match in _NUMBER_RE.finditer(value):
            out.append(_to_value(match))
    elif isinstance(value, dict):
        for item in value.values():
            _numeric(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _numeric(item, out)


def _to_value(match: re.Match) -> float:
    number = float(match.group("number").replace(",", ""))
    scale = (match.group("scale") or "").lower()
    if scale == "k":
        number *= 1_000
    elif scale in {"lakh", "lac", "lakhs"}:
        number *= 100_000
    elif scale in {"crore", "cr"}:
        number *= 10_000_000
    elif scale in {"m", "million"}:
        number *= 1_000_000
    return number


def allowed_numbers(tool_results: list[dict], extra: list[Any] | None = None) -> list[float]:
    values: list[float] = []
    for result in tool_results:
        for key in ("facts", "display", "headline", "interpretation", "assumptions"):
            _numeric(result.get(key), values)
    for item in extra or []:
        _numeric(item, values)
    return values


def extract_claims(text: str) -> list[dict]:
    cleaned = _CITATION_RE.sub(" ", text or "")
    cleaned = _ENUM_RE.sub("\n", cleaned)
    claims = []
    for match in _NUMBER_RE.finditer(cleaned):
        raw = match.group(0).strip()
        value = _to_value(match)
        claims.append(
            {
                "text": raw,
                "value": round(value, 4),
                "currency": bool(match.group("currency")),
                "percent": (match.group("scale") or "") == "%",
            }
        )
    return claims


def _matches(claim: float, allowed: list[float]) -> bool:
    for candidate in allowed:
        tolerance = max(0.51, abs(claim) * 0.006)
        if abs(claim - candidate) <= tolerance:
            return True
    return False


def verify_answer(answer: str, tool_results: list[dict], extra_allowed: list[Any] | None = None) -> dict:
    claims = extract_claims(answer)
    allowed = allowed_numbers(tool_results, extra_allowed)
    unsupported = [c for c in claims if not _matches(c["value"], allowed)]
    return {
        "passed": len(unsupported) == 0,
        "checked": len(claims),
        "unsupported": unsupported[:12],
        "allowed_count": len(allowed),
    }
