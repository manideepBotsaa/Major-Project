"""Affordability calculus.

Implements and extends the five just-in-time use cases from Ramjattan et al.
(IHTC 2021): luxury affordability, budget tracking, small-transaction
affordability, loan affordability, and savings estimation.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..categories import DISCRETIONARY_CATEGORIES, normalize_category
from ..extensions import db
from ..models import Asset, Goal
from ..utils import as_float, money_str, month_bounds, safe_div, today
from .analytics import (
    emergency_fund,
    net_worth,
    recurring_candidates,
    safe_to_spend,
    savings_capacity,
    tx_between,
)
from .budgeting import budget_status
from .calculators import emi, loan_payoff


def _liquid_cash(user_id: int) -> float:
    assets = Asset.query.filter_by(user_id=user_id).all()
    return sum(float(a.value) for a in assets if a.asset_type == "cash")


def check_affordability(
    user_id: int,
    amount: float,
    category: str | None = None,
    as_of: date | None = None,
    apr: float | None = None,
    months: int | None = None,
    purpose: str | None = None,
) -> dict:
    as_of = as_of or today()
    amount = max(0.0, as_float(amount))
    if amount <= 0:
        raise ValueError("Amount must be positive")
    category = normalize_category(category) if category else "Shopping"
    sts = safe_to_spend(user_id, as_of)
    ef = emergency_fund(user_id, as_of)
    capacity = savings_capacity(user_id, 3)
    cash = _liquid_cash(user_id)
    discretionary_remaining = float(sts["amount"])
    emergency_target = float(ef["target_3_months"])
    emergency_surplus = max(0.0, cash - emergency_target)

    max_from_buffer = max(0.0, cash - emergency_target)
    max_safe = max(0.0, min(discretionary_remaining + max_from_buffer * 0.25, cash - emergency_target * 0.5))
    if amount <= discretionary_remaining * 0.5 and float(ef["months_covered"]) >= 3:
        verdict = "comfortable"
        label = "Comfortably affordable"
    elif amount <= discretionary_remaining and float(ef["months_covered"]) >= 3:
        verdict = "affordable"
        label = "Affordable within this month's plan"
    elif amount <= max_from_buffer and float(ef["months_covered"]) >= 1:
        verdict = "stretch"
        label = "Affordable, but it uses your buffer"
    else:
        verdict = "not_now"
        label = "Not affordable right now"

    monthly_savings = max(1.0, float(capacity["avg_monthly_savings"]))
    wait_months = max(1, int(round(amount / monthly_savings))) if verdict == "not_now" else 0
    alternatives = []
    if verdict == "not_now":
        alternatives.append(
            {
                "option": "Wait and save",
                "detail": f"At your recent saving pace, you could fund this in about {wait_months} months.",
                "impact": "No debt, no dip into your emergency buffer.",
            }
        )
        alternatives.append(
            {
                "option": "Reduce discretionary spending",
                "detail": "Cutting 20% from dining, shopping and entertainment for a few months would close the gap faster.",
                "impact": "Accelerates the purchase without borrowing.",
            }
        )
    if amount > discretionary_remaining > 0:
        alternatives.append(
            {
                "option": "Split across months",
                "detail": f"Your remaining discretionary budget is {money_str(discretionary_remaining)}.",
                "impact": "Keeps this month's budget intact.",
            }
        )

    financing = None
    if apr is not None and months:
        payment = emi(amount, apr, months)
        interest = payment * months - amount
        financing = {
            "apr": round(float(apr), 2),
            "months": int(months),
            "monthly_payment": money_str(payment),
            "total_interest": money_str(max(0.0, interest)),
            "total_cost": money_str(amount + max(0.0, interest)),
            "verdict": "expensive" if interest / amount > 0.10 else "moderate",
        }

    goal_impact = None
    goals = Goal.query.filter_by(user_id=user_id, archived=False).order_by(Goal.priority).all()
    if goals:
        goal = goals[0]
        monthly = max(0.0, float(goal.monthly_contribution))
        delay = amount / monthly if monthly > 0 else None
        goal_impact = {
            "goal": goal.name,
            "monthly_contribution": money_str(monthly),
            "delay_months": round(delay, 1) if delay is not None else None,
            "note": "Approximate delay if the purchase is funded from the money earmarked for this goal."
            if delay is not None
            else "This goal has no monthly contribution yet.",
        }

    subscriptions = [s for s in recurring_candidates(user_id) if s["is_subscription"]]
    return {
        "amount": money_str(amount),
        "category": category,
        "purpose": purpose or "purchase",
        "as_of": as_of.isoformat(),
        "verdict": verdict,
        "label": label,
        "max_safe_amount": money_str(max(0.0, max_safe)),
        "breakdown": {
            "discretionary_remaining": money_str(discretionary_remaining),
            "daily_safe_spend": sts["daily"],
            "cash_available": money_str(cash),
            "emergency_months": ef["months_covered"],
            "emergency_gap_3m": ef["gap_to_3_months"],
            "avg_monthly_savings": capacity["avg_monthly_savings"],
            "emergency_surplus": money_str(emergency_surplus),
            "upcoming_subscriptions": money_str(sum(float(s["monthly_cost"]) for s in subscriptions)),
        },
        "financing": financing,
        "goal_impact": goal_impact,
        "wait_months": wait_months,
        "alternatives": alternatives,
        "assumptions": [
            "Affordability is based on recorded transactions, budgets and cash assets.",
            "The emergency buffer is three months of essential expenses.",
            "Financing cost uses the stated APR and does not include fees or taxes.",
        ],
    }


def small_purchase_affordability(user_id: int, category: str, as_of: date | None = None) -> dict:
    as_of = as_of or today()
    category = normalize_category(category)
    status = budget_status(user_id, as_of.replace(day=1), as_of)
    row = next((c for c in status["categories"] if c["category"] == category), None)
    if not row:
        sts = safe_to_spend(user_id, as_of)
        return {
            "category": category,
            "has_budget": False,
            "daily_allowance": sts["daily"],
            "message": "No category budget is set; using your overall discretionary allowance.",
        }
    return {
        "category": category,
        "has_budget": True,
        "budget": row["amount"],
        "spent": row["spent"],
        "remaining": row["remaining"],
        "days_left": row["days_left"],
        "daily_allowance": row["daily_remaining"],
        "on_track_limit": row["pace_expected"],
        "state": row["state"],
        "message": f"You can spend about {row['daily_remaining']} per day in {category} for the rest of this month.",
    }


def budget_tracking(user_id: int, category: str, as_of: date | None = None) -> dict:
    as_of = as_of or today()
    category = normalize_category(category)
    status = budget_status(user_id, as_of.replace(day=1), as_of)
    row = next((c for c in status["categories"] if c["category"] == category), None)
    if not row:
        return {"category": category, "tracked": False, "message": f"No budget is set for {category} this month."}
    return {
        "category": category,
        "tracked": True,
        "amount": row["amount"],
        "spent": row["spent"],
        "remaining": row["remaining"],
        "expected_by_today": row["pace_expected"],
        "state": row["state"],
        "projected": row["projected"],
        "message": f"{category}: spent {row['spent']} of {row['amount']}; {row['state'].replace('_', ' ')}.",
    }


def savings_estimate(user_id: int, months: int = 1) -> dict:
    months = max(1, int(months))
    capacity = savings_capacity(user_id, 3)
    avg = max(0.0, float(capacity["avg_monthly_savings"]))
    return {
        "months": months,
        "monthly_savings": money_str(avg),
        "estimate": money_str(avg * months),
        "method": capacity["method"],
        "savings_rate": capacity["savings_rate"],
    }


def loan_affordability(
    user_id: int,
    principal: float,
    apr: float,
    monthly_payment: float | None = None,
    as_of: date | None = None,
) -> dict:
    principal = max(0.0, as_float(principal))
    apr = max(0.0, as_float(apr))
    capacity = savings_capacity(user_id, 3)
    if monthly_payment is None:
        monthly_payment = max(0.0, float(capacity["avg_monthly_savings"]) * 0.5)
    monthly_payment = max(0.0, as_float(monthly_payment))
    payoff = loan_payoff(principal, apr, monthly_payment)
    save_monthly = max(1.0, float(capacity["avg_monthly_savings"]))
    wait_months = int(round(principal / save_monthly))
    interest = payoff.get("total_interest") or 0.0
    return {
        "principal": money_str(principal),
        "apr": round(apr, 2),
        "monthly_payment": money_str(monthly_payment),
        "payoff": payoff,
        "wait_and_save_months": wait_months,
        "interest_vs_waiting": money_str(interest),
        "verdict": "affordable" if payoff.get("minimum_payment_ok") and monthly_payment <= save_monthly else "risky",
        "message": (
            f"At {money_str(monthly_payment)} per month, this loan takes {payoff.get('months')} months "
            f"and costs {money_str(interest)} in interest."
            if payoff.get("minimum_payment_ok")
            else "That payment does not cover the monthly interest; the loan would not amortise."
        ),
    }
