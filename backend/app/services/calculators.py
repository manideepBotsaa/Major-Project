"""Financial mathematics used by both the product and the research harness.

All functions are pure and unit-tested.  Projections use floats (they are
estimates); ledger amounts elsewhere remain Decimal.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from ..utils import as_float, clamp, money_str, safe_div


def emi(principal: float, annual_rate: float, months: int) -> float:
    principal = max(0.0, as_float(principal))
    months = max(1, int(months))
    monthly_rate = max(0.0, as_float(annual_rate)) / 12.0 / 100.0
    if monthly_rate == 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    return principal * monthly_rate * factor / (factor - 1)


def amortization(principal: float, annual_rate: float, months: int) -> dict:
    principal = max(0.0, as_float(principal))
    months = max(1, int(months))
    monthly_rate = max(0.0, as_float(annual_rate)) / 12.0 / 100.0
    payment = emi(principal, annual_rate, months)
    balance = principal
    total_interest = 0.0
    schedule = []
    for month in range(1, months + 1):
        interest = balance * monthly_rate
        principal_paid = min(balance, payment - interest)
        if principal_paid < 0:
            principal_paid = 0.0
        balance = max(0.0, balance - principal_paid)
        total_interest += interest
        schedule.append(
            {
                "month": month,
                "payment": round(payment, 2),
                "principal": round(principal_paid, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2),
            }
        )
        if balance <= 0.005:
            break
    return {
        "principal": round(principal, 2),
        "annual_rate": round(as_float(annual_rate), 2),
        "months": months,
        "monthly_payment": round(payment, 2),
        "total_payment": round(payment * len(schedule), 2),
        "total_interest": round(total_interest, 2),
        "schedule": schedule,
    }


def sip_future_value(
    monthly_investment: float,
    annual_return: float,
    years: float,
    step_up_pct: float = 0.0,
) -> dict:
    monthly = max(0.0, as_float(monthly_investment))
    annual = as_float(annual_return)
    total_months = max(0, int(round(as_float(years) * 12)))
    monthly_rate = annual / 12.0 / 100.0
    balance = 0.0
    invested = 0.0
    contribution = monthly
    yearly_schedule = []
    for month in range(1, total_months + 1):
        balance = balance * (1 + monthly_rate) + contribution
        invested += contribution
        if month % 12 == 0:
            if step_up_pct:
                contribution *= 1 + as_float(step_up_pct) / 100.0
            yearly_schedule.append(
                {
                    "year": month // 12,
                    "invested": round(invested, 2),
                    "value": round(balance, 2),
                }
            )
    return {
        "monthly_investment": round(monthly, 2),
        "annual_return": round(annual, 2),
        "years": round(as_float(years), 2),
        "months": total_months,
        "invested": round(invested, 2),
        "future_value": round(balance, 2),
        "gains": round(balance - invested, 2),
        "schedule": yearly_schedule,
    }


def swp_projection(corpus: float, monthly_withdrawal: float, annual_return: float) -> dict:
    corpus = max(0.0, as_float(corpus))
    withdrawal = max(0.0, as_float(monthly_withdrawal))
    monthly_rate = as_float(annual_return) / 12.0 / 100.0
    balance = corpus
    months = 0
    total_withdrawn = 0.0
    schedule = []
    while balance > 0 and months < 1200 and withdrawal > 0:
        balance *= 1 + monthly_rate
        taken = min(balance, withdrawal)
        balance -= taken
        total_withdrawn += taken
        months += 1
        if months % 12 == 0:
            schedule.append({"year": months // 12, "balance": round(balance, 2)})
    return {
        "corpus": round(corpus, 2),
        "monthly_withdrawal": round(withdrawal, 2),
        "annual_return": round(as_float(annual_return), 2),
        "months_lasted": months,
        "years_lasted": round(months / 12.0, 1),
        "total_withdrawn": round(total_withdrawn, 2),
        "schedule": schedule,
    }


def fire_projection(
    current_age: float,
    annual_expenses: float,
    current_savings: float,
    monthly_savings: float,
    annual_return: float = 9.0,
    inflation: float = 5.0,
    withdrawal_rate: float = 4.0,
) -> dict:
    current_age = max(15.0, as_float(current_age, 30))
    annual_expenses = max(1.0, as_float(annual_expenses))
    current_savings = max(0.0, as_float(current_savings))
    monthly_savings = max(0.0, as_float(monthly_savings))
    nominal_return = as_float(annual_return) / 100.0
    infl = as_float(inflation) / 100.0
    wr = max(0.005, as_float(withdrawal_rate, 4.0) / 100.0)
    real_return = (1 + nominal_return) / (1 + infl) - 1
    monthly_real = real_return / 12.0

    fi_number_today = annual_expenses / wr
    balance = current_savings
    months = 0
    while months < 12 * 70:
        target_at_month = fi_number_today * (1 + infl) ** (months / 12.0)
        if balance >= target_at_month and monthly_savings >= 0:
            break
        balance = balance * (1 + monthly_real) + monthly_savings
        months += 1
        if monthly_savings == 0 and real_return <= 0:
            months = 12 * 70
            break
    years = months / 12.0
    return {
        "current_age": round(current_age, 1),
        "annual_expenses": round(annual_expenses, 2),
        "fi_number_today": round(fi_number_today, 2),
        "projected_fi_number": round(fi_number_today * (1 + infl) ** years, 2),
        "years_to_fi": round(years, 1),
        "fi_age": round(current_age + years, 1),
        "monthly_savings": round(monthly_savings, 2),
        "real_return": round(real_return * 100, 2),
        "withdrawal_rate": round(wr * 100, 2),
        "reached": months < 12 * 70,
    }


def loan_payoff(balance: float, annual_rate: float, monthly_payment: float, max_months: int = 600) -> dict:
    balance = max(0.0, as_float(balance))
    monthly_rate = max(0.0, as_float(annual_rate)) / 12.0 / 100.0
    payment = max(0.0, as_float(monthly_payment))
    if balance == 0:
        return {
            "months": 0, "years": 0.0, "total_interest": 0.0, "total_paid": 0.0,
            "minimum_payment_ok": True, "schedule": [],
        }
    if payment <= balance * monthly_rate:
        minimum = balance * monthly_rate + 1.0
        return {
            "months": None,
            "years": None,
            "total_interest": None,
            "total_paid": None,
            "minimum_payment_ok": False,
            "required_minimum": round(minimum, 2),
            "schedule": [],
            "note": "The payment does not cover monthly interest, so the balance would never be repaid.",
        }
    remaining = balance
    total_interest = 0.0
    schedule = []
    month = 0
    while remaining > 0.005 and month < max_months:
        month += 1
        interest = remaining * monthly_rate
        principal = min(remaining, payment - interest)
        remaining -= principal
        total_interest += interest
        schedule.append(
            {
                "month": month,
                "payment": round(payment if remaining > 0.005 else principal + interest, 2),
                "principal": round(principal, 2),
                "interest": round(interest, 2),
                "balance": round(max(0.0, remaining), 2),
            }
        )
    return {
        "months": month,
        "years": round(month / 12.0, 1),
        "total_interest": round(total_interest, 2),
        "total_paid": round(balance + total_interest, 2),
        "minimum_payment_ok": True,
        "required_minimum": round(balance * monthly_rate + 1.0, 2),
        "schedule": schedule,
    }


def _debt_simulation(debts: list[dict], extra_payment: float, strategy: str) -> dict:
    working = [
        {
            "name": d.get("name", "Debt"),
            "balance": max(0.0, as_float(d.get("balance"))),
            "apr": max(0.0, as_float(d.get("apr"))),
            "minimum": max(0.0, as_float(d.get("minimum_payment") or d.get("minimum"))),
        }
        for d in debts
    ]
    working = [d for d in working if d["balance"] > 0]
    if not working:
        return {
            "strategy": strategy, "months": 0, "years": 0.0, "total_interest": 0.0,
            "total_paid": 0.0, "order": [], "schedule": [], "monthly_outlay": 0.0,
        }
    order = sorted(
        working,
        key=(lambda d: (-d["apr"], d["balance"])) if strategy == "avalanche" else (lambda d: (d["balance"], -d["apr"])),
    )
    order_names = [d["name"] for d in order]
    by_name = {d["name"]: d for d in working}
    total_interest = 0.0
    total_paid = 0.0
    month = 0
    history = []
    original_balance = sum(d["balance"] for d in working)
    max_months = 600

    while any(d["balance"] > 0.005 for d in working) and month < max_months:
        month += 1
        month_interest = 0.0
        for debt in working:
            if debt["balance"] <= 0:
                continue
            interest = debt["balance"] * debt["apr"] / 12.0 / 100.0
            debt["balance"] += interest
            month_interest += interest
            pay = min(debt["balance"], debt["minimum"])
            debt["balance"] -= pay
            total_paid += pay
        freed = sum(
            d["minimum"] for d in working if d["balance"] <= 0.005
        )
        available_extra = max(0.0, extra_payment) + freed
        for name in order_names:
            if available_extra <= 0:
                break
            debt = by_name[name]
            if debt["balance"] <= 0:
                continue
            pay = min(debt["balance"], available_extra)
            debt["balance"] -= pay
            available_extra -= pay
            total_paid += pay
        total_interest += month_interest
        if month <= 120 or month % 12 == 0:
            history.append(
                {
                    "month": month,
                    "balance": round(sum(d["balance"] for d in working), 2),
                    "interest_paid": round(total_interest, 2),
                }
            )
    monthly_outlay = sum(d["minimum"] for d in working) + max(0.0, extra_payment)
    return {
        "strategy": strategy,
        "months": month,
        "years": round(month / 12.0, 1),
        "total_interest": round(total_interest, 2),
        "total_paid": round(total_paid, 2),
        "original_balance": round(original_balance, 2),
        "monthly_outlay": round(monthly_outlay, 2),
        "order": order_names,
        "schedule": history,
    }


def debt_plan(debts: Iterable[dict], extra_payment: float = 0.0) -> dict:
    debts = list(debts)
    avalanche = _debt_simulation(debts, extra_payment, "avalanche")
    snowball = _debt_simulation(debts, extra_payment, "snowball")
    baseline = _debt_simulation(debts, 0.0, "avalanche")
    return {
        "avalanche": avalanche,
        "snowball": snowball,
        "baseline": baseline,
        "extra_payment": round(max(0.0, as_float(extra_payment)), 2),
        "interest_saved_vs_baseline": round(
            max(0.0, (baseline["total_interest"] or 0) - (avalanche["total_interest"] or 0)), 2
        ),
        "months_saved_vs_baseline": max(0, (baseline["months"] or 0) - (avalanche["months"] or 0)),
    }


def required_monthly_contribution(
    target: float,
    current: float,
    months: int,
    annual_return: float = 0.0,
) -> float:
    target = max(0.0, as_float(target))
    current = max(0.0, as_float(current))
    months = max(1, int(months))
    monthly_rate = as_float(annual_return) / 12.0 / 100.0
    if current >= target:
        return 0.0
    future_current = current * (1 + monthly_rate) ** months
    gap = target - future_current
    if monthly_rate == 0:
        return gap / months
    annuity_factor = ((1 + monthly_rate) ** months - 1) / monthly_rate
    return gap / annuity_factor


def goal_projection(
    target: float,
    current: float,
    monthly_contribution: float,
    annual_return: float,
    months: int,
) -> dict:
    target = max(0.0, as_float(target))
    current = max(0.0, as_float(current))
    monthly = max(0.0, as_float(monthly_contribution))
    monthly_rate = as_float(annual_return) / 12.0 / 100.0
    months = max(1, int(months))
    balance = current
    invested = current
    for _ in range(months):
        balance = balance * (1 + monthly_rate) + monthly
        invested += monthly
    shortfall = max(0.0, target - balance)
    return {
        "projected_value": round(balance, 2),
        "target": round(target, 2),
        "contributed": round(invested, 2),
        "gains": round(balance - invested, 2),
        "shortfall": round(shortfall, 2),
        "funded_pct": round(clamp(safe_div(balance, target)) * 100, 1),
        "required_monthly": round(required_monthly_contribution(target, current, months, annual_return), 2),
    }


def compound_interest(principal: float, annual_rate: float, years: float, compounds_per_year: int = 12) -> dict:
    p = max(0.0, as_float(principal))
    r = as_float(annual_rate) / 100.0
    n = max(1, int(compounds_per_year))
    t = max(0.0, as_float(years))
    amount = p * (1 + r / n) ** (n * t)
    return {
        "principal": round(p, 2),
        "amount": round(amount, 2),
        "interest": round(amount - p, 2),
        "effective_annual_rate": round(((1 + r / n) ** n - 1) * 100, 2),
    }
