"""Savings goals, Monte Carlo feasibility, and contributions."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import numpy as np

from ..extensions import db
from ..models import Goal, GoalContribution
from ..utils import (
    as_float,
    clamp,
    days_in_month,
    money_str,
    months_between,
    safe_div,
    today,
)
from .calculators import goal_projection, required_monthly_contribution


def monte_carlo_goal(
    target: float,
    current: float,
    monthly_contribution: float,
    annual_return: float,
    months: int,
    volatility: float = 12.0,
    simulations: int = 1200,
    seed: int = 7,
) -> dict:
    """Estimate probability of reaching a goal with stochastic returns.

    Returns are modelled as i.i.d. normal monthly returns.  This is a
    deliberately simple model; it is a planning aid, not a market forecast.
    """
    target = max(0.0, as_float(target))
    current = max(0.0, as_float(current))
    monthly = max(0.0, as_float(monthly_contribution))
    months = max(1, int(months))
    if current >= target:
        return {"probability": 1.0, "p10": current, "p50": current, "p90": current, "simulations": simulations}
    rng = np.random.default_rng(seed)
    mean = as_float(annual_return) / 12.0 / 100.0
    std = max(0.0, as_float(volatility)) / 100.0 / np.sqrt(12.0)
    returns = rng.normal(mean, std, size=(simulations, months))
    balances = np.full(simulations, current, dtype=float)
    for month in range(months):
        balances = balances * (1.0 + returns[:, month]) + monthly
    success = float(np.mean(balances >= target))
    return {
        "probability": round(success, 3),
        "p10": round(float(np.percentile(balances, 10)), 2),
        "p50": round(float(np.percentile(balances, 50)), 2),
        "p90": round(float(np.percentile(balances, 90)), 2),
        "simulations": simulations,
        "volatility": volatility,
    }


def goal_status(goal: Goal, as_of: date | None = None) -> dict:
    as_of = as_of or today()
    saved = float(goal.saved_amount)
    target = float(goal.target_amount)
    monthly = float(goal.monthly_contribution)
    expected_return = float(goal.expected_return or 0)
    progress = clamp(safe_div(saved, target)) * 100 if target else 0.0
    months_left = int(round(months_between(as_of, goal.target_date))) if goal.target_date else None
    if months_left is not None and months_left <= 0:
        months_left = 0
    required = (
        required_monthly_contribution(target, saved, months_left, expected_return)
        if months_left and months_left > 0
        else None
    )
    projection = (
        goal_projection(target, saved, monthly, expected_return, months_left)
        if months_left
        else None
    )
    mc = (
        monte_carlo_goal(target, saved, monthly, expected_return, months_left, seed=goal.id or 7)
        if months_left
        else None
    )
    probability = mc["probability"] if mc else None

    if saved >= target:
        status = "achieved"
    elif months_left == 0:
        status = "overdue"
    elif probability is None:
        status = "no_deadline"
    elif probability >= 0.75:
        status = "on_track"
    elif probability >= 0.45:
        status = "at_risk"
    else:
        status = "off_track"

    if required is not None:
        monthly_gap = max(0.0, required - monthly)
    elif target > saved:
        monthly_gap = max(0.0, (target - saved) / 60.0 - monthly)
    else:
        monthly_gap = 0.0

    return {
        "id": goal.id,
        "name": goal.name,
        "category": goal.category,
        "target_amount": money_str(target),
        "saved_amount": money_str(saved),
        "monthly_contribution": money_str(monthly),
        "target_date": goal.target_date.isoformat() if goal.target_date else None,
        "expected_return": expected_return,
        "priority": goal.priority,
        "progress_pct": round(progress, 1),
        "months_left": months_left,
        "required_monthly": money_str(required) if required is not None else None,
        "monthly_gap": money_str(monthly_gap),
        "projected_value": money_str(projection["projected_value"]) if projection else None,
        "shortfall": money_str(projection["shortfall"]) if projection else None,
        "probability": probability,
        "p10": money_str(mc["p10"]) if mc else None,
        "p50": money_str(mc["p50"]) if mc else None,
        "p90": money_str(mc["p90"]) if mc else None,
        "status": status,
        "note": goal.notes,
    }


def goal_overview(user_id: int, as_of: date | None = None) -> dict:
    goals = Goal.query.filter_by(user_id=user_id, archived=False).order_by(Goal.priority, Goal.target_date).all()
    items = [goal_status(g, as_of) for g in goals]
    total_target = sum(float(g["target_amount"]) for g in items)
    total_saved = sum(float(g["saved_amount"]) for g in items)
    monthly = sum(float(g["monthly_contribution"]) for g in items)
    probabilities = [g["probability"] for g in items if g["probability"] is not None]
    return {
        "goals": items,
        "count": len(items),
        "total_target": money_str(total_target),
        "total_saved": money_str(total_saved),
        "monthly_committed": money_str(monthly),
        "overall_progress": round(safe_div(total_saved, total_target) * 100, 1) if total_target else 0.0,
        "average_probability": round(sum(probabilities) / len(probabilities), 3) if probabilities else None,
        "on_track_count": sum(1 for g in items if g["status"] in {"on_track", "achieved"}),
        "at_risk_count": sum(1 for g in items if g["status"] in {"at_risk", "off_track", "overdue"}),
    }


def add_contribution(user_id: int, goal_id: int, amount: float, contribution_date: date, note: str = "") -> GoalContribution:
    goal = Goal.query.filter_by(id=goal_id, user_id=user_id).first()
    if not goal:
        raise ValueError("Goal not found")
    if amount <= 0:
        raise ValueError("Contribution must be positive")
    contribution = GoalContribution(
        goal_id=goal.id,
        amount=Decimal(str(round(amount, 2))),
        contribution_date=contribution_date,
        note=note[:300],
    )
    db.session.add(contribution)
    db.session.commit()
    return contribution


def create_goal(user_id: int, data: dict) -> Goal:
    target = as_float(data.get("target_amount"))
    if target <= 0:
        raise ValueError("Target amount must be positive")
    target_date = data.get("target_date")
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date[:10]) if target_date else None
    goal = Goal(
        user_id=user_id,
        name=str(data.get("name", "New goal")).strip()[:120] or "New goal",
        category=str(data.get("category", "General"))[:40],
        target_amount=Decimal(str(round(target, 2))),
        initial_amount=Decimal(str(round(max(0.0, as_float(data.get("initial_amount"))), 2))),
        monthly_contribution=Decimal(str(round(max(0.0, as_float(data.get("monthly_contribution"))), 2))),
        target_date=target_date,
        expected_return=max(0.0, min(30.0, as_float(data.get("expected_return"), 8.0))),
        priority=max(1, min(3, int(as_float(data.get("priority"), 2)))),
        notes=str(data.get("notes", ""))[:500],
    )
    db.session.add(goal)
    db.session.commit()
    return goal
