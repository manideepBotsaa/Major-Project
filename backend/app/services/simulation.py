"""Counterfactual 'what if' simulations for the insights page and advisor."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..categories import normalize_category
from ..models import Goal
from ..utils import add_months, as_float, money_str, month_bounds, today
from .analytics import savings_capacity, tx_between
from .calculators import debt_plan, goal_projection


def category_monthly_average(user_id: int, category: str, months: int = 3, as_of: date | None = None) -> float:
    as_of = as_of or today()
    category = normalize_category(category)
    total = 0.0
    for offset in range(1, months + 1):
        first, last = month_bounds(add_months(as_of, -offset))
        rows = tx_between(user_id, first, last, "expense")
        total += sum(float(Decimal(r.amount)) for r in rows if r.category == category)
    return total / max(1, months)


def what_if(
    user_id: int,
    category: str | None = None,
    reduction_pct: float = 0.0,
    extra_savings: float = 0.0,
    extra_debt_payment: float = 0.0,
    months: int = 12,
    as_of: date | None = None,
) -> dict:
    as_of = as_of or today()
    months = max(1, min(60, int(months)))
    capacity = savings_capacity(user_id, 3)
    baseline_monthly = float(capacity["avg_monthly_savings"])
    category = normalize_category(category) if category else None
    category_spend = category_monthly_average(user_id, category, 3, as_of) if category else 0.0
    reduction_pct = max(0.0, min(100.0, as_float(reduction_pct)))
    freed = category_spend * reduction_pct / 100.0
    improvement = freed + max(0.0, as_float(extra_savings))
    scenario_monthly = baseline_monthly + improvement

    from ..models import Debt

    debts = [
        {
            "name": d.name,
            "balance": float(d.balance),
            "apr": float(d.apr),
            "minimum_payment": float(d.minimum_payment),
        }
        for d in Debt.query.filter_by(user_id=user_id).all()
    ]
    baseline_debt = debt_plan(debts, 0.0) if debts else None
    scenario_debt = debt_plan(debts, max(0.0, as_float(extra_debt_payment))) if debts else None

    goals = Goal.query.filter_by(user_id=user_id, archived=False).order_by(Goal.priority).all()
    goal_effect = None
    if goals:
        goal = goals[0]
        current = float(goal.saved_amount)
        target = float(goal.target_amount)
        ret = float(goal.expected_return or 0)
        base_projection = goal_projection(target, current, float(goal.monthly_contribution), ret, months)
        new_projection = goal_projection(
            target, current, float(goal.monthly_contribution) + max(0.0, improvement), ret, months
        )
        goal_effect = {
            "goal": goal.name,
            "current_monthly": money_str(goal.monthly_contribution),
            "baseline_value": money_str(base_projection["projected_value"]),
            "scenario_value": money_str(new_projection["projected_value"]),
            "extra_value": money_str(new_projection["projected_value"] - base_projection["projected_value"]),
            "target": money_str(target),
            "monthly_improvement": money_str(improvement),
        }

    projection = []
    balance = 0.0
    for month in range(1, months + 1):
        balance += max(0.0, scenario_monthly)
        if month % max(1, months // 6) == 0 or month == months:
            projection.append({"month": month, "saved": round(balance, 2)})

    return {
        "months": months,
        "category": category,
        "reduction_pct": round(reduction_pct, 1),
        "category_monthly_spend": money_str(category_spend),
        "freed_per_month": money_str(freed),
        "monthly_improvement": money_str(improvement),
        "extra_monthly_savings": money_str(max(0.0, as_float(extra_savings))),
        "extra_debt_payment": money_str(max(0.0, as_float(extra_debt_payment))),
        "baseline_monthly_savings": money_str(baseline_monthly),
        "scenario_monthly_savings": money_str(scenario_monthly),
        "baseline_projected_savings": money_str(max(0.0, baseline_monthly) * months),
        "scenario_projected_savings": money_str(max(0.0, scenario_monthly) * months),
        "extra_savings": money_str(max(0.0, scenario_monthly - baseline_monthly) * months),
        "goal_impact": goal_effect,
        "debt": {
            "baseline_interest": money_str(baseline_debt["avalanche"]["total_interest"]) if baseline_debt else None,
            "scenario_interest": money_str(scenario_debt["avalanche"]["total_interest"]) if scenario_debt else None,
            "interest_saved": money_str(
                max(
                    0.0,
                    (baseline_debt["avalanche"]["total_interest"] or 0)
                    - (scenario_debt["avalanche"]["total_interest"] or 0),
                )
            )
            if baseline_debt and scenario_debt
            else None,
            "months_saved": max(
                0,
                (baseline_debt["avalanche"]["months"] or 0) - (scenario_debt["avalanche"]["months"] or 0),
            )
            if baseline_debt and scenario_debt
            else None,
        }
        if debts
        else None,
        "projection": projection,
        "assumptions": [
            "Hold current income and all other spending constant.",
            "Savings are not invested here; debt interest is modelled separately.",
            "A projection is not a guarantee.",
        ],
    }
