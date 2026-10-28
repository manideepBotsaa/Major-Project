"""Query planning: rules first, optional LLM planner, always schema-validated."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ...categories import ALL_CATEGORIES, normalize_category
from ...utils import (
    add_months,
    as_float,
    parse_amount,
    parse_duration_months,
    parse_percent,
    today,
)
from .providers import LLMError, get_provider, parse_json
from .tools import TOOLS, catalog

log = logging.getLogger(__name__)

MAX_CALLS = 3

_CATEGORY_ALIASES = {
    "food": "Food & Dining",
    "dining": "Food & Dining",
    "eating out": "Food & Dining",
    "restaurant": "Food & Dining",
    "swiggy": "Food & Dining",
    "zomato": "Food & Dining",
    "groceries": "Groceries",
    "grocery": "Groceries",
    "transport": "Transport",
    "uber": "Transport",
    "cab": "Transport",
    "fuel": "Transport",
    "rent": "Housing",
    "housing": "Housing",
    "utilities": "Utilities",
    "electricity": "Utilities",
    "healthcare": "Healthcare",
    "medical": "Healthcare",
    "shopping": "Shopping",
    "amazon": "Shopping",
    "entertainment": "Entertainment",
    "movies": "Entertainment",
    "subscriptions": "Subscriptions",
    "netflix": "Subscriptions",
    "education": "Education",
    "travel": "Travel",
    "trip": "Travel",
    "flight": "Travel",
    "loan": "Loan EMI",
    "debt": "Loan EMI",
    "credit card": "Loan EMI",
    "insurance": "Insurance",
    "investments": "Investments",
    "investing": "Investments",
    "sip": "Investments",
}


@dataclass
class ToolCall:
    tool: str
    args: dict = field(default_factory=dict)
    reason: str = ""


@dataclass
class Plan:
    calls: list[ToolCall]
    source: str = "rules"
    clarification: str | None = None
    rationale: str = ""

    def as_dict(self) -> dict:
        return {
            "calls": [{"tool": c.tool, "args": c.args, "reason": c.reason} for c in self.calls],
            "source": self.source,
            "clarification": self.clarification,
            "rationale": self.rationale,
        }


def detect_category(text: str) -> str | None:
    lower = (text or "").lower()
    for category in ALL_CATEGORIES:
        if category.lower() in lower:
            return category
    for alias, category in sorted(_CATEGORY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lower):
            return category
    return None


def _amount(text: str) -> float | None:
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\s*(?:%|percent|months?|mos?|years?|yrs?)\b", " ", text, flags=re.I)
    value = parse_amount(cleaned)
    if value is None:
        return None
    return float(value)


def _months(text: str) -> int | None:
    lower = (text or "").lower()
    if re.search(r"\blast month\b", lower):
        return 1
    if re.search(r"\blast year\b|\bpast year\b", lower):
        return 12
    if re.search(r"\bhalf[- ]year\b", lower):
        return 6
    return parse_duration_months(text)


def _month_hint(text: str, as_of: date) -> str | None:
    lower = (text or "").lower()
    if re.search(r"\blast month\b|\bprevious month\b|\bmonth before\b", lower):
        return add_months(as_of, -1).strftime("%Y-%m")
    if re.search(r"\bthis month\b|\bcurrent month\b", lower):
        return as_of.strftime("%Y-%m")
    return None


def _age(text: str) -> float:
    match = re.search(r"\b(?:i am|i'm|age[d]?)\s*(\d{2})\b", text or "", flags=re.I)
    if not match:
        match = re.search(r"\b(\d{2})\s*(?:years?|yrs?)\s*old\b", text or "", flags=re.I)
    if match:
        return max(18.0, min(90.0, float(match.group(1))))
    return 30.0


def _calls_for(text: str, as_of: date) -> tuple[list[ToolCall], str | None]:
    t = (text or "").lower().strip()
    if not t:
        return [ToolCall("financial_overview", {}, "empty query")], None
    amount = _amount(text)
    percent = parse_percent(text)
    months = _months(text)
    category = detect_category(text)
    month_hint = _month_hint(text, as_of)
    calls: list[ToolCall] = []
    clarification = None

    def add(tool: str, args: dict | None = None, reason: str = "") -> None:
        if len(calls) < MAX_CALLS and all(c.tool != tool for c in calls):
            calls.append(ToolCall(tool, args or {}, reason))

    if re.search(r"\b(hi|hello|hey|good morning|good evening|namaste)\b", t) and len(t) < 25:
        return [ToolCall("financial_overview", {}, "greeting")], None

    wants_afford = bool(re.search(r"\b(afford|affordable|buy|purchase|should i get|can i get|worth it)\b", t))
    wants_goal = bool(re.search(r"\b(goal|trip|house|car|wedding|education fund|retire)\b", t))
    wants_debt = bool(re.search(r"\b(debt|loan|credit card|pay off|payoff|emi)\b", t))
    wants_budget = "budget" in t
    wants_forecast = bool(re.search(r"\b(forecast|predict|next month|next few months|projection)\b", t))
    wants_save = bool(re.search(r"\b(save|saving|savings)\b", t))
    wants_emergency = bool(re.search(r"\b(emergency|rainy day|buffer|runway)\b", t))
    wants_subscription = bool(re.search(r"\b(subscription|recurring|netflix|spotify|prime)\b", t))
    wants_unusual = bool(re.search(r"\b(unusual|anomaly|anomalies|weird|big expense|overspend)\b", t))
    wants_health = bool(re.search(r"\b(health score|financial health|how am i doing|score)\b", t))
    wants_networth = bool(re.search(r"\b(net worth|networth|assets|liabilit)\b", t))
    wants_invest = bool(re.search(r"\b(invest|sip|mutual fund|compounding)\b", t))
    wants_retire = bool(re.search(r"\b(retire|retirement|fire|financial independence)\b", t))
    wants_categories = bool(re.search(r"\b(where.*money|spending|spent|expenses|category|categories|breakdown)\b", t))
    wants_safe = bool(re.search(r"\b(safe to spend|daily|how much can i spend|left to spend)\b", t))
    wants_transactions = bool(re.search(r"\b(transaction|transactions|recent activity|last purchase)\b", t))
    wants_whatif = bool(re.search(r"\b(what if|what-if|if i (cut|reduce|save|pay)|scenario|simulate)\b", t))
    wants_learning = bool(re.search(r"\b(what is|what are|explain|define|learn|how does|how do|meaning of)\b", t))

    if wants_whatif:
        args = {
            "category": category,
            "reduction_pct": percent if percent is not None else (10 if category else 0),
            "extra_savings": amount if amount and wants_save else 0,
            "months": months or 12,
        }
        if wants_debt and amount:
            args["extra_debt_payment"] = amount
            args["extra_savings"] = 0
        add("what_if", args, "what-if scenario")
        return calls, None

    if wants_afford and re.search(r"\b(loan|borrow|finance|financing|installment|instalment)\b", t) and amount:
        add(
            "loan_affordability",
            {"principal": amount, "apr": percent or 12, "monthly_payment": None},
            "loan affordability",
        )
        if wants_goal:
            add("goal_status", {}, "goal context")
        return calls, None

    if wants_afford:
        if amount:
            add(
                "check_affordability",
                {
                    "amount": amount,
                    "category": category or "Shopping",
                    "apr": percent if (percent is not None and re.search(r"credit|card|finance|emi", t)) else None,
                    "months": months,
                },
                "purchase affordability",
            )
            if wants_goal or "goal" in t:
                add("goal_status", {}, "goal context")
        else:
            add("safe_to_spend", {}, "spending capacity")
            add("budget_status", {}, "budget context")
            clarification = "Tell me the purchase amount and what it is for, and I can run the affordability check."
        return calls, clarification

    if wants_retire:
        add("calculate_fire", {"current_age": _age(text)}, "retirement projection")
        return calls, clarification

    if wants_debt:
        if percent and amount and "emi" in t:
            add("calculate_emi", {"principal": amount, "annual_rate": percent, "months": months or 60}, "EMI calculation")
        elif amount and re.search(r"\b(loan|borrow)\b", t) and "pay off" not in t and "repay" not in t:
            add("loan_affordability", {"principal": amount, "apr": percent or 12}, "loan affordability")
        else:
            add("debt_payoff", {"extra_payment": amount if amount and wants_save else 0}, "debt payoff")
        return calls, clarification

    if wants_emergency:
        add("emergency_fund", {}, "emergency runway")
        if wants_save:
            add("savings_estimate", {"months": months or 6}, "savings estimate")
        return calls, clarification

    if wants_subscription:
        add("recurring_subscriptions", {}, "subscription audit")
        return calls, clarification

    if wants_unusual:
        add("anomalies", {}, "unusual spending")
        return calls, clarification

    if wants_forecast:
        add("forecast_expenses", {"horizon": min(6, max(1, months or 3))}, "expense forecast")
        if wants_budget:
            add("budget_status", {}, "budget context")
        return calls, clarification

    if wants_budget:
        if category and "how much" in t:
            add("budget_tracking", {"category": category}, "category budget pace")
        else:
            add("budget_status", {}, "budget status")
        return calls, clarification

    if wants_invest:
        if amount:
            add(
                "calculate_sip",
                {"monthly_investment": amount, "annual_return": percent or 12, "years": (months or 120) / 12},
                "SIP projection",
            )
        else:
            add("literacy_lookup", {"query": text}, "investment education")
        return calls, clarification

    if wants_health:
        add("financial_health", {}, "health score")
        return calls, clarification

    if wants_networth:
        add("net_worth", {}, "net worth")
        return calls, clarification

    if wants_safe:
        add("safe_to_spend", {}, "spending allowance")
        return calls, clarification

    if wants_save:
        add("savings_estimate", {"months": months or 3}, "savings estimate")
        if wants_goal:
            add("goal_status", {}, "goal context")
        return calls, clarification

    if wants_transactions:
        add("recent_transactions", {"limit": 5}, "recent transactions")
        return calls, clarification

    if wants_goal:
        add("goal_status", {}, "goal status")
        return calls, clarification

    if wants_categories:
        add("category_spending", {"month": month_hint} if month_hint else {}, "category breakdown")
        return calls, clarification

    if wants_learning:
        add("literacy_lookup", {"query": text}, "financial education")
        return calls, clarification

    add("financial_overview", {}, "general overview")
    return calls, clarification


def rule_plan(text: str, as_of: date | None = None) -> Plan:
    calls, clarification = _calls_for(text, as_of or today())
    return Plan(calls=calls, source="rules", clarification=clarification, rationale="Deterministic intent rules")


def _coerce_args(spec, args: dict) -> dict:
    if not isinstance(args, dict):
        return {}
    cleaned: dict = {}
    properties = (spec.parameters or {}).get("properties", {})
    for key, value in args.items():
        if key not in properties:
            continue
        expected = properties[key].get("type")
        try:
            if expected == "number":
                cleaned[key] = float(value)
            elif expected == "integer":
                cleaned[key] = int(float(value))
            elif expected == "string":
                cleaned[key] = str(value)[:300]
            else:
                cleaned[key] = value
        except (TypeError, ValueError):
            continue
    return cleaned


def validate_llm_plan(data: dict, question: str) -> Plan:
    calls = []
    raw_calls = data.get("calls") if isinstance(data, dict) else None
    if not isinstance(raw_calls, list):
        raise LLMError("Planner returned no calls list")
    for item in raw_calls[:MAX_CALLS]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("tool", ""))
        if name not in TOOLS:
            continue
        if name == "recent_transactions" and not re.search(
            r"\b(transaction|transactions|recent|purchase|payment)\b", question.lower()
        ):
            continue
        args = _coerce_args(TOOLS[name], item.get("args") or {})
        required = (TOOLS[name].parameters or {}).get("required", [])
        if any(key not in args for key in required):
            continue
        calls.append(ToolCall(name, args, str(item.get("reason", ""))[:200]))
    if not calls:
        raise LLMError("No valid tool calls")
    return Plan(calls=calls, source="llm", clarification=data.get("clarification"), rationale=str(data.get("reason", ""))[:300])


def llm_plan(provider, user, question: str, as_of: date) -> Plan:
    tools_json = json.dumps(
        [
            {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
            for t in catalog()
        ],
        ensure_ascii=False,
    )[:14000]
    system = (
        "You are the planning module of Clearpath, a personal-finance advisor. "
        "Choose at most three tools that are necessary to answer the user's question. "
        "Never do arithmetic yourself; the tools compute every number. "
        "Return ONLY JSON with this shape: "
        '{"calls":[{"tool":"tool_name","args":{...},"reason":"short"}],"clarification":null}. '
        "Use only tools in the catalogue and only arguments allowed by their schema. "
        "If the question is educational, use literacy_lookup. "
        "Use recent_transactions only when the user explicitly asks about transactions. "
        f"Today is {as_of.isoformat()}; currency is {user.currency}. "
        f"Catalogue: {tools_json}"
    )
    response = provider.complete(system, question, json_mode=True)
    data = parse_json(response.text)
    plan = validate_llm_plan(data, question)
    plan.rationale = (plan.rationale + f" ({response.model})")[:300]
    return plan


def plan_query(app, user, question: str, as_of: date | None = None) -> Plan:
    as_of = as_of or today()
    fallback = rule_plan(question, as_of)
    provider = get_provider(app)
    if not provider.available():
        return fallback
    try:
        return llm_plan(provider, user, question, as_of)
    except Exception as exc:
        log.warning("LLM planner failed; using rules: %s", exc)
        fallback.rationale += f" (planner fallback: {type(exc).__name__})"
        return fallback
