"""Cash-flow forecasting with a transparent, reproducible baseline.

The product uses a per-user ridge regression on lagged monthly expenses with
seasonal terms.  With sparse history it falls back to a moving average.  The
research harness benchmarks the same implementation against naive baselines
using rolling-origin evaluation.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..models import Transaction
from ..utils import add_months, as_float, money_str, month_bounds, month_key, today


def monthly_expense_series(user_id: int, months: int = 24, as_of: date | None = None) -> list[dict]:
    """Complete months of total expenses, from the user's first activity."""
    as_of = as_of or today()
    last_complete = add_months(as_of.replace(day=1), -1)
    first_tx = (
        Transaction.query.with_entities(Transaction.transaction_date)
        .filter_by(user_id=user_id)
        .order_by(Transaction.transaction_date.asc())
        .first()
    )
    if not first_tx:
        return []
    first_month = first_tx[0].replace(day=1)
    start = max(first_month, add_months(last_complete, -(months - 1)))
    if start > last_complete:
        return []
    rows = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.kind == "expense",
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= month_bounds(last_complete)[1],
    ).all()
    totals: dict[str, float] = {}
    cursor = start
    while cursor <= last_complete:
        totals[month_key(cursor)] = 0.0
        cursor = add_months(cursor, 1)
    for row in rows:
        key = month_key(row.transaction_date)
        if key in totals:
            totals[key] += float(row.amount)
    series = []
    cursor = start
    while cursor <= last_complete:
        key = month_key(cursor)
        series.append({"month": key, "label": cursor.strftime("%b"), "amount": round(totals[key], 2)})
        cursor = add_months(cursor, 1)
    return series


def _features(history: list[float], target_month: date, index: int) -> list[float]:
    lag1 = history[-1] if len(history) >= 1 else 0.0
    lag2 = history[-2] if len(history) >= 2 else lag1
    lag3 = history[-3] if len(history) >= 3 else lag2
    roll3 = float(np.mean(history[-3:])) if history else 0.0
    roll6 = float(np.mean(history[-6:])) if history else 0.0
    angle = 2 * math.pi * (target_month.month - 1) / 12.0
    return [lag1, lag2, lag3, roll3, roll6, math.sin(angle), math.cos(angle), float(index)]


def _fit_predict(history: list[float], start_month: date, horizon: int) -> tuple[list[float], dict]:
    """Train on all but the last three points and report honest holdout error."""
    n = len(history)
    X, y = [], []
    for i in range(3, n):
        month = add_months(start_month, i)
        X.append(_features(history[:i], month, i))
        y.append(history[i])
    if len(X) < 5:
        return [], {}
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
    model.fit(np.asarray(X), np.asarray(y))
    holdout = min(3, max(1, n // 5))
    train_X, train_y = X[:-holdout], y[:-holdout]
    test_X, test_y = X[-holdout:], y[-holdout:]
    if len(train_X) >= 5:
        hold_model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
        hold_model.fit(np.asarray(train_X), np.asarray(train_y))
        preds = hold_model.predict(np.asarray(test_X))
        errors = np.abs(preds - np.asarray(test_y))
        mae = float(np.mean(errors))
        nonzero = np.asarray(test_y) != 0
        mape = float(np.mean(errors[nonzero] / np.asarray(test_y)[nonzero]) * 100) if nonzero.any() else None
    else:
        mae, mape = None, None
    working = list(history)
    forecasts = []
    for step in range(horizon):
        target_month = add_months(start_month, n + step)
        features = _features(working, target_month, n + step)
        value = float(model.predict(np.asarray([features]))[0])
        value = max(0.0, value)
        forecasts.append(value)
        working.append(value)
    return forecasts, {"mae": round(mae, 2) if mae is not None else None, "mape": round(mape, 1) if mape is not None else None}


def _moving_average_forecast(history: list[float], start_month: date, horizon: int) -> list[float]:
    window = history[-3:] if len(history) >= 3 else history
    base = float(np.mean(window)) if window else 0.0
    forecasts = []
    for step in range(horizon):
        target = add_months(start_month, len(history) + step)
        # If we have a same-month observation from last year, blend it in.
        seasonal = None
        if len(history) >= 12:
            candidate = history[-12 + (step % 12)] if len(history) >= 12 else None
            seasonal = candidate
        value = base * 0.75 + (seasonal if seasonal is not None else base) * 0.25
        forecasts.append(max(0.0, value))
    return forecasts


def forecast_expenses(user_id: int, horizon: int = 3, as_of: date | None = None) -> dict:
    horizon = max(1, min(12, int(horizon)))
    as_of = as_of or today()
    history_rows = monthly_expense_series(user_id, 24, as_of)
    if not history_rows:
        return {
            "horizon": horizon,
            "method": "insufficient_history",
            "confidence": "low",
            "history": [],
            "forecast": [],
            "metrics": {},
            "note": "Add at least three complete months of expenses to generate a forecast.",
        }
    history = [r["amount"] for r in history_rows]
    start_month = date.fromisoformat(history_rows[0]["month"] + "-01")
    last_month = date.fromisoformat(history_rows[-1]["month"] + "-01")

    if len(history) >= 8:
        values, metrics = _fit_predict(history, start_month, horizon)
        method = "ridge_lag_seasonal"
        confidence = "high" if metrics.get("mape") is not None and metrics["mape"] < 15 else "medium"
    elif len(history) >= 3:
        values, metrics = _moving_average_forecast(history, start_month, horizon), {}
        method = "moving_average"
        confidence = "low"
    else:
        base = float(np.mean(history))
        values, metrics = [base] * horizon, {}
        method = "mean"
        confidence = "low"

    residual = float(np.std(history[-6:])) if len(history) >= 4 else float(np.std(history)) if len(history) > 1 else 0.0
    forecasts = []
    for step, value in enumerate(values, start=1):
        month = add_months(last_month, step)
        spread = 1.28 * residual * math.sqrt(step)
        forecasts.append(
            {
                "month": month_key(month),
                "label": month.strftime("%b %y"),
                "amount": money_str(value),
                "low": money_str(max(0.0, value - spread)),
                "high": money_str(value + spread),
            }
        )
    return {
        "horizon": horizon,
        "method": method,
        "confidence": confidence,
        "history": history_rows,
        "forecast": forecasts,
        "metrics": metrics,
        "note": "Forecast of total expenses from your own recorded history. Intervals are approximate 80% ranges.",
        "model_card": {
            "features": ["3 monthly lags", "3- and 6-month rolling means", "month-of-year sin/cos", "time index"],
            "algorithm": "Ridge regression (alpha=1.0), standardised",
            "holdout": "Last 3 observed months, chronological split",
            "fallback": "3-month moving average when fewer than 8 complete months exist",
        },
    }
