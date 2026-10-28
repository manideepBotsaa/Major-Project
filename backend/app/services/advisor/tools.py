"""Typed financial tools.

Every number in a user-facing answer originates here.  The language model can
choose which tool to call and how to explain the result, but it cannot execute
SQL, invent figures, or bypass these calculations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Callable

from ...categories import CURRENCY_SYMBOLS, normalize_category
from ...models import Debt, Goal, Transaction
from ...utils import (
    add_months,
    as_float,
    money_str,
    month_key,
    parse_amount,
    parse_duration_months,
    parse_month,
    parse_percent,
    today,
)
from .. import analytics, affordability, budgeting, calculators, forecasting, goals as goals_service, simulation
from ..literacy import search_knowledge


@dataclass
class ToolResult:
    tool: str
    label: str
    args: dict
    headline: str
    display: list[str] = field(default_factory=list)
    interpretation: str = ""
    facts: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    knowledge: list[dict] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "tool": self.tool,
            "label": self.label,
            "args": self.args,
            "headline": self.headline,
            "display": self.display,
            "interpretation": self.interpretation,
            "facts": self.facts,
            "assumptions": self.assumptions,
            "knowledge": self.knowledge,
            "error": self.error,
        }


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable


def _symbol(user) -> str:
    return CURRENCY_SYMBOLS.get(user.currency or "INR", "₹")


def _indian_group(value: float) -> str:
    negative = value < 0
    whole = f"{abs(value):.0f}"
    if len(whole) <= 3:
        grouped = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3
    return ("-" if negative else "") + grouped


def fmt_money(user, value: Any, decimals: bool = False) -> str:
    number = as_float(value)
    symbol = _symbol(user)
    if number == 0:
        return f"{symbol}0"
    if abs(number) < 1000 and not float(number).is_integer():
        return f"{symbol}{number:,.2f}"
    if decimals and abs(number) < 100000:
        return f"{symbol}{number:,.2f}"
    return f"{symbol}{_indian_group(number)}"


def fmt_pct(value: Any, digits: int = 1) -> str:
    return f"{round(as_float(value), digits)}%"


def _knowledge(query: str, k: int = 1) -> list[dict]:
    try:
        return search_knowledge(query, k)
    except Exception:
        return []


def _month_arg(args: dict, as_of: date) -> date:
    raw = args.get("month")
    if raw:
        try:
            return parse_month(raw, as_of.replace(day=1))
        except Exception:
            pass
    return as_of.replace(day=1)


def _overview(user, args, as_of):
    month = _month_arg(args, as_of)
    summary = analytics.monthly_summary(user.id, month)
    health = analytics.financial_health(user.id, as_of)
    safe = analytics.safe_to_spend(user.id, as_of)
    net = float(summary["net"])
    headline = f"Your net cash flow for {summary['label']} is {fmt_money(user, net)}."
    display = [
        f"Income: {fmt_money(user, summary['income'])}",
        f"Expenses: {fmt_money(user, summary['expenses'])}",
        f"Savings rate: {fmt_pct(summary['savings_rate']) if summary['savings_rate'] is not None else 'not available'}",
        f"Financial health score: {health['score']}/100 ({health['grade']})",
        f"Safe to spend for the rest of this month: {fmt_money(user, safe['amount'])}",
    ]
    if summary["expense_categories"]:
        top = summary["expense_categories"][0]
        display.append(f"Largest expense category: {top['category']} at {fmt_money(user, top['amount'])}")
    if net < 0:
        interpretation = "You spent more than you earned this month. The fastest fix is usually one large discretionary category, not ten small cuts."
    elif summary["savings_rate"] is not None and summary["savings_rate"] < 10:
        interpretation = "You are cash-flow positive, but the margin is thin. A 10% savings rate is a more resilient target than simply avoiding a deficit."
    else:
        interpretation = "You are cash-flow positive. Direct part of this surplus to a goal or an emergency buffer before it gets absorbed by everyday spending."
    return ToolResult(
        tool="financial_overview",
        label="Monthly overview",
        args={"month": month_key(month)},
        headline=headline,
        display=display,
        interpretation=interpretation,
        facts={
            "month": summary["month"],
            "income": summary["income"],
            "expenses": summary["expenses"],
            "net": summary["net"],
            "savings_rate": summary["savings_rate"],
            "health_score": health["score"],
            "safe_to_spend": safe["amount"],
        },
        assumptions=["Based on recorded transactions for the selected month."],
        knowledge=_knowledge("cash flow budgeting savings rate", 1),
    )


def _category_spending(user, args, as_of):
    month = _month_arg(args, as_of)
    summary = analytics.monthly_summary(user.id, month)
    limit = max(1, min(10, int(as_float(args.get("limit"), 5))))
    categories = summary["expense_categories"][:limit]
    if not categories:
        return ToolResult(
            tool="category_spending",
            label="Category spending",
            args={"month": month_key(month)},
            headline=f"There are no recorded expenses for {summary['label']}.",
            display=[],
            interpretation="Add or import transactions and I can break them down by category.",
            facts={"month": summary["month"], "expense_categories": []},
            knowledge=_knowledge("tracking expenses categories", 1),
        )
    top = categories[0]
    display = []
    for row in categories:
        delta = ""
        if row["delta_pct"] is not None:
            direction = "up" if row["delta_pct"] >= 0 else "down"
            delta = f", {direction} {fmt_pct(abs(row['delta_pct']))} vs last month"
        display.append(f"{row['category']}: {fmt_money(user, row['amount'])} ({fmt_pct(row['share'])} of spending{delta})")
    interpretation = (
        f"{top['category']} is {fmt_pct(top['share'])} of your spending in {summary['label']}. "
        "A useful test is whether that share matches what you would choose deliberately, not what happens by default."
    )
    return ToolResult(
        tool="category_spending",
        label="Category spending",
        args={"month": month_key(month), "limit": limit},
        headline=f"Your largest expense category in {summary['label']} was {top['category']} at {fmt_money(user, top['amount'])}.",
        display=display,
        interpretation=interpretation,
        facts={"month": summary["month"], "expense_categories": categories, "total_expenses": summary["expenses"]},
        knowledge=_knowledge("spending categories budget", 1),
    )


def _budget_status(user, args, as_of):
    month = _month_arg(args, as_of)
    status = budgeting.budget_status(user.id, month, as_of)
    if not status["categories"]:
        return ToolResult(
            tool="budget_status",
            label="Budget status",
            args={"month": month_key(month)},
            headline=f"No budgets are set for {status['label']}.",
            display=[f"Unbudgeted spending so far: {fmt_money(user, status['unbudgeted'][0]['spent']) if status['unbudgeted'] else fmt_money(user, 0)}"],
            interpretation="Budgets turn a vague intention into a daily allowance. Start with your three largest categories.",
            facts={"month": status["month"], "total_budget": status["total_budget"], "categories": []},
            knowledge=_knowledge("how to make a budget", 1),
        )
    display = []
    for row in status["categories"]:
        display.append(
            f"{row['category']}: {fmt_money(user, row['spent'])} of {fmt_money(user, row['amount'])} "
            f"({fmt_pct(row['used_pct'])} used, {row['state'].replace('_', ' ')})"
        )
    headline = (
        f"You have used {fmt_money(user, status['total_spent'])} of your {fmt_money(user, status['total_budget'])} "
        f"monthly budget."
    )
    interpretation = (
        f"{status['over_count']} categories are over budget and {status['watch_count']} are at risk. "
        "The daily remaining amounts are the actionable number; the total is just the scoreboard."
    )
    return ToolResult(
        tool="budget_status",
        label="Budget status",
        args={"month": month_key(month)},
        headline=headline,
        display=display[:8],
        interpretation=interpretation,
        facts={
            "month": status["month"],
            "total_budget": status["total_budget"],
            "total_spent": status["total_spent"],
            "total_remaining": status["total_remaining"],
            "over_count": status["over_count"],
            "watch_count": status["watch_count"],
            "categories": status["categories"],
        },
        assumptions=["Budget pace compares spending to the fraction of the month elapsed."],
        knowledge=_knowledge("budget pacing categories", 1),
    )


def _safe_to_spend(user, args, as_of):
    data = analytics.safe_to_spend(user.id, as_of)
    headline = f"You can safely spend about {fmt_money(user, data['amount'])} for the rest of this month."
    display = [
        f"Daily allowance: {fmt_money(user, data['daily'])} for {data['days_left']} days",
        f"Basis: {data['note']}",
    ]
    for row in data.get("categories", [])[:6]:
        display.append(f"{row['category']}: {fmt_money(user, row['remaining'])} left, or {fmt_money(user, row['daily'])} per day")
    return ToolResult(
        tool="safe_to_spend",
        label="Safe to spend",
        args={},
        headline=headline,
        display=display,
        interpretation="This is a spending ceiling, not a target. Unspent money is what funds your goals.",
        facts=data,
        assumptions=["Upcoming detected subscriptions are reserved where possible."],
        knowledge=_knowledge("spending plan discretionary budget", 1),
    )


def _check_affordability(user, args, as_of):
    amount = as_float(args.get("amount"))
    if amount <= 0:
        raise ValueError("A positive purchase amount is required")
    category = args.get("category")
    apr = as_float(args.get("apr")) if args.get("apr") is not None else None
    months = int(as_float(args.get("months"))) if args.get("months") else None
    result = affordability.check_affordability(
        user.id, amount, category=category, as_of=as_of, apr=apr, months=months
    )
    headline = f"{result['label']}: {fmt_money(user, amount)}."
    display = [
        f"Remaining discretionary budget: {fmt_money(user, result['breakdown']['discretionary_remaining'])}",
        f"Cash available: {fmt_money(user, result['breakdown']['cash_available'])}",
        f"Emergency runway: {result['breakdown']['emergency_months']} months",
        f"Maximum comfortable spend right now: {fmt_money(user, result['max_safe_amount'])}",
    ]
    if result["financing"]:
        display.append(
            f"If financed at {fmt_pct(result['financing']['apr'])} for {result['financing']['months']} months: "
            f"{fmt_money(user, result['financing']['monthly_payment'])} per month and "
            f"{fmt_money(user, result['financing']['total_interest'])} in interest."
        )
    if result["goal_impact"] and result["goal_impact"]["delay_months"]:
        display.append(
            f"Impact on {result['goal_impact']['goal']}: about {result['goal_impact']['delay_months']} months of delay."
        )
    alternatives = [f"{a['option']}: {a['detail']}" for a in result["alternatives"]]
    interpretation = result["label"] + ". " + (" ".join(alternatives) if alternatives else "It fits within this month's plan without touching your emergency buffer.")
    return ToolResult(
        tool="check_affordability",
        label="Purchase affordability",
        args={"amount": amount, "category": category, "apr": apr, "months": months},
        headline=headline,
        display=display,
        interpretation=interpretation,
        facts=result,
        assumptions=result["assumptions"],
        knowledge=_knowledge("emergency fund large purchase", 2),
    )


def _savings_capacity(user, args, as_of):
    months = max(1, min(24, int(as_float(args.get("months"), 3))))
    data = analytics.savings_capacity(user.id, months)
    return ToolResult(
        tool="savings_capacity",
        label="Savings capacity",
        args={"months": months},
        headline=f"Your recent saving pace is about {fmt_money(user, data['avg_monthly_savings'])} per month.",
        display=[
            f"Average monthly income: {fmt_money(user, data['avg_monthly_income'])}",
            f"Average monthly expenses: {fmt_money(user, data['avg_monthly_expenses'])}",
            f"Savings rate: {fmt_pct(data['savings_rate'])}",
            f"Projected savings over {months} months: {fmt_money(user, data['projected_savings'])}",
        ],
        interpretation="This is a capacity estimate, not a commitment. Automating the transfer on payday is what turns capacity into savings.",
        facts=data,
        assumptions=[data["method"]],
        knowledge=_knowledge("saving money automatically", 1),
    )


def _savings_estimate(user, args, as_of):
    months = max(1, min(60, int(as_float(args.get("months"), 1))))
    data = affordability.savings_estimate(user.id, months)
    return ToolResult(
        tool="savings_estimate",
        label="Savings estimate",
        args={"months": months},
        headline=f"At your recent pace, you could save about {fmt_money(user, data['estimate'])} in {months} months.",
        display=[
            f"Average monthly savings: {fmt_money(user, data['monthly_savings'])}",
            f"Savings rate: {fmt_pct(data['savings_rate'])}",
        ],
        interpretation=data["method"],
        facts=data,
        assumptions=["Assumes income and spending stay at the recent three-month average."],
        knowledge=_knowledge("savings estimate emergency fund", 1),
    )


def _small_purchase(user, args, as_of):
    category = args.get("category") or "Food & Dining"
    data = affordability.small_purchase_affordability(user.id, category, as_of)
    return ToolResult(
        tool="small_purchase_affordability",
        label="Small purchase allowance",
        args={"category": category},
        headline=data["message"],
        display=[
            f"Budget: {fmt_money(user, data.get('budget', 0))}",
            f"Spent: {fmt_money(user, data.get('spent', 0))}",
            f"Remaining: {fmt_money(user, data.get('remaining', 0))}",
            f"Days left: {data.get('days_left', '—')}",
        ],
        interpretation="Use the daily allowance as a guardrail, not a quota to exhaust.",
        facts=data,
        knowledge=_knowledge("daily spending allowance", 1),
    )


def _budget_tracking(user, args, as_of):
    category = args.get("category") or "Food & Dining"
    data = affordability.budget_tracking(user.id, category, as_of)
    return ToolResult(
        tool="budget_tracking",
        label="Budget tracking",
        args={"category": category},
        headline=data["message"],
        display=[
            f"Budget: {fmt_money(user, data.get('amount', 0))}",
            f"Spent: {fmt_money(user, data.get('spent', 0))}",
            f"Expected by today: {fmt_money(user, data.get('expected_by_today', 0))}",
            f"Projected month-end: {fmt_money(user, data.get('projected', 0))}",
        ],
        interpretation="If actual spending is above the expected-by-today line, the category needs attention now rather than on the 30th.",
        facts=data,
        knowledge=_knowledge("budget tracking pace", 1),
    )


def _goal_status(user, args, as_of):
    overview = goals_service.goal_overview(user.id, as_of)
    items = overview["goals"]
    name = (args.get("goal") or "").strip().lower()
    if name:
        items = [g for g in items if name in g["name"].lower()] or items
    if not items:
        return ToolResult(
            tool="goal_status",
            label="Goal status",
            args={"goal": name or None},
            headline="You have no active savings goals yet.",
            display=[],
            interpretation="A goal gives every spending decision a reference point. Start with an emergency buffer and one meaningful purchase.",
            facts={"goals": []},
            knowledge=_knowledge("setting savings goals", 1),
        )
    display = []
    for goal in items[:5]:
        probability = f", {round((goal['probability'] or 0) * 100)}% estimated success" if goal["probability"] is not None else ""
        display.append(
            f"{goal['name']}: {fmt_money(user, goal['saved_amount'])} of {fmt_money(user, goal['target_amount'])} "
            f"({fmt_pct(goal['progress_pct'])}{probability}); {fmt_money(user, goal['monthly_contribution'])} per month"
        )
    headline = (
        f"You have {overview['count']} active goals, with {fmt_money(user, overview['total_saved'])} saved "
        f"toward {fmt_money(user, overview['total_target'])}."
    )
    interpretation = (
        f"{overview['on_track_count']} goals look on track and {overview['at_risk_count']} need attention. "
        "The probability is a Monte Carlo estimate based on your current contribution and an assumed return."
    )
    return ToolResult(
        tool="goal_status",
        label="Goal status",
        args={"goal": name or None},
        headline=headline,
        display=display,
        interpretation=interpretation,
        facts=overview,
        assumptions=["Goal probabilities assume normally distributed returns and are not guarantees."],
        knowledge=_knowledge("savings goal planning", 1),
    )


def _debt_payoff(user, args, as_of):
    extra = max(0.0, as_float(args.get("extra_payment")))
    debts = Debt.query.filter_by(user_id=user.id).all()
    if not debts:
        return ToolResult(
            tool="debt_payoff",
            label="Debt payoff",
            args={"extra_payment": extra},
            headline="You have no recorded debts.",
            display=[],
            interpretation="Keeping it that way is a competitive advantage. Avoid new high-interest debt for discretionary purchases.",
            facts={"debts": [], "avalanche": None},
            knowledge=_knowledge("avoiding high interest debt", 1),
        )
    payload = [
        {
            "name": d.name,
            "balance": float(d.balance),
            "apr": float(d.apr),
            "minimum_payment": float(d.minimum_payment),
        }
        for d in debts
    ]
    plan = calculators.debt_plan(payload, extra)
    avalanche = plan["avalanche"]
    baseline = plan["baseline"]
    total_minimum = sum(d["minimum_payment"] for d in payload)
    suggested_extra = round(total_minimum * 0.15 / 100.0) * 100
    suggested = calculators.debt_plan(payload, suggested_extra) if suggested_extra > 0 else plan
    display = [
        f"Total balance: {fmt_money(user, sum(d['balance'] for d in payload))}",
        f"Debt-free in: {avalanche['months']} months ({avalanche['years']} years)",
        f"Total interest: {fmt_money(user, avalanche['total_interest'])}",
        f"Interest saved with {fmt_money(user, extra)} extra per month: {fmt_money(user, plan['interest_saved_vs_baseline'])}",
        f"Adding {fmt_money(user, suggested_extra)} per month would save a further "
        f"{fmt_money(user, max(0.0, (avalanche['total_interest'] or 0) - (suggested['avalanche']['total_interest'] or 0)))} in interest.",        "Avalanche order: " + " → ".join(avalanche["order"]),
    ]
    interpretation = (
        "Avalanche (highest APR first) minimizes interest. Snowball (smallest balance first) can be more motivating; "
        f"the difference here is {fmt_money(user, max(0, avalanche['total_interest'] - plan['snowball']['total_interest']))} in interest."
    )
    return ToolResult(
        tool="debt_payoff",
        label="Debt payoff plan",
        args={"extra_payment": extra},
        headline=f"At your minimum payments, debt-free in about {avalanche['months']} months; extra payments shorten that.",
        display=display,
        interpretation=interpretation,
        facts={"plan": plan, "debts": payload, "suggested_extra": suggested_extra},
        assumptions=["APR is constant, payments are made on time, and no new debt is added."],
        knowledge=_knowledge("debt avalanche snowball interest", 2),
    )


def _emergency_fund(user, args, as_of):
    data = analytics.emergency_fund(user.id, as_of)
    return ToolResult(
        tool="emergency_fund",
        label="Emergency fund",
        args={},
        headline=f"Your cash covers about {data['months_covered']} months of essential expenses.",
        display=[
            f"Essential monthly expenses: {fmt_money(user, data['essential_monthly_expenses'])}",
            f"Cash available: {fmt_money(user, data['cash_available'])}",
            f"Three-month target: {fmt_money(user, data['target_3_months'])}",
            f"Six-month target: {fmt_money(user, data['target_6_months'])}",
            f"Gap to three months: {fmt_money(user, data['gap_to_3_months'])}",
        ],
        interpretation=(
            "Three months is a reasonable first milestone; six months is sturdier for variable income. "
            "Keep this money in cash, not equity."
        ),
        facts=data,
        knowledge=_knowledge("emergency fund", 1),
    )


def _forecast(user, args, as_of):
    horizon = max(1, min(6, int(as_float(args.get("horizon"), 3))))
    data = forecasting.forecast_expenses(user.id, horizon=horizon, as_of=as_of)
    if not data["forecast"]:
        return ToolResult(
            tool="forecast_expenses",
            label="Expense forecast",
            args={"horizon": horizon},
            headline=data["note"],
            display=[],
            interpretation="Three complete months of expense history are enough to produce a first forecast.",
            facts=data,
            knowledge=_knowledge("forecasting expenses", 1),
        )
    display = [
        f"{row['label']}: {fmt_money(user, row['amount'])} (range {fmt_money(user, row['low'])}–{fmt_money(user, row['high'])})"
        for row in data["forecast"]
    ]
    first = data["forecast"][0]
    interpretation = (
        f"The first projected month is {fmt_money(user, first['amount'])}. "
        "The range matters more than the point estimate when you are planning a budget."
    )
    if data["metrics"].get("mape") is not None:
        interpretation += f" Backtest error on recent months: {fmt_pct(data['metrics']['mape'])}."
    return ToolResult(
        tool="forecast_expenses",
        label="Expense forecast",
        args={"horizon": horizon},
        headline=f"Next month's expenses are projected at about {fmt_money(user, first['amount'])}.",
        display=display,
        interpretation=interpretation,
        facts=data,
        assumptions=["The forecast uses your own history; it does not predict one-off life events."],
        knowledge=_knowledge("forecasting variable expenses", 1),
    )


def _recurring(user, args, as_of):
    rows = analytics.recurring_candidates(user.id)
    subscriptions = [r for r in rows if r["is_subscription"]]
    annual = sum(float(r["annual_cost"]) for r in subscriptions)
    display = [
        f"{r['merchant']}: {fmt_money(user, r['monthly_cost'])} per month, next around {r['next_expected']}"
        for r in subscriptions[:8]
    ]
    return ToolResult(
        tool="recurring_subscriptions",
        label="Recurring subscriptions",
        args={},
        headline=f"I found {len(subscriptions)} likely subscriptions costing about {fmt_money(user, annual)} a year.",
        display=display,
        interpretation="Recurring charges are small individually and large collectively. Review the ones you have not used in the last month.",
        facts={"count": len(subscriptions), "annual_cost": money_str(annual), "subscriptions": subscriptions},
        assumptions=["Detected from repeated descriptions and stable monthly intervals; false positives are possible."],
        knowledge=_knowledge("subscription audit", 1),
    )


def _anomalies(user, args, as_of):
    rows = analytics.detect_anomalies(user.id)
    display = [
        f"{r['transaction']['description'] or r['transaction']['category']}: {fmt_money(user, r['transaction']['amount'])} "
        f"on {r['transaction']['date']} ({r['multiple']}x your typical {r['transaction']['category']} spend)"
        for r in rows[:5]
    ]
    return ToolResult(
        tool="anomalies",
        label="Unusual spending",
        args={},
        headline=f"I found {len(rows)} unusual expenses in the recent period.",
        display=display,
        interpretation="An anomaly is not automatically a mistake. It is a prompt to check whether the expense was deliberate.",
        facts={"count": len(rows), "anomalies": rows},
        assumptions=["Anomalies are robust z-scores against your own category history."],
        knowledge=_knowledge("irregular expenses", 1),
    )


def _health(user, args, as_of):
    data = analytics.financial_health(user.id, as_of)
    display = [
        f"{c['label']}: {c['score']}/{c['max']} ({c['value']})" for c in data["components"]
    ]
    return ToolResult(
        tool="financial_health",
        label="Financial health",
        args={},
        headline=f"Your financial health score is {data['score']}/100 ({data['grade']}).",
        display=display,
        interpretation=f"The biggest opportunity is {data['top_priority']}. The score is a transparent composite, not a credit score.",
        facts=data,
        assumptions=["The score weights savings, emergency runway, debt load, budget adherence, goals and data completeness."],
        knowledge=_knowledge("financial health savings rate", 1),
    )


def _net_worth(user, args, as_of):
    data = analytics.net_worth(user.id)
    display = [
        f"Assets: {fmt_money(user, data['assets'])}",
        f"Debts: {fmt_money(user, data['debts'])}",
        f"Liquid assets: {fmt_money(user, data['liquid_assets'])}",
        f"Cash: {fmt_money(user, data['cash_assets'])}",
    ]
    return ToolResult(
        tool="net_worth",
        label="Net worth",
        args={},
        headline=f"Your recorded net worth is {fmt_money(user, data['net_worth'])}.",
        display=display,
        interpretation="Net worth is a stock, not a score. The direction over time matters more than today's snapshot.",
        facts=data,
        assumptions=["Only assets and debts entered in Clearpath are included."],
        knowledge=_knowledge("net worth assets liabilities", 1),
    )


def _calculate_emi(user, args, as_of):
    principal = as_float(args.get("principal") or args.get("amount"))
    rate = as_float(args.get("annual_rate") if args.get("annual_rate") is not None else args.get("apr"), 10)
    months = int(as_float(args.get("months"), 60))
    if principal <= 0:
        raise ValueError("A loan principal is required")
    data = calculators.amortization(principal, rate, months)
    return ToolResult(
        tool="calculate_emi",
        label="EMI calculator",
        args={"principal": principal, "annual_rate": rate, "months": months},
        headline=f"The monthly EMI is {fmt_money(user, data['monthly_payment'])}.",
        display=[
            f"Principal: {fmt_money(user, data['principal'])}",
            f"Interest rate: {fmt_pct(data['annual_rate'])}",
            f"Tenure: {data['months']} months",
            f"Total interest: {fmt_money(user, data['total_interest'])}",
            f"Total payment: {fmt_money(user, data['total_payment'])}",
        ],
        interpretation="Longer tenures lower the EMI but raise total interest. Compare the total payment, not only the monthly number.",
        facts=data,
        assumptions=["Fixed rate, no processing fees, on-time payments."],
        knowledge=_knowledge("loan EMI interest", 1),
    )


def _calculate_sip(user, args, as_of):
    monthly = as_float(args.get("monthly_investment") or args.get("amount"), 5000)
    rate = as_float(args.get("annual_return") if args.get("annual_return") is not None else 12, 12)
    years = as_float(args.get("years"), 10)
    step_up = as_float(args.get("step_up_pct"), 0)
    data = calculators.sip_future_value(monthly, rate, years, step_up)
    return ToolResult(
        tool="calculate_sip",
        label="SIP projection",
        args={"monthly_investment": monthly, "annual_return": rate, "years": years, "step_up_pct": step_up},
        headline=f"Investing {fmt_money(user, monthly)} a month at {fmt_pct(rate)} for {years} years projects to {fmt_money(user, data['future_value'])}.",
        display=[
            f"Total invested: {fmt_money(user, data['invested'])}",
            f"Estimated gains: {fmt_money(user, data['gains'])}",
            f"Assumed annual return: {fmt_pct(rate)}",
        ],
        interpretation="This is a compound-growth illustration, not a promised return. Equity returns are volatile and can be negative over short periods.",
        facts=data,
        assumptions=["Constant return, monthly contributions at month-end, no taxes or fees."],
        knowledge=_knowledge("SIP compounding mutual funds", 2),
    )


def _calculate_fire(user, args, as_of):
    capacity = analytics.savings_capacity(user.id, 3)
    net = analytics.net_worth(user.id)
    annual_expenses = as_float(args.get("annual_expenses"), float(capacity["avg_monthly_expenses"]) * 12)
    if annual_expenses <= 0:
        annual_expenses = max(1.0, float(capacity["avg_monthly_expenses"]) * 12)
    age = as_float(args.get("current_age"), 30)
    savings = as_float(args.get("current_savings"), float(net["liquid_assets"]))
    monthly = as_float(args.get("monthly_savings"), max(0.0, float(capacity["avg_monthly_savings"])))
    rate = as_float(args.get("annual_return"), 9)
    inflation = as_float(args.get("inflation"), 5)
    data = calculators.fire_projection(age, annual_expenses, savings, monthly, rate, inflation)
    return ToolResult(
        tool="calculate_fire",
        label="FIRE projection",
        args={"current_age": age, "annual_expenses": annual_expenses, "current_savings": savings, "monthly_savings": monthly},
        headline=(
            f"Your FI number is about {fmt_money(user, data['fi_number_today'])} today; "
            f"at the current pace you reach it around age {data['fi_age']}."
            if data["reached"]
            else "At the current pace, the projection does not reach financial independence within 70 years."
        ),
        display=[
            f"Annual expenses: {fmt_money(user, data['annual_expenses'])}",
            f"FI number (4% rule): {fmt_money(user, data['fi_number_today'])}",
            f"Monthly savings: {fmt_money(user, data['monthly_savings'])}",
            f"Real return after inflation: {fmt_pct(data['real_return'])}",
            f"Years to FI: {data['years_to_fi']}",
        ],
        interpretation="The FI number is a target, not a finish line. Sequence-of-returns risk and health costs can change the picture.",
        facts=data,
        assumptions=["Constant real return, constant savings, 4% withdrawal rate, expenses grow with inflation."],
        knowledge=_knowledge("FIRE financial independence 4 percent rule", 2),
    )


def _loan_affordability(user, args, as_of):
    principal = as_float(args.get("principal") or args.get("amount"))
    apr = as_float(args.get("apr"), 12)
    payment = args.get("monthly_payment")
    if principal <= 0:
        raise ValueError("A loan principal is required")
    data = affordability.loan_affordability(
        user.id, principal, apr, as_float(payment) if payment is not None else None, as_of
    )
    return ToolResult(
        tool="loan_affordability",
        label="Loan affordability",
        args={"principal": principal, "apr": apr, "monthly_payment": payment},
        headline=data["message"],
        display=[
            f"Monthly payment: {fmt_money(user, data['monthly_payment'])}",
            f"Interest over the life of the loan: {fmt_money(user, data['interest_vs_waiting'])}",
            f"Months to save the principal instead: {data['wait_and_save_months']}",
        ],
        interpretation="Borrowing converts a future purchase into a present one and adds interest. Compare it with waiting, not only with the monthly payment.",
        facts=data,
        assumptions=["Fixed APR, no fees, on-time payments."],
        knowledge=_knowledge("loan affordability interest", 1),
    )


def _literacy(user, args, as_of):
    query = str(args.get("query") or "").strip()
    chunks = search_knowledge(query or "personal finance basics", 3)
    if not chunks:
        return ToolResult(
            tool="literacy_lookup",
            label="Financial literacy",
            args={"query": query},
            headline="The literacy library is not available yet.",
            display=[],
            interpretation="Run the seed command to load the curriculum.",
            facts={"query": query, "passages": []},
        )
    display = [f"{c['title']} — {c['heading']}: {c['text'][:260]}..." for c in chunks]
    return ToolResult(
        tool="literacy_lookup",
        label="Financial literacy",
        args={"query": query},
        headline=f"Here is what the Clearpath library says about {query or 'personal finance'}.",
        display=display,
        interpretation="Use the concept, then apply it to the numbers in your own dashboard.",
        facts={"query": query, "passages": chunks},
        assumptions=["Content is educational and does not account for your full circumstances."],
        knowledge=chunks,
    )


def _recent_transactions(user, args, as_of):
    limit = max(1, min(20, int(as_float(args.get("limit"), 5))))
    rows = (
        Transaction.query.filter_by(user_id=user.id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    display = [
        f"{r.transaction_date.isoformat()} · {r.description or r.category} · {r.kind} {fmt_money(user, r.amount)}"
        for r in rows
    ]
    return ToolResult(
        tool="recent_transactions",
        label="Recent transactions",
        args={"limit": limit},
        headline=f"Here are your {len(rows)} most recent transactions.",
        display=display,
        interpretation="Descriptions are shown only because you asked for them; analytics otherwise works on categories and amounts.",
        facts={"transactions": [r.as_dict() for r in rows], "count": len(rows)},
        assumptions=["Only your own records are included."],
        knowledge=_knowledge("reviewing transactions", 1),
    )


def _what_if(user, args, as_of):
    data = simulation.what_if(
        user.id,
        category=args.get("category"),
        reduction_pct=as_float(args.get("reduction_pct"), 0),
        extra_savings=as_float(args.get("extra_savings"), 0),
        extra_debt_payment=as_float(args.get("extra_debt_payment"), 0),
        months=int(as_float(args.get("months"), 12)),
        as_of=as_of,
    )
    display = [
        f"Monthly improvement: {fmt_money(user, data['monthly_improvement'])}",
        f"Extra saved over {data['months']} months: {fmt_money(user, data['extra_savings'])}",
    ]
    if data["goal_impact"]:
        display.append(f"Extra progress on {data['goal_impact']['goal']}: {fmt_money(user, data['goal_impact']['extra_value'])}")
    if data["debt"]:
        display.append(f"Debt interest saved: {fmt_money(user, data['debt']['interest_saved'])}")
    return ToolResult(
        tool="what_if",
        label="What-if simulation",
        args={
            "category": data["category"],
            "reduction_pct": data["reduction_pct"],
            "extra_savings": data["extra_monthly_savings"],
            "extra_debt_payment": data["extra_debt_payment"],
            "months": data["months"],
        },
        headline=f"That change would free about {fmt_money(user, data['monthly_improvement'])} per month.",
        display=display,
        interpretation="This is a deterministic scenario, not a forecast. It isolates one change while holding everything else constant.",
        facts=data,
        assumptions=data["assumptions"],
        knowledge=_knowledge("opportunity cost savings", 1),
    )


TOOLS: dict[str, ToolSpec] = {}


def _register(name: str, description: str, parameters: dict, handler):
    TOOLS[name] = ToolSpec(name, description, parameters, handler)


_register(
    "financial_overview",
    "Income, expenses, net cash flow, savings rate, health score and safe-to-spend for a month.",
    {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM; defaults to current month"}}},
    _overview,
)
_register(
    "category_spending",
    "Breakdown of expenses by category, with shares and month-over-month change.",
    {"type": "object", "properties": {"month": {"type": "string"}, "limit": {"type": "integer"}}},
    _category_spending,
)
_register(
    "budget_status",
    "Progress and pacing for every category budget in a month.",
    {"type": "object", "properties": {"month": {"type": "string"}}},
    _budget_status,
)
_register(
    "safe_to_spend",
    "Remaining discretionary spending allowance and a daily allowance for the rest of the month.",
    {"type": "object", "properties": {}},
    _safe_to_spend,
)
_register(
    "check_affordability",
    "Decide whether a purchase is affordable now, using discretionary budget, cash buffer and goal impact. Optionally model credit-card financing.",
    {
        "type": "object",
        "properties": {
            "amount": {"type": "number"},
            "category": {"type": "string"},
            "apr": {"type": "number", "description": "Annual percentage rate if financed"},
            "months": {"type": "integer"},
        },
        "required": ["amount"],
    },
    _check_affordability,
)
_register(
    "savings_capacity",
    "Average monthly savings and projected savings capacity over a horizon.",
    {"type": "object", "properties": {"months": {"type": "integer"}}},
    _savings_capacity,
)
_register(
    "savings_estimate",
    "Estimate how much the user can save over N months from recent behaviour.",
    {"type": "object", "properties": {"months": {"type": "integer"}}},
    _savings_estimate,
)
_register(
    "small_purchase_affordability",
    "Daily allowance for a specific spending category for the rest of the month.",
    {"type": "object", "properties": {"category": {"type": "string"}}, "required": ["category"]},
    _small_purchase,
)
_register(
    "budget_tracking",
    "Whether a category is on pace at today's date.",
    {"type": "object", "properties": {"category": {"type": "string"}}, "required": ["category"]},
    _budget_tracking,
)
_register(
    "goal_status",
    "Progress, required contribution and Monte Carlo success probability for savings goals.",
    {"type": "object", "properties": {"goal": {"type": "string"}}},
    _goal_status,
)
_register(
    "debt_payoff",
    "Avalanche and snowball debt payoff plans, including interest and time saved by extra payments.",
    {"type": "object", "properties": {"extra_payment": {"type": "number"}}},
    _debt_payoff,
)
_register(
    "emergency_fund",
    "Months of essential expenses covered by cash, with three- and six-month targets.",
    {"type": "object", "properties": {}},
    _emergency_fund,
)
_register(
    "forecast_expenses",
    "Forecast total expenses for the next 1–6 months with approximate 80% intervals.",
    {"type": "object", "properties": {"horizon": {"type": "integer"}}},
    _forecast,
)
_register(
    "recurring_subscriptions",
    "Detect recurring subscriptions and their annual cost.",
    {"type": "object", "properties": {}},
    _recurring,
)
_register(
    "anomalies",
    "Unusually large expenses relative to the user's own category history.",
    {"type": "object", "properties": {}},
    _anomalies,
)
_register(
    "financial_health",
    "Transparent 0–100 financial health score with component breakdown.",
    {"type": "object", "properties": {}},
    _health,
)
_register(
    "net_worth",
    "Assets, debts, liquid assets and net worth.",
    {"type": "object", "properties": {}},
    _net_worth,
)
_register(
    "calculate_emi",
    "EMI, total interest and amortization for a loan.",
    {
        "type": "object",
        "properties": {
            "principal": {"type": "number"},
            "annual_rate": {"type": "number"},
            "months": {"type": "integer"},
        },
        "required": ["principal"],
    },
    _calculate_emi,
)
_register(
    "calculate_sip",
    "Future value of a monthly SIP with optional annual step-up.",
    {
        "type": "object",
        "properties": {
            "monthly_investment": {"type": "number"},
            "annual_return": {"type": "number"},
            "years": {"type": "number"},
            "step_up_pct": {"type": "number"},
        },
        "required": ["monthly_investment"],
    },
    _calculate_sip,
)
_register(
    "calculate_fire",
    "Financial-independence number and years to FI using income, expenses and savings.",
    {
        "type": "object",
        "properties": {
            "current_age": {"type": "number"},
            "annual_expenses": {"type": "number"},
            "current_savings": {"type": "number"},
            "monthly_savings": {"type": "number"},
            "annual_return": {"type": "number"},
            "inflation": {"type": "number"},
        },
    },
    _calculate_fire,
)
_register(
    "loan_affordability",
    "Payoff time and interest for a new loan at a given monthly payment.",
    {
        "type": "object",
        "properties": {
            "principal": {"type": "number"},
            "apr": {"type": "number"},
            "monthly_payment": {"type": "number"},
        },
        "required": ["principal"],
    },
    _loan_affordability,
)
_register(
    "literacy_lookup",
    "Search the financial-literacy library for a concept or question. Returns cited passages.",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    _literacy,
)
_register(
    "recent_transactions",
    "The user's most recent transactions. Contains decrypted descriptions; use only when explicitly asked.",
    {"type": "object", "properties": {"limit": {"type": "integer"}}},
    _recent_transactions,
)
_register(
    "what_if",
    "Simulate the effect of cutting a category, saving more, or paying extra debt for a number of months.",
    {
        "type": "object",
        "properties": {
            "category": {"type": "string"},
            "reduction_pct": {"type": "number"},
            "extra_savings": {"type": "number"},
            "extra_debt_payment": {"type": "number"},
            "months": {"type": "integer"},
        },
    },
    _what_if,
)


def catalog() -> list[dict]:
    return [
        {"name": spec.name, "description": spec.description, "parameters": spec.parameters}
        for spec in TOOLS.values()
    ]


def execute(name: str, user, args: dict, as_of: date | None = None) -> ToolResult:
    spec = TOOLS.get(name)
    if not spec:
        raise ValueError(f"Unknown tool: {name}")
    if not isinstance(args, dict):
        args = {}
    return spec.handler(user, args, as_of or today())
