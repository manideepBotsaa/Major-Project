"""Just-in-time nudges and gamification.

The nudge engine is the product implementation of the just-in-time education
idea in Ramjattan et al. (2021): suggestions are generated from the user's
current financial state, carry the arithmetic that justifies them, and record
whether the user accepted or dismissed them.  This makes nudge effectiveness
measurable rather than assumed.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func

from ..extensions import db
from ..models import ActivityEvent, Goal, Nudge, Transaction
from ..utils import money_str, month_bounds, month_key, today
from .analytics import budget_adherence, emergency_fund, financial_health, savings_capacity, tx_between
from .budgeting import budget_status
from .forecasting import forecast_expenses
from .goals import goal_overview

MAX_ACTIVE_NUDGES = 4


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _candidate(
    rule_id: str,
    dedupe_key: str,
    severity: str,
    priority: int,
    title: str,
    body: str,
    action_label: str = "Got it",
    action_type: str = "ack",
    points: int = 5,
    payload: dict | None = None,
) -> dict:
    return {
        "rule_id": rule_id,
        "dedupe_key": dedupe_key[:160],
        "severity": severity,
        "priority": priority,
        "title": title,
        "body": body,
        "action_label": action_label,
        "action_type": action_type,
        "points": points,
        "payload": payload or {},
    }


def _build_candidates(user_id: int, as_of: date) -> list[dict]:
    candidates: list[dict] = []
    month = as_of.replace(day=1)
    key = month_key(month)

    budgets = budget_status(user_id, month, as_of)
    for row in budgets["categories"]:
        if row["state"] == "over":
            candidates.append(
                _candidate(
                    "budget_over",
                    f"budget_over:{row['category']}:{key}",
                    "critical",
                    5,
                    f"{row['category']} is over budget",
                    f"You have spent {row['spent']} against a {row['amount']} budget, "
                    f"which is {row['used_pct']}% of the plan. Every extra 100 now comes "
                    f"out of another goal. Pause this category for the rest of {month.strftime('%B')}.",
                    "Show me the damage",
                    "open_budgets",
                    10,
                    {"category": row["category"], "month": key},
                )
            )
        elif row["state"] == "watch":
            candidates.append(
                _candidate(
                    "budget_pace",
                    f"budget_pace:{row['category']}:{key}",
                    "attention",
                    35,
                    f"Watch the pace on {row['category']}",
                    f"At today's pace you are heading to about {row['projected']} by month-end, "
                    f"against a budget of {row['amount']}. You have {row['daily_remaining']} "
                    f"per day left to stay on track.",
                    "Review budget",
                    "open_budgets",
                    5,
                    {"category": row["category"], "month": key},
                )
            )

    capacity = savings_capacity(user_id, 3)
    if float(capacity["avg_monthly_income"]) > 0 and float(capacity["savings_rate"]) < 10:
        candidates.append(
            _candidate(
                "low_savings",
                f"low_savings:{key}",
                "attention",
                30,
                "Your savings rate needs attention",
                f"Over the last three months you kept {capacity['savings_rate']}% of income "
                f"({capacity['avg_monthly_savings']} per month). Moving to 10% would add "
                f"{money_str(float(capacity['avg_monthly_income']) * 0.10 - max(0, float(capacity['avg_monthly_savings'])))} "
                "per month toward your goals.",
                "Build a savings plan",
                "open_goals",
                8,
                {"savings_rate": capacity["savings_rate"]},
            )
        )

    ef = emergency_fund(user_id, as_of)
    if ef["status"] == "low":
        candidates.append(
            _candidate(
                "emergency_low",
                f"emergency_low:{key}",
                "attention",
                25,
                "Your emergency runway is thin",
                f"You have {ef['months_covered']} months of essential expenses in cash "
                f"({ef['cash_available']}). A three-month buffer needs {ef['gap_to_3_months']} more. "
                "This is the buffer that stops a surprise from becoming debt.",
                "Plan the buffer",
                "open_goals",
                8,
                {"gap": ef["gap_to_3_months"]},
            )
        )

    from ..models import Debt

    for debt in Debt.query.filter_by(user_id=user_id).all():
        if float(debt.apr) >= 18 and float(debt.balance) > 0:
            candidates.append(
                _candidate(
                    "high_interest_debt",
                    f"high_interest_debt:{debt.id}:{key}",
                    "critical",
                    15,
                    f"{debt.name} is charging {debt.apr:.0f}% interest",
                    f"A balance of {money_str(debt.balance)} at {debt.apr:.0f}% APR costs about "
                    f"{money_str(float(debt.balance) * float(debt.apr) / 1200)} in interest this month. "
                    "Prioritise this over new investing until it is cleared.",
                    "See payoff plan",
                    "open_goals",
                    10,
                    {"debt_id": debt.id, "apr": float(debt.apr)},
                )
            )

    goals = goal_overview(user_id, as_of)
    for goal in goals["goals"]:
        if goal["status"] in {"at_risk", "off_track"} and goal["months_left"]:
            candidates.append(
                _candidate(
                    "goal_at_risk",
                    f"goal_at_risk:{goal['id']}:{key}",
                    "attention",
                    40,
                    f"{goal['name']} is behind plan",
                    f"At {goal['monthly_contribution']} per month, the estimated success chance is "
                    f"{round((goal['probability'] or 0) * 100)}%. You need about "
                    f"{goal['required_monthly']} per month to get back on track.",
                    "Open goal plan",
                    "open_goals",
                    8,
                    {"goal_id": goal["id"], "gap": goal["monthly_gap"]},
                )
            )

    from .analytics import recurring_candidates

    subscriptions = [s for s in recurring_candidates(user_id) if s["is_subscription"]]
    annual_subs = sum(float(s["annual_cost"]) for s in subscriptions)
    annual_income = float(capacity["avg_monthly_income"]) * 12
    if subscriptions and (len(subscriptions) >= 5 or (annual_income and annual_subs / annual_income > 0.03)):
        candidates.append(
            _candidate(
                "subscription_creep",
                f"subscription_creep:{key}",
                "info",
                45,
                "Subscription creep detected",
                f"{len(subscriptions)} recurring subscriptions cost about {money_str(annual_subs)} a year. "
                "Cancelling the two you use least could fund a goal contribution instead.",
                "Review subscriptions",
                "open_insights",
                5,
                {"count": len(subscriptions), "annual": money_str(annual_subs)},
            )
        )

    from .analytics import detect_anomalies

    anomalies = detect_anomalies(user_id, 30)
    if anomalies:
        top = anomalies[0]
        tx = top["transaction"]
        candidates.append(
            _candidate(
                "unusual_spend",
                f"unusual_spend:{tx['id']}",
                "attention",
                20,
                "That expense is unusual for you",
                f"{tx['description'] or tx['category']} was {tx['amount']}, about "
                f"{top['multiple']}x your typical {tx['category']} spend. If this was a one-off, "
                "no action is needed; if it repeats, it deserves a budget line.",
                "Review transaction",
                "open_transactions",
                5,
                {"transaction_id": tx["id"]},
            )
        )

    first, last = month_bounds(month)
    salary_rows = [
        r for r in tx_between(user_id, max(first, as_of - timedelta(days=3)), as_of, "income")
        if r.category == "Salary"
    ]
    if salary_rows:
        salary = max(float(r.amount) for r in salary_rows)
        candidates.append(
            _candidate(
                "payday_save",
                f"payday_save:{key}",
                "info",
                50,
                "Payday is the cheapest time to save",
                f"Move 10% of your latest salary ({money_str(salary * 0.10)}) to your priority goal "
                "before it becomes spendable. Saving after spending is optional; saving first is automatic.",
                "Set up a goal",
                "open_goals",
                10,
                {"suggested": money_str(salary * 0.10)},
            )
        )

    forecast = forecast_expenses(user_id, horizon=1, as_of=as_of)
    if forecast.get("forecast") and float(budgets["total_budget"]) > 0:
        projected = float(budgets["projected_total"])
        if projected > float(budgets["total_budget"]) * 1.05:
            candidates.append(
                _candidate(
                    "forecast_overspend",
                    f"forecast_overspend:{key}",
                    "attention",
                    32,
                    "This month is trending over plan",
                    f"At the current pace, spending lands near {money_str(projected)} against a "
                    f"budget of {budgets['total_budget']}. Trimming "
                    f"{money_str(projected - float(budgets['total_budget']))} over the remaining "
                    "days keeps the month on plan.",
                    "Open insights",
                    "open_insights",
                    6,
                    {"projected": money_str(projected)},
                )
            )

    summary = gamification_summary(user_id)
    if summary["streak"] >= 3:
        candidates.append(
            _candidate(
                "streak_reinforce",
                f"streak_reinforce:{as_of.isoformat()}",
                "info",
                60,
                f"{summary['streak']}-day tracking streak",
                "Consistency is the quiet superpower of personal finance. Log today's activity "
                "to keep the streak alive and earn 5 points.",
                "Log something",
                "open_transactions",
                5,
                {"streak": summary["streak"]},
            )
        )
    return sorted(candidates, key=lambda c: c["priority"])


def generate_nudges(user_id: int, as_of: date | None = None, persist: bool = True) -> list[dict]:
    as_of = as_of or today()
    now = _now()
    candidates = _build_candidates(user_id, as_of)
    existing = {n.dedupe_key: n for n in Nudge.query.filter_by(user_id=user_id).all()}
    active: list[Nudge] = []
    for candidate in candidates:
        row = existing.get(candidate["dedupe_key"])
        if row is None:
            # SQLAlchemy column defaults are applied on flush, so set the status
            # explicitly: otherwise an unflushed row still has ``status=None``
            # and is skipped by the visibility check below.
            row = Nudge(user_id=user_id, status="active", **candidate)
            if not persist:
                active.append(row)
                continue
            db.session.add(row)
            existing[row.dedupe_key] = row
        elif row.status == "snoozed" and row.snoozed_until and row.snoozed_until <= now:
            row.status = "active"
        if row.status == "active":
            active.append(row)
    if persist:
        stale = Nudge.query.filter(
            Nudge.user_id == user_id,
            Nudge.status == "active",
            Nudge.created_at < now - timedelta(days=21),
        ).all()
        for row in stale:
            row.status = "expired"
        db.session.commit()
    active.sort(key=lambda n: (n.priority, n.id or 0))
    return [n.as_dict() for n in active[:MAX_ACTIVE_NUDGES]]


def respond_to_nudge(user_id: int, nudge_id: int, action: str) -> dict:
    nudge = Nudge.query.filter_by(id=nudge_id, user_id=user_id).first()
    if not nudge:
        raise ValueError("Nudge not found")
    if action not in {"accept", "dismiss", "snooze", "complete"}:
        raise ValueError("Unknown action")
    now = _now()
    if nudge.status in {"dismissed", "accepted", "expired"}:
        return {"nudge": nudge.as_dict(), "gamification": gamification_summary(user_id)}
    if action == "snooze":
        nudge.status = "snoozed"
        nudge.snoozed_until = now + timedelta(days=3)
    elif action in {"accept", "complete"}:
        nudge.status = "accepted"
        nudge.responded_at = now
        award_points(
            user_id,
            "nudge_accept",
            5,
            f"Acted on: {nudge.title}",
            {"nudge_id": nudge.id, "rule_id": nudge.rule_id},
            once_per_day=False,
        )
    else:
        nudge.status = "dismissed"
        nudge.responded_at = now
    db.session.commit()
    return {"nudge": nudge.as_dict(), "gamification": gamification_summary(user_id)}


def award_points(
    user_id: int,
    event_type: str,
    points: int,
    description: str = "",
    meta: dict | None = None,
    once_per_day: bool = True,
) -> ActivityEvent | None:
    today_ = today()
    if once_per_day:
        existing = ActivityEvent.query.filter_by(
            user_id=user_id, event_type=event_type, occurred_on=today_
        ).first()
        if existing:
            return existing
    event = ActivityEvent(
        user_id=user_id,
        event_type=event_type,
        points=max(0, int(points)),
        description=description[:200],
        occurred_on=today_,
        meta=meta or {},
    )
    db.session.add(event)
    db.session.commit()
    return event


def _streaks(dates: list[date]) -> tuple[int, int]:
    if not dates:
        return 0, 0
    unique = sorted(set(dates))
    longest = 1
    current_run = 1
    for previous, current in zip(unique, unique[1:]):
        if (current - previous).days == 1:
            current_run += 1
            longest = max(longest, current_run)
        else:
            current_run = 1
    today_ = today()
    current_streak = 0
    cursor = today_
    if unique[-1] != today_ and (today_ - unique[-1]).days > 1:
        return 0, longest
    if unique[-1] != today_:
        cursor = today_ - timedelta(days=1)
    date_set = set(unique)
    while cursor in date_set:
        current_streak += 1
        cursor -= timedelta(days=1)
    return current_streak, longest


BADGES = [
    {"id": "first_step", "label": "First step", "description": "Logged your first transaction", "threshold": 1, "metric": "transactions"},
    {"id": "tracker_10", "label": "Tracker", "description": "Logged 10 transactions", "threshold": 10, "metric": "transactions"},
    {"id": "budget_boss", "label": "Budget boss", "description": "Kept 80% of budgets on track", "threshold": 0.8, "metric": "adherence"},
    {"id": "goal_getter", "label": "Goal getter", "description": "Reached 50% of a savings goal", "threshold": 0.5, "metric": "goal"},
    {"id": "learner", "label": "Learner", "description": "Completed 3 literacy modules", "threshold": 3, "metric": "modules"},
    {"id": "streak_7", "label": "7-day streak", "description": "Tracked activity for 7 days in a row", "threshold": 7, "metric": "streak"},
    {"id": "streak_30", "label": "30-day streak", "description": "Tracked activity for 30 days in a row", "threshold": 30, "metric": "streak"},
    {"id": "nudge_pro", "label": "Nudge pro", "description": "Acted on 5 nudges", "threshold": 5, "metric": "nudges"},
]


def gamification_summary(user_id: int) -> dict:
    events = ActivityEvent.query.filter_by(user_id=user_id).order_by(ActivityEvent.id.desc()).all()
    total_points = sum(e.points for e in events)
    streak, longest = _streaks([e.occurred_on for e in events])
    tx_count = Transaction.query.filter_by(user_id=user_id).count()
    from ..models import LiteracyProgress

    modules_done = LiteracyProgress.query.filter_by(user_id=user_id, status="completed").count()
    nudge_accepts = Nudge.query.filter_by(user_id=user_id, status="accepted").count()
    goals = Goal.query.filter_by(user_id=user_id, archived=False).all()
    goal_progress = max((float(g.saved_amount) / float(g.target_amount) if float(g.target_amount) else 0) for g in goals) if goals else 0.0
    adherence, _, _ = budget_adherence(user_id, today().replace(day=1))
    metrics = {
        "transactions": tx_count,
        "streak": streak,
        "modules": modules_done,
        "nudges": nudge_accepts,
        "goal": goal_progress,
        "adherence": adherence,
    }
    earned = []
    for badge in BADGES:
        value = metrics.get(badge["metric"], 0)
        if value >= badge["threshold"]:
            earned.append(badge)
    level = 1 + total_points // 200
    return {
        "points": total_points,
        "level": level,
        "points_to_next": 200 - (total_points % 200),
        "streak": streak,
        "longest_streak": longest,
        "badges": earned,
        "badges_available": [b for b in BADGES if b not in earned],
        "recent_activity": [e.as_dict() for e in events[:8]],
        "metrics": {
            "transactions": tx_count,
            "modules_completed": modules_done,
            "nudges_accepted": nudge_accepts,
            "goal_progress": round(goal_progress * 100, 1),
            "budget_adherence": round(adherence * 100, 1),
        },
    }


def nudge_effectiveness(user_id: int) -> dict:
    """Descriptive statistics for nudges the user has responded to."""
    rows = Nudge.query.filter(Nudge.user_id == user_id, Nudge.status != "active").all()
    accepted = sum(1 for n in rows if n.status == "accepted")
    dismissed = sum(1 for n in rows if n.status == "dismissed")
    total = accepted + dismissed
    by_rule: dict[str, dict] = {}
    for n in rows:
        item = by_rule.setdefault(n.rule_id, {"rule_id": n.rule_id, "accepted": 0, "dismissed": 0})
        if n.status == "accepted":
            item["accepted"] += 1
        elif n.status == "dismissed":
            item["dismissed"] += 1
    for item in by_rule.values():
        decisions = item["accepted"] + item["dismissed"]
        item["acceptance_rate"] = round(item["accepted"] / decisions * 100, 1) if decisions else None
    return {
        "total_decided": total,
        "accepted": accepted,
        "dismissed": dismissed,
        "acceptance_rate": round(accepted / total * 100, 1) if total else None,
        "by_rule": sorted(by_rule.values(), key=lambda x: x["accepted"] + x["dismissed"], reverse=True),
    }
