"""Deterministic analytics: cash flow, health score, anomalies, recurring series."""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import func

from ..categories import DISCRETIONARY_CATEGORIES, ESSENTIAL_CATEGORIES, normalize_category
from ..extensions import db
from ..models import Asset, Budget, Debt, Goal, Transaction
from ..utils import (
    add_months,
    as_float,
    clamp,
    days_in_month,
    month_bounds,
    month_key,
    month_label,
    money_str,
    normalize_text,
    pct,
    safe_div,
    today,
)


def tx_between(
    user_id: int,
    start: date,
    end: date,
    kind: str | None = None,
) -> list[Transaction]:
    query = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
    )
    if kind:
        query = query.filter(Transaction.kind == kind)
    return query.order_by(Transaction.transaction_date.asc(), Transaction.id.asc()).all()


def _sum(rows: Iterable[Transaction], kind: str) -> Decimal:
    return sum((Decimal(r.amount) for r in rows if r.kind == kind), Decimal("0"))


def _category_totals(rows: Iterable[Transaction], kind: str) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in rows:
        if row.kind == kind:
            totals[row.category] += Decimal(row.amount)
    return dict(totals)


def monthly_summary(user_id: int, month: date) -> dict:
    first, last = month_bounds(month)
    rows = tx_between(user_id, first, last)
    prev_first, prev_last = month_bounds(add_months(first, -1))
    prev_rows = tx_between(user_id, prev_first, prev_last)

    income = _sum(rows, "income")
    expenses = _sum(rows, "expense")
    net = income - expenses
    savings_rate = pct(float(net), float(income)) if income else None

    current = _category_totals(rows, "expense")
    previous = _category_totals(prev_rows, "expense")
    total_expenses = float(expenses) or 1.0
    categories = []
    for category, amount in sorted(current.items(), key=lambda kv: kv[1], reverse=True):
        prev_amount = previous.get(category, Decimal("0"))
        delta = None
        if prev_amount:
            delta = round(float((amount - prev_amount) / prev_amount * 100), 1)
        categories.append(
            {
                "category": category,
                "amount": money_str(amount),
                "share": round(float(amount) / total_expenses * 100, 1),
                "previous_amount": money_str(prev_amount),
                "delta_pct": delta,
            }
        )

    income_categories = [
        {"category": category, "amount": money_str(amount)}
        for category, amount in sorted(_category_totals(rows, "income").items(), key=lambda kv: kv[1], reverse=True)
    ]

    daily: dict[str, dict] = {}
    for day in range(1, days_in_month(first) + 1):
        key = date(first.year, first.month, day).isoformat()
        daily[key] = {"date": key, "income": 0.0, "expenses": 0.0}
    for row in rows:
        bucket = daily.get(row.transaction_date.isoformat())
        if bucket is not None:
            bucket["income" if row.kind == "income" else "expenses"] += float(row.amount)

    top_merchants: dict[str, dict] = {}
    for row in rows:
        if row.kind != "expense":
            continue
        key = (row.description or row.category).strip()[:60]
        item = top_merchants.setdefault(key, {"name": key, "amount": 0.0, "count": 0})
        item["amount"] += float(row.amount)
        item["count"] += 1
    merchants = sorted(top_merchants.values(), key=lambda x: x["amount"], reverse=True)[:5]
    for item in merchants:
        item["amount"] = money_str(item["amount"])

    return {
        "month": month_key(first),
        "label": month_label(first),
        "income": money_str(income),
        "expenses": money_str(expenses),
        "net": money_str(net),
        "savings_rate": savings_rate,
        "expense_categories": categories,
        "income_categories": income_categories,
        "top_merchants": merchants,
        "transaction_count": len(rows),
        "daily": list(daily.values()),
        "days_in_month": days_in_month(first),
        "days_elapsed": min(today().day, days_in_month(first))
        if (first.year, first.month) == (today().year, today().month)
        else days_in_month(first),
    }


def cashflow_series(user_id: int, months: int = 12, end: date | None = None) -> list[dict]:
    end = (end or today()).replace(day=1)
    start = add_months(end, -(months - 1))
    rows = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= month_bounds(end)[1],
    ).all()
    buckets: dict[str, dict] = {}
    cursor = start
    while cursor <= end:
        buckets[month_key(cursor)] = {
            "month": month_key(cursor),
            "label": cursor.strftime("%b"),
            "full_label": month_label(cursor),
            "income": 0.0,
            "expenses": 0.0,
            "net": 0.0,
        }
        cursor = add_months(cursor, 1)
    for row in rows:
        bucket = buckets.get(month_key(row.transaction_date))
        if not bucket:
            continue
        bucket["income" if row.kind == "income" else "expenses"] += float(row.amount)
    series = []
    for bucket in buckets.values():
        bucket["net"] = bucket["income"] - bucket["expenses"]
        bucket["income"] = money_str(bucket["income"])
        bucket["expenses"] = money_str(bucket["expenses"])
        bucket["net"] = money_str(bucket["net"])
        series.append(bucket)
    return series


def _avg_monthly(user_id: int, months: int = 3, kind: str | None = None) -> float:
    """Average over complete months, falling back to the current month."""
    today_ = today()
    totals = []
    for offset in range(1, months + 1):
        first, last = month_bounds(add_months(today_, -offset))
        rows = tx_between(user_id, first, last, kind)
        totals.append(float(_sum(rows, kind)) if kind else float(_sum(rows, "income") - _sum(rows, "expenses")))
    if not any(totals):
        first, last = month_bounds(today_)
        rows = tx_between(user_id, first, last, kind)
        totals = [float(_sum(rows, kind)) if kind else float(_sum(rows, "income") - _sum(rows, "expenses"))]
    return sum(totals) / max(1, len(totals))


def net_worth(user_id: int) -> dict:
    assets = Asset.query.filter_by(user_id=user_id).all()
    debts = Debt.query.filter_by(user_id=user_id).all()
    total_assets = sum((Decimal(a.value) for a in assets), Decimal("0"))
    total_debts = sum((Decimal(d.balance) for d in debts), Decimal("0"))
    liquid = sum((Decimal(a.value) for a in assets if a.is_liquid), Decimal("0"))
    cash = sum((Decimal(a.value) for a in assets if a.asset_type == "cash"), Decimal("0"))
    by_type: dict[str, float] = defaultdict(float)
    for asset in assets:
        by_type[asset.asset_type] += float(asset.value)
    return {
        "assets": money_str(total_assets),
        "debts": money_str(total_debts),
        "net_worth": money_str(total_assets - total_debts),
        "liquid_assets": money_str(liquid),
        "cash_assets": money_str(cash),
        "asset_breakdown": [
            {"type": key, "amount": money_str(value)} for key, value in sorted(by_type.items())
        ],
        "debt_count": len(debts),
        "asset_count": len(assets),
    }


def emergency_fund(user_id: int, as_of: date | None = None) -> dict:
    as_of = as_of or today()
    essential_monthly = 0.0
    for offset in range(1, 4):
        first, last = month_bounds(add_months(as_of, -offset))
        rows = tx_between(user_id, first, last, "expense")
        essential_monthly += float(
            sum((Decimal(r.amount) for r in rows if r.category in ESSENTIAL_CATEGORIES), Decimal("0"))
        )
    essential_monthly /= 3.0
    if essential_monthly == 0:
        essential_monthly = max(1.0, _avg_monthly(user_id, 3, "expense") * 0.6)
    cash = sum(
        (
            Decimal(a.value)
            for a in Asset.query.filter_by(user_id=user_id).all()
            if a.asset_type == "cash"
        ),
        Decimal("0"),
    )
    months_covered = float(cash) / essential_monthly if essential_monthly else 0.0
    target_3 = essential_monthly * 3
    target_6 = essential_monthly * 6
    return {
        "essential_monthly_expenses": money_str(essential_monthly),
        "cash_available": money_str(cash),
        "months_covered": round(months_covered, 2),
        "target_3_months": money_str(target_3),
        "target_6_months": money_str(target_6),
        "gap_to_3_months": money_str(max(0, target_3 - float(cash))),
        "gap_to_6_months": money_str(max(0, target_6 - float(cash))),
        "status": "strong" if months_covered >= 6 else "building" if months_covered >= 3 else "low",
    }


def budget_adherence(user_id: int, month: date) -> tuple[float, int, int]:
    from .budgeting import budget_status

    status = budget_status(user_id, month)
    categories = status["categories"]
    if not categories:
        return 0.5, 0, 0
    on_track = sum(1 for c in categories if c["state"] in {"on_track", "watch"})
    return on_track / len(categories), on_track, len(categories)


def financial_health(user_id: int, as_of: date | None = None) -> dict:
    as_of = as_of or today()
    avg_income = _avg_monthly(user_id, 3, "income")
    avg_expenses = _avg_monthly(user_id, 3, "expense")
    avg_savings = avg_income - avg_expenses
    savings_rate = safe_div(avg_savings, avg_income)
    savings_score = clamp(savings_rate / 0.30) * 25

    ef = emergency_fund(user_id, as_of)
    ef_months = as_float(ef["months_covered"])
    emergency_score = clamp(ef_months / 6.0) * 20

    debts = Debt.query.filter_by(user_id=user_id).all()
    monthly_debt = sum((Decimal(d.minimum_payment) for d in debts), Decimal("0"))
    dti = safe_div(float(monthly_debt), avg_income) if avg_income else 0.0
    debt_score = (1.0 - clamp(dti / 0.40)) * 20
    if not debts:
        debt_score = 18.0

    adherence, on_track, total_budgets = budget_adherence(user_id, as_of)
    budget_score = adherence * 15

    goals = Goal.query.filter_by(user_id=user_id, archived=False).all()
    if goals:
        progress = [clamp(float(g.saved_amount) / float(g.target_amount)) if float(g.target_amount) else 0 for g in goals]
        goal_score = (sum(progress) / len(progress)) * 10
    else:
        goal_score = 5.0

    transactions = Transaction.query.filter_by(user_id=user_id).count()
    completeness = 0
    if transactions >= 10:
        completeness += 4
    if total_budgets:
        completeness += 2
    if goals:
        completeness += 2
    if debts or Asset.query.filter_by(user_id=user_id).count():
        completeness += 2
    completeness_score = float(completeness)

    components = [
        {
            "key": "savings",
            "label": "Savings rate",
            "score": round(savings_score, 1),
            "max": 25,
            "value": f"{round(savings_rate * 100, 1)}%",
            "status": "good" if savings_rate >= 0.20 else "watch" if savings_rate >= 0.10 else "low",
            "explanation": "Share of income left after expenses (trailing 3 months).",
        },
        {
            "key": "emergency",
            "label": "Emergency runway",
            "score": round(emergency_score, 1),
            "max": 20,
            "value": f"{ef_months:.1f} months",
            "status": "good" if ef_months >= 6 else "watch" if ef_months >= 3 else "low",
            "explanation": "Cash reserves divided by essential monthly expenses.",
        },
        {
            "key": "debt",
            "label": "Debt load",
            "score": round(debt_score, 1),
            "max": 20,
            "value": f"{round(dti * 100, 1)}% DTI",
            "status": "good" if dti <= 0.15 else "watch" if dti <= 0.30 else "low",
            "explanation": "Minimum debt payments as a share of monthly income.",
        },
        {
            "key": "budget",
            "label": "Budget adherence",
            "score": round(budget_score, 1),
            "max": 15,
            "value": f"{on_track}/{total_budgets}" if total_budgets else "No budgets",
            "status": "good" if adherence >= 0.75 else "watch" if adherence >= 0.5 else "low",
            "explanation": "Categories currently on or near their planned pace.",
        },
        {
            "key": "goals",
            "label": "Goal progress",
            "score": round(goal_score, 1),
            "max": 10,
            "value": f"{len(goals)} active" if goals else "No goals",
            "status": "good" if goal_score >= 6 else "watch" if goal_score >= 3 else "low",
            "explanation": "Average progress across active savings goals.",
        },
        {
            "key": "completeness",
            "label": "Data completeness",
            "score": round(completeness_score, 1),
            "max": 10,
            "value": f"{transactions} transactions",
            "status": "good" if completeness_score >= 8 else "watch",
            "explanation": "Whether transactions, budgets, goals and assets are tracked.",
        },
    ]
    score = round(sum(c["score"] for c in components), 1)
    grade = "Excellent" if score >= 80 else "Good" if score >= 65 else "Fair" if score >= 45 else "Needs attention"
    top_fix = min(components, key=lambda c: c["score"] / c["max"])
    return {
        "score": score,
        "grade": grade,
        "components": components,
        "top_priority": top_fix["label"],
        "as_of": as_of.isoformat(),
        "trailing": {
            "avg_income": money_str(avg_income),
            "avg_expenses": money_str(avg_expenses),
            "avg_savings": money_str(avg_savings),
            "savings_rate": round(savings_rate * 100, 1),
        },
    }


def _median_mad(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    med = statistics.median(values)
    deviations = [abs(v - med) for v in values]
    mad = statistics.median(deviations) if deviations else 0.0
    return float(med), float(mad)


def detect_anomalies(user_id: int, lookback_days: int = 120) -> list[dict]:
    end = today()
    start = end - timedelta(days=lookback_days)
    history_start = end - timedelta(days=lookback_days + 240)
    history = tx_between(user_id, history_start, start - timedelta(days=1), "expense")
    recent = tx_between(user_id, start, end, "expense")

    by_category: dict[str, list[float]] = defaultdict(list)
    for row in history:
        by_category[row.category].append(float(row.amount))

    anomalies = []
    for row in recent:
        values = by_category.get(row.category, [])
        if len(values) < 5:
            continue
        med, mad = _median_mad(values)
        threshold = med + 3.5 * 1.4826 * max(mad, med * 0.05)
        if float(row.amount) > threshold and float(row.amount) >= 500:
            severity = "high" if float(row.amount) > threshold * 1.6 else "medium"
            anomalies.append(
                {
                    "transaction": row.as_dict(),
                    "category_median": money_str(med),
                    "threshold": money_str(threshold),
                    "multiple": round(float(row.amount) / med, 1) if med else None,
                    "severity": severity,
                    "reason": f"{row.category} spending is well above your usual pattern.",
                }
            )
    return sorted(anomalies, key=lambda a: float(a["transaction"]["amount"]), reverse=True)[:12]


def recurring_candidates(user_id: int, lookback_days: int = 210) -> list[dict]:
    end = today()
    start = end - timedelta(days=lookback_days)
    rows = tx_between(user_id, start, end, "expense")
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for row in rows:
        key = normalize_text(row.description) or row.category.lower()
        groups[key].append(row)

    results = []
    for key, items in groups.items():
        if len(items) < 3:
            continue
        items = sorted(items, key=lambda r: r.transaction_date)
        intervals = [
            (items[i].transaction_date - items[i - 1].transaction_date).days
            for i in range(1, len(items))
        ]
        if not intervals:
            continue
        median_interval = statistics.median(intervals)
        if not (24 <= median_interval <= 38):
            continue
        amounts = [float(i.amount) for i in items]
        amount_med = statistics.median(amounts)
        amount_spread = statistics.pstdev(amounts) / amount_med if amount_med else 1
        if amount_spread > 0.35:
            continue
        last = items[-1]
        next_expected = last.transaction_date + timedelta(days=int(round(median_interval)))
        days_until = (next_expected - end).days
        confidence = clamp(1.0 - abs(median_interval - 30) / 30) * clamp(1.0 - amount_spread)
        category = last.category
        results.append(
            {
                "merchant": last.description or key.title(),
                "category": category,
                "average_amount": money_str(amount_med),
                "monthly_cost": money_str(amount_med),
                "annual_cost": money_str(amount_med * 12),
                "occurrences": len(items),
                "median_interval_days": int(round(median_interval)),
                "last_date": last.transaction_date.isoformat(),
                "next_expected": next_expected.isoformat(),
                "days_until": days_until,
                "confidence": round(float(confidence), 2),
                "is_subscription": category in {"Subscriptions", "Entertainment", "Utilities"},
            }
        )
    return sorted(results, key=lambda r: float(r["monthly_cost"]), reverse=True)


def category_trends(user_id: int, months: int = 6) -> dict:
    end = today().replace(day=1)
    start = add_months(end, -(months - 1))
    rows = tx_between(user_id, start, month_bounds(end)[1], "expense")
    month_list = []
    cursor = start
    while cursor <= end:
        month_list.append(cursor)
        cursor = add_months(cursor, 1)
    keys = [month_key(m) for m in month_list]
    totals: dict[str, dict[str, float]] = defaultdict(lambda: {k: 0.0 for k in keys})
    for row in rows:
        totals[row.category][month_key(row.transaction_date)] += float(row.amount)
    return {
        "months": [{"key": k, "label": month_list[i].strftime("%b")} for i, k in enumerate(keys)],
        "series": [
            {
                "category": category,
                "values": [round(values[k], 2) for k in keys],
                "total": round(sum(values.values()), 2),
            }
            for category, values in sorted(totals.items(), key=lambda kv: sum(kv[1].values()), reverse=True)
        ],
    }


def safe_to_spend(user_id: int, as_of: date | None = None) -> dict:
    from .budgeting import budget_status

    as_of = as_of or today()
    month = as_of.replace(day=1)
    status = budget_status(user_id, month, as_of)
    budgets = [c for c in status["categories"] if c["category"] in DISCRETIONARY_CATEGORIES]
    if not budgets:
        avg_income = _avg_monthly(user_id, 3, "income")
        spent = sum(
            float(Decimal(r.amount))
            for r in tx_between(user_id, month, as_of, "expense")
            if r.category in DISCRETIONARY_CATEGORIES
        )
        allowance = max(0.0, avg_income * 0.20 - spent)
        days_left = max(1, days_in_month(as_of) - as_of.day + 1)
        return {
            "amount": money_str(allowance),
            "daily": money_str(allowance / days_left),
            "days_left": days_left,
            "basis": "income_rule",
            "note": "Based on a 20% discretionary allowance until budgets are set.",
            "categories": [],
        }

    remaining = sum(float(c["remaining"]) for c in budgets)
    upcoming = 0.0
    for series in recurring_candidates(user_id):
        if not series["is_subscription"]:
            continue
        next_date = date.fromisoformat(series["next_expected"])
        if as_of < next_date <= month_bounds(month)[1]:
            upcoming += float(series["monthly_cost"])
    reserve = min(remaining * 0.15, upcoming)
    usable = max(0.0, remaining - reserve)
    days_left = max(1, days_in_month(as_of) - as_of.day + 1)
    return {
        "amount": money_str(usable),
        "daily": money_str(usable / days_left),
        "days_left": days_left,
        "basis": "budget",
        "note": "Remaining discretionary budget, reserving upcoming subscriptions.",
        "categories": [
            {
                "category": c["category"],
                "remaining": c["remaining"],
                "daily": money_str(float(c["remaining"]) / days_left),
            }
            for c in budgets
        ],
    }


def savings_capacity(user_id: int, months: int = 3) -> dict:
    avg_income = _avg_monthly(user_id, 3, "income")
    avg_expenses = _avg_monthly(user_id, 3, "expense")
    avg_savings = avg_income - avg_expenses
    rate = safe_div(avg_savings, avg_income)
    return {
        "avg_monthly_income": money_str(avg_income),
        "avg_monthly_expenses": money_str(avg_expenses),
        "avg_monthly_savings": money_str(avg_savings),
        "savings_rate": round(rate * 100, 1),
        "horizon_months": months,
        "projected_savings": money_str(max(0.0, avg_savings) * months),
        "method": "Average of the last three complete months; falls back to the current month when history is sparse.",
    }


def overview(user_id: int, month: date | None = None) -> dict:
    """Single dashboard payload to keep the UI fast and consistent."""
    from .budgeting import budget_status
    from .goals import goal_overview
    from .nudges import generate_nudges, gamification_summary

    month = (month or today()).replace(day=1)
    summary = monthly_summary(user_id, month)
    budgets = budget_status(user_id, month)
    goals = goal_overview(user_id)
    ef = emergency_fund(user_id)
    health = financial_health(user_id)
    debts = [d.as_dict() for d in Debt.query.filter_by(user_id=user_id).order_by(Debt.apr.desc()).all()]
    assets = [a.as_dict() for a in Asset.query.filter_by(user_id=user_id).all()]
    nudges = generate_nudges(user_id)
    forecast = None
    try:
        from .forecasting import forecast_expenses

        forecast = forecast_expenses(user_id, horizon=3)
    except Exception:  # forecasting must never break the dashboard
        forecast = None
    return {
        "month": summary,
        "cashflow": cashflow_series(user_id, 12, month),
        "budgets": budgets,
        "goals": goals,
        "debts": debts,
        "assets": assets,
        "net_worth": net_worth(user_id),
        "emergency_fund": ef,
        "financial_health": health,
        "safe_to_spend": safe_to_spend(user_id),
        "nudges": nudges,
        "gamification": gamification_summary(user_id),
        "forecast": forecast,
        "recurring": recurring_candidates(user_id)[:8],
        "anomalies": detect_anomalies(user_id)[:5],
    }
