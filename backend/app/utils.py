"""Small, dependency-free helpers used across the financial engine."""
from __future__ import annotations

import calendar
import hashlib
import math
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Iterable

CENT = Decimal("0.01")


def today() -> date:
    return datetime.now(timezone.utc).date()


def parse_date(value: Any, default: date | None = None) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            pass
    if default is not None:
        return default
    raise ValueError("Invalid date; expected YYYY-MM-DD")


def parse_month(value: Any, default: date | None = None) -> date:
    """Parse YYYY-MM or YYYY-MM-DD into the first day of the month."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.replace(day=1)
    raw = str(value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}", raw):
        raw += "-01"
    parsed = parse_date(raw, default)
    return parsed.replace(day=1)


def month_start(value: date | None = None) -> date:
    value = value or today()
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    total = value.year * 12 + (value.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def month_bounds(value: date) -> tuple[date, date]:
    first = value.replace(day=1)
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, last


def days_in_month(value: date) -> int:
    return calendar.monthrange(value.year, value.month)[1]


def days_between(a: date, b: date) -> int:
    return max(0, (b - a).days)


def months_between(start: date, end: date) -> float:
    """Fractional month distance, used for goal projections."""
    if end <= start:
        return 0.0
    whole = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        whole -= 1
        anchor = add_months(start, whole)
        span = (add_months(anchor, 1) - anchor).days
        whole += max(0, (end - anchor).days) / max(1, span)
    else:
        anchor = add_months(start, whole)
        span = (add_months(anchor, 1) - anchor).days
        whole += min(1.0, (end - anchor).days / max(1, span))
    return max(0.0, float(whole))


def money(value: Any) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid monetary amount")
    if not result.is_finite():
        raise ValueError("Amount must be finite")
    return result.quantize(CENT, rounding=ROUND_HALF_UP)


def money_str(value: Any, places: int = 2) -> str:
    try:
        d = Decimal(str(value)).quantize(Decimal("1." + "0" * places), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        d = Decimal("0")
    return f"{d:.{places}f}"


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def pct(part: float, whole: float, digits: int = 1) -> float | None:
    if not whole:
        return None
    return round(part / whole * 100.0, digits)


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if not denominator:
        return default
    return numerator / denominator


def fingerprint(*parts: Any) -> str:
    raw = "|".join("" if p is None else str(p).strip().lower() for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def normalize_text(value: str | None) -> str:
    text = (value or "").lower()
    text = re.sub(r"[^a-z0-9\s&]", " ", text)
    text = re.sub(r"\b(upi|neft|imps|pos|ach|dr|cr|txn|ref|payment|paid|to|from|via)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_AMOUNT_RE = re.compile(
    r"(?P<currency>₹|rs\.?|inr|\$|usd|€|eur|£|gbp)?\s*"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<scale>k|lakh|lac|lakhs|crore|cr|m|million)?\b",
    re.IGNORECASE,
)


def parse_amount(text: str | None) -> float | None:
    """Extract the first monetary amount from free text (₹1.2 lakh -> 120000)."""
    if not text:
        return None
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    number = float(match.group("number").replace(",", ""))
    scale = (match.group("scale") or "").lower()
    if scale in {"k"}:
        number *= 1_000
    elif scale in {"lakh", "lac", "lakhs"}:
        number *= 100_000
    elif scale in {"crore", "cr"}:
        number *= 10_000_000
    elif scale in {"m", "million"}:
        number *= 1_000_000
    return number


def parse_duration_months(text: str | None) -> int | None:
    if not text:
        return None
    lower = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(year|yr|years|yrs)", lower)
    if m:
        return max(1, int(round(float(m.group(1)) * 12)))
    m = re.search(r"(\d+)\s*(month|months|mo|mos)", lower)
    if m:
        return max(1, int(m.group(1)))
    return None


def parse_percent(text: str | None) -> float | None:
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m:
        return float(m.group(1))
    return None


def daterange(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def json_safe(value: Any) -> Any:
    """Recursively convert Decimal/date values into JSON-friendly primitives."""
    if isinstance(value, Decimal):
        return money_str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6)
    return value


def month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def month_label(value: date) -> str:
    return value.strftime("%b %Y")


def financial_year(value: date) -> str:
    start = value.year if value.month >= 4 else value.year - 1
    return f"{start}-{str(start + 1)[-2:]}"
