"""Dashboard, forecasting, insights and calculator endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from ..errors import body, current_user, error, require_user
from ..services import affordability, analytics, calculators, simulation
from ..utils import as_float, parse_month, today

insights_bp = Blueprint("insights", __name__)


@insights_bp.get("/insights/overview")
@require_user
def overview():
    user = current_user()
    try:
        month = parse_month(request.args.get("month"), today().replace(day=1))
    except ValueError:
        return error("month must use YYYY-MM")
    return jsonify(analytics.overview(user.id, month))


@insights_bp.get("/insights/health")
@require_user
def health():
    return jsonify(analytics.financial_health(current_user().id))


@insights_bp.get("/insights/forecast")
@require_user
def forecast():
    from ..services.forecasting import forecast_expenses

    try:
        horizon = max(1, min(12, int(request.args.get("horizon", 3))))
    except ValueError:
        return error("horizon must be a number")
    return jsonify(forecast_expenses(current_user().id, horizon))


@insights_bp.get("/insights/cashflow")
@require_user
def cashflow():
    try:
        months = max(3, min(36, int(request.args.get("months", 12))))
    except ValueError:
        return error("months must be a number")
    return jsonify({"series": analytics.cashflow_series(current_user().id, months)})


@insights_bp.get("/insights/trends")
@require_user
def trends():
    try:
        months = max(3, min(24, int(request.args.get("months", 6))))
    except ValueError:
        return error("months must be a number")
    return jsonify(analytics.category_trends(current_user().id, months))


@insights_bp.get("/insights/recurring")
@require_user
def recurring():
    return jsonify({"recurring": analytics.recurring_candidates(current_user().id)})


@insights_bp.get("/insights/anomalies")
@require_user
def anomalies():
    return jsonify({"anomalies": analytics.detect_anomalies(current_user().id)})


@insights_bp.get("/insights/net-worth")
@require_user
def net_worth_view():
    return jsonify(analytics.net_worth(current_user().id))


@insights_bp.get("/insights/safe-to-spend")
@require_user
def safe_to_spend():
    return jsonify(analytics.safe_to_spend(current_user().id))


@insights_bp.post("/insights/affordability")
@require_user
def affordability_check():
    """Just-in-time purchase check.

    This is the product-facing counterpart of the advisor's
    ``check_affordability`` tool.  It returns the deterministic verdict,
    arithmetic, financing cost and goal impact without invoking a language
    model, so the same result is available even when the advisor is offline.
    """
    user = current_user()
    data = body()
    amount = as_float(data.get("amount"))
    if amount <= 0:
        return error("amount must be positive")
    apr = data.get("apr")
    months = data.get("months")
    try:
        result = affordability.check_affordability(
            user.id,
            amount,
            category=data.get("category") or "Shopping",
            apr=as_float(apr) if apr not in (None, "") else None,
            months=int(as_float(months)) if months not in (None, "", 0) else None,
            purpose=str(data.get("purpose") or "")[:160] or None,
        )
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(result)


@insights_bp.post("/insights/what-if")
@require_user
def what_if():
    user = current_user()
    data = body()
    try:
        result = simulation.what_if(
            user.id,
            category=data.get("category"),
            reduction_pct=as_float(data.get("reduction_pct"), 0),
            extra_savings=as_float(data.get("extra_savings"), 0),
            extra_debt_payment=as_float(data.get("extra_debt_payment"), 0),
            months=int(as_float(data.get("months"), 12)),
        )
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    return jsonify(result)


# ---------------------------------------------------------------------------
# Calculators (also available to the advisor as tools)
# ---------------------------------------------------------------------------
@insights_bp.post("/calculators/emi")
@require_user
def emi_calculator():
    data = body()
    principal = as_float(data.get("principal"))
    if principal <= 0:
        return error("principal must be positive")
    result = calculators.amortization(
        principal,
        as_float(data.get("annual_rate"), 10),
        max(1, min(480, int(as_float(data.get("months"), 60)))),
    )
    return jsonify(result)


@insights_bp.post("/calculators/sip")
def sip_calculator():
    data = body()
    monthly = as_float(data.get("monthly_investment"))
    if monthly <= 0:
        return error("monthly_investment must be positive")
    return jsonify(
        calculators.sip_future_value(
            monthly,
            as_float(data.get("annual_return"), 12),
            max(0.1, min(50, as_float(data.get("years"), 10))),
            as_float(data.get("step_up_pct"), 0),
        )
    )


@insights_bp.post("/calculators/swp")
def swp_calculator():
    data = body()
    corpus = as_float(data.get("corpus"))
    withdrawal = as_float(data.get("monthly_withdrawal"))
    if corpus <= 0 or withdrawal <= 0:
        return error("corpus and monthly_withdrawal must be positive")
    return jsonify(calculators.swp_projection(corpus, withdrawal, as_float(data.get("annual_return"), 8)))


@insights_bp.post("/calculators/fire")
@require_user
def fire_calculator():
    user = current_user()
    data = body()
    capacity = analytics.savings_capacity(user.id, 3)
    net = analytics.net_worth(user.id)
    annual = as_float(data.get("annual_expenses"), float(capacity["avg_monthly_expenses"]) * 12)
    monthly = as_float(data.get("monthly_savings"), max(0.0, float(capacity["avg_monthly_savings"])))
    if annual <= 0:
        return error("annual_expenses must be positive")
    return jsonify(
        calculators.fire_projection(
            as_float(data.get("current_age"), 30),
            annual,
            as_float(data.get("current_savings"), float(net["liquid_assets"])),
            monthly,
            as_float(data.get("annual_return"), 9),
            as_float(data.get("inflation"), 5),
            as_float(data.get("withdrawal_rate"), 4),
        )
    )


@insights_bp.post("/calculators/compound")
def compound_calculator():
    data = body()
    return jsonify(
        calculators.compound_interest(
            as_float(data.get("principal")),
            as_float(data.get("annual_rate"), 8),
            as_float(data.get("years"), 10),
            int(as_float(data.get("compounds_per_year"), 12)),
        )
    )


@insights_bp.get("/insights/research-summary")
def research_summary():
    path = Path(__file__).resolve().parents[3] / "research" / "results" / "summary.json"
    if not path.exists():
        return jsonify({"available": False, "message": "Run the research harness to generate results."})
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return jsonify({"available": True, **data})
