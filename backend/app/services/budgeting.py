"""Budget planning and pacing."""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal

from ..categories import EXPENSE_CATEGORIES, normalize_category
from ..extensions import db
from ..models import Budget
from ..utils import (
    add_months,
    as_float,
    days_in_month,
    money_str,
    month_bounds,
    month_key,
    today,
)


def get_budget(user_id: int, category: str, month: date) -> Budget | None:
    return Budget.query.filter_by(user_id=user_id, category=category, month=month).first()


def upsert_budget(user_id: int, category: str, month: date, amount: float, rollover: bool = False) -> Budget:
    category = normalize_category(category)
    budget = get_budget(user_id, category, month)
    if budget is None:
        budget = Budget(user_id=user_id, category=category, month=month, amount=Decimal("0"))
        db.session.add(budget)
    budget.amount = Decimal(str(max(0.0, as_float(amount))))
    budget.rollover = bool(rollover)
    db.session.commit()
    return budget


def delete_budget(user_id: int, budget_id: int) -> bool:
    budget = Budget.query.filter_by(id=budget_id, user_id=user_id).first()
    if not budget:
        return False
    db.session.delete(budget)
    db.session.commit()
    return True


def budget_status(user_id: int, month: date, as_of: date | None = None) -> dict:
    from .analytics import tx_between

    month = month.replace(day=1)
    as_of = as_of or today()
    first, last = month_bounds(month)
    budgets = Budget.query.filter_by(user_id=user_id, month=month).order_by(Budget.category).all()
    rows = tx_between(user_id, first, last, "expense")
    spent: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        spent[row.category] += Decimal(row.amount)

    if as_of < first:
        elapsed = 0
    elif as_of > last:
        elapsed = days_in_month(month)
    else:
        elapsed = as_of.day
    total_days = days_in_month(month)

    categories = []
    total_budget = 0.0
    total_spent = 0.0
    for budget in budgets:
        amount = float(budget.amount)
        used = float(spent.get(budget.category, Decimal("0")))
        remaining = amount - used
        pace_expected = amount * (elapsed / total_days) if elapsed else 0.0
        projected = used / elapsed * total_days if elapsed and elapsed < total_days else used
        if used > amount:
            state = "over"
        elif used > pace_expected * 1.15 or projected > amount * 1.05:
            state = "watch"
        else:
            state = "on_track"
        categories.append(
            {
                "id": budget.id,
                "category": budget.category,
                "amount": money_str(amount),
                "spent": money_str(used),
                "remaining": money_str(remaining),
                "used_pct": round(used / amount * 100, 1) if amount else 0.0,
                "pace_expected": money_str(pace_expected),
                "pace_pct": round(used / pace_expected * 100, 1) if pace_expected else 0.0,
                "projected": money_str(projected),
                "state": state,
                "rollover": bool(budget.rollover),
                "days_left": max(0, total_days - elapsed),
                "daily_remaining": money_str(max(0.0, remaining) / max(1, total_days - elapsed)),
            }
        )
        total_budget += amount
        total_spent += used

    budgeted_categories = {b.category for b in budgets}
    unbudgeted = [
        {"category": category, "spent": money_str(value)}
        for category, value in sorted(spent.items(), key=lambda kv: kv[1], reverse=True)
        if category not in budgeted_categories and float(value) > 0
    ]

    over_count = sum(1 for c in categories if c["state"] == "over")
    watch_count = sum(1 for c in categories if c["state"] == "watch")
    if not categories:
        overall = "not_set"
    elif over_count:
        overall = "over"
    elif watch_count:
        overall = "watch"
    else:
        overall = "on_track"
    projected_total = sum(float(c["projected"]) for c in categories)
    return {
        "month": month_key(month),
        "label": month.strftime("%B %Y"),
        "total_budget": money_str(total_budget),
        "total_spent": money_str(total_spent),
        "total_remaining": money_str(total_budget - total_spent),
        "overall_state": overall,
        "over_count": over_count,
        "watch_count": watch_count,
        "projected_total": money_str(projected_total),
        "elapsed_days": elapsed,
        "days_in_month": total_days,
        "categories": categories,
        "unbudgeted": unbudgeted,
        "available_categories": EXPENSE_CATEGORIES,
    }


def suggest_budgets(user_id: int, month: date, months: int = 3) -> list[dict]:
    from .analytics import tx_between

    totals: dict[str, list[float]] = defaultdict(list)
    for offset in range(1, months + 1):
        first, last = month_bounds(add_months(month, -offset))
        rows = tx_between(user_id, first, last, "expense")
        by_cat: dict[str, float] = defaultdict(float)
        for row in rows:
            by_cat[row.category] += float(row.amount)
        for category in EXPENSE_CATEGORIES:
            totals[category].append(by_cat.get(category, 0.0))
    suggestions = []
    existing = {b.category: float(b.amount) for b in Budget.query.filter_by(user_id=user_id, month=month).all()}
    for category, values in totals.items():
        # A plain median is zero-inflated for infrequent categories (for example
        # one grocery run in three months gives median([0, 0, 3000]) == 0 and
        # hides the line entirely).  Use the typical *active-month* spend so
        # sparse but real categories still receive a usable starting budget.
        active_months = [value for value in values if value > 0]
        if not active_months:
            continue
        typical = statistics.median(active_months)
        suggested = round((typical * 1.05) / 100.0) * 100
        suggestions.append(
            {
                "category": category,
                "suggested": money_str(suggested),
                "median_spend": money_str(typical),
                "months_active": len(active_months),
                "months_observed": len(values),
                "current_budget": money_str(existing.get(category, 0)),
                "is_set": category in existing,
            }
        )
    return sorted(suggestions, key=lambda s: float(s["suggested"]), reverse=True)


def copy_budgets(user_id: int, from_month: date, to_month: date) -> int:
    source = Budget.query.filter_by(user_id=user_id, month=from_month).all()
    if not source:
        return 0
    count = 0
    for budget in source:
        existing = get_budget(user_id, budget.category, to_month)
        if existing:
            continue
        db.session.add(
            Budget(
                user_id=user_id,
                category=budget.category,
                month=to_month,
                amount=budget.amount,
                rollover=budget.rollover,
            )
        )
        count += 1
    db.session.commit()
    return count
