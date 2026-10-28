"""Deterministic demo data and literacy seeding.

The demo account is intentionally realistic: eighteen months of INR
transactions with recurring bills, subscriptions, a credit-card balance,
goals, contributions and a few genuine anomalies.  It is generated with a
fixed random seed so screenshots, tests and the research harness are
reproducible.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from .extensions import db
from .models import (
    ActivityEvent,
    Asset,
    Budget,
    Debt,
    Goal,
    GoalContribution,
    LiteracyModule,
    LiteracyProgress,
    Nudge,
    QuizAttempt,
    Transaction,
    User,
)
from .services.literacy import seed_literacy as _seed_literacy
from .utils import add_months, days_in_month, month_key, today

DEMO_EMAIL = "demo@clearpath.app"
DEMO_PASSWORD = "DemoPass123!"


def _d(value: float) -> Decimal:
    return Decimal(str(round(float(value), 2)))


def _date_in_month(month: date, day: int) -> date | None:
    day = min(day, days_in_month(month))
    value = date(month.year, month.month, day)
    return value if value <= today() else None


def _tx(user_id: int, when: date | None, kind: str, amount: float, category: str, description: str) -> Transaction | None:
    if when is None:
        return None
    return Transaction(
        user_id=user_id,
        kind=kind,
        amount=_d(amount),
        category=category,
        description=description,
        notes="",
        transaction_date=when,
        recurring=False,
        source="demo",
        category_source="demo",
        category_confidence=1.0,
        fingerprint=None,
    )


def _monthly_transactions(user_id: int, month: date, offset: int, rng: random.Random) -> list[Transaction]:
    rows: list[Transaction] = []

    def add(day: int, kind: str, amount: float, category: str, description: str) -> None:
        row = _tx(user_id, _date_in_month(month, day), kind, amount, category, description)
        if row is not None:
            rows.append(row)

    # Income ---------------------------------------------------------------
    add(1, "income", 145000, "Salary", "Salary - TechNova Solutions")
    if offset % 3 == 1:
        add(20, "income", rng.uniform(18000, 34000), "Freelance", "Freelance - Design Retainer")
    if offset == 12:
        add(18, "income", 50000, "Salary", "Annual performance bonus")

    # Fixed obligations ----------------------------------------------------
    add(3, "expense", 35000, "Housing", "Rent - Green Valley Apartments")
    add(5, "expense", 12400, "Loan EMI", "HDFC Car Loan EMI")
    add(5, "expense", 649, "Subscriptions", "Netflix")
    add(7, "expense", 15000, "Investments", "Groww SIP - Index Fund")
    add(7, "expense", 119, "Subscriptions", "Spotify")
    add(10, "expense", 2200, "Insurance", "Star Health Insurance")
    add(12, "expense", 299, "Subscriptions", "Amazon Prime")
    add(15, "expense", 75, "Subscriptions", "iCloud Storage")
    add(18, "expense", 149, "Subscriptions", "YouTube Premium")
    add(22, "expense", 130, "Subscriptions", "Google One")

    # Utilities ------------------------------------------------------------
    add(8, "expense", rng.uniform(2400, 3600), "Utilities", "BESCOM Electricity")
    add(9, "expense", 999, "Utilities", "ACT Fibernet")
    add(14, "expense", 599, "Utilities", "Airtel Postpaid")
    add(20, "expense", rng.uniform(950, 1250), "Utilities", "Indane Gas")

    # Groceries and everyday food -----------------------------------------
    for day in (3, 9, 16, 24):
        add(day, "expense", rng.uniform(2300, 3400), "Groceries", rng.choice(
            ["BigBasket", "Reliance Fresh", "DMart", "Local Kirana"]
        ))
    dining_days = sorted(rng.sample(range(2, 28), 7))
    for day in dining_days:
        add(day, "expense", rng.uniform(280, 1600), "Food & Dining", rng.choice(
            ["Swiggy", "Zomato", "Third Wave Coffee", "Truffles", "Local restaurant"]
        ))

    # Transport ------------------------------------------------------------
    for day in (4, 11, 17, 23):
        add(day, "expense", rng.uniform(180, 780), "Transport", rng.choice(
            ["Uber", "Ola", "Namma Metro"]
        ))
    add(11, "expense", rng.uniform(2200, 2800), "Transport", "Indian Oil Fuel")

    # Discretionary --------------------------------------------------------
    for day in sorted(rng.sample(range(2, 27), 3)):
        add(day, "expense", rng.uniform(800, 4200), "Shopping", rng.choice(
            ["Amazon", "Flipkart", "Myntra", "Decathlon"]
        ))
    for day in sorted(rng.sample(range(2, 27), 2)):
        add(day, "expense", rng.uniform(380, 1100), "Entertainment", rng.choice(
            ["PVR Cinemas", "BookMyShow", "Spotify Concert"]
        ))
    add(17, "expense", rng.uniform(320, 780), "Healthcare", "Apollo Pharmacy")
    if offset % 4 == 0:
        add(19, "expense", 800, "Healthcare", "Practo Consultation")

    # Occasional large expenses (create honest anomalies) -----------------
    if offset == 2:
        add(21, "expense", 28000, "Shopping", "Croma - Laptop")
    if offset == 5:
        add(13, "expense", 18000, "Healthcare", "Apollo Hospital - Day Procedure")
    if offset in {3, 9, 15}:
        add(14, "expense", rng.uniform(12000, 22000), "Travel", "MakeMyTrip - Weekend Trip")
    if offset == 4:
        add(6, "expense", 4999, "Education", "Coursera - Data Course")

    return rows


BUDGETS = {
    "Housing": 35000,
    "Groceries": 12000,
    "Food & Dining": 9000,
    "Transport": 7000,
    "Utilities": 7000,
    "Subscriptions": 1400,
    "Entertainment": 3000,
    "Shopping": 9000,
    "Healthcare": 2500,
    "Insurance": 2500,
    "Loan EMI": 12400,
    "Investments": 15000,
}


def _seed_budgets(user_id: int) -> None:
    for offset in range(0, 6):
        month = add_months(today().replace(day=1), -offset)
        for category, amount in BUDGETS.items():
            db.session.add(
                Budget(
                    user_id=user_id,
                    category=category,
                    month=month,
                    amount=_d(amount),
                    rollover=False,
                )
            )


def _seed_goals(user_id: int) -> list[Goal]:
    current = today()
    specs = [
        {
            "name": "Emergency fund top-up",
            "category": "Safety",
            "target_amount": 300000,
            "initial_amount": 135000,
            "monthly_contribution": 10000,
            "target_date": add_months(current, 12),
            "expected_return": 4.0,
            "priority": 1,
            "notes": "Three to six months of essential expenses in a separate savings account.",
        },
        {
            "name": "Japan trip",
            "category": "Travel",
            "target_amount": 400000,
            "initial_amount": 40000,
            "monthly_contribution": 12000,
            "target_date": add_months(current, 8),
            "expected_return": 6.0,
            "priority": 2,
            "notes": "Flights, stay and food for two weeks.",
        },
        {
            "name": "New laptop",
            "category": "Purchase",
            "target_amount": 120000,
            "initial_amount": 30000,
            "monthly_contribution": 6000,
            "target_date": add_months(current, 6),
            "expected_return": 4.0,
            "priority": 2,
            "notes": "Replace the seven-year-old work machine.",
        },
        {
            "name": "Retirement corpus",
            "category": "Retirement",
            "target_amount": 5000000,
            "initial_amount": 180000,
            "monthly_contribution": 15000,
            "target_date": add_months(current, 240),
            "expected_return": 9.0,
            "priority": 1,
            "notes": "Long-horizon equity and EPF contributions.",
        },
    ]
    goals = []
    for spec in specs:
        goal = Goal(
            user_id=user_id,
            name=spec["name"],
            category=spec["category"],
            target_amount=_d(spec["target_amount"]),
            initial_amount=_d(spec["initial_amount"]),
            monthly_contribution=_d(spec["monthly_contribution"]),
            target_date=spec["target_date"],
            expected_return=spec["expected_return"],
            priority=spec["priority"],
            notes=spec["notes"],
            archived=False,
        )
        db.session.add(goal)
        db.session.flush()
        goals.append(goal)
        for offset in range(1, 7):
            when = _date_in_month(add_months(today().replace(day=1), -offset), 7)
            if when is None:
                continue
            db.session.add(
                GoalContribution(
                    goal_id=goal.id,
                    amount=_d(spec["monthly_contribution"]),
                    contribution_date=when,
                    note="Monthly automatic contribution",
                )
            )
    return goals


def _seed_debts(user_id: int) -> None:
    debts = [
        ("Car loan - HDFC Bank", "auto_loan", 285000, 9.2, 12400, 5, None),
        ("Credit card - Axis Bank", "credit_card", 75000, 36.0, 2400, 18, 150000),
        ("Personal loan - Bajaj Finserv", "personal_loan", 60000, 14.5, 4800, 12, None),
    ]
    for name, kind, balance, apr, minimum, due, limit in debts:
        db.session.add(
            Debt(
                user_id=user_id,
                name=name,
                debt_type=kind,
                balance=_d(balance),
                apr=apr,
                minimum_payment=_d(minimum),
                due_day=due,
                credit_limit=_d(limit) if limit else None,
            )
        )


def _seed_assets(user_id: int) -> None:
    assets = [
        ("Savings account - HDFC", "cash", 85000, True),
        ("Emergency fund - ICICI", "cash", 135000, True),
        ("Index fund portfolio", "investment", 185000, True),
        ("PPF account", "retirement", 95000, False),
        ("EPF balance", "retirement", 260000, False),
    ]
    for name, kind, value, liquid in assets:
        db.session.add(
            Asset(user_id=user_id, name=name, asset_type=kind, value=_d(value), is_liquid=liquid)
        )


def _seed_activity(user_id: int) -> None:
    today_ = today()
    for offset in range(12):
        day = today_ - timedelta(days=offset)
        db.session.add(
            ActivityEvent(
                user_id=user_id,
                event_type="transaction_log",
                description="Logged a transaction" if offset else "Reviewed the dashboard",
                points=2,
                occurred_on=day,
                meta={"seeded": True},
            )
        )
    db.session.add(
        ActivityEvent(
            user_id=user_id,
            event_type="goal_contribution",
            description="Contributed to Japan trip",
            points=10,
            occurred_on=today_ - timedelta(days=3),
            meta={"seeded": True},
        )
    )


def _seed_nudge_history(user_id: int) -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    history = [
        ("budget_over", "Food & Dining was over budget", "accepted"),
        ("high_interest_debt", "Credit-card interest check", "accepted"),
        ("goal_at_risk", "Japan trip is behind plan", "accepted"),
        ("emergency_low", "Emergency runway reminder", "dismissed"),
        ("subscription_creep", "Subscription audit reminder", "dismissed"),
    ]
    for index, (rule, title, status) in enumerate(history):
        db.session.add(
            Nudge(
                user_id=user_id,
                rule_id=rule,
                dedupe_key=f"history:{rule}",
                severity="attention",
                priority=30 + index,
                title=title,
                body="Historical response retained for the demo and for nudge-effectiveness reporting.",
                action_label="Review",
                action_type="ack",
                payload={"seeded": True},
                points=5,
                status=status,
                created_at=now - timedelta(days=18 + index),
                responded_at=now - timedelta(days=17 + index),
            )
        )


def _seed_literacy_progress(user_id: int) -> None:
    completed = [
        ("budget-as-a-decision", 3, 3),
        ("emergency-fund", 2, 3),
        ("debt-and-interest", 3, 3),
    ]
    for slug, score, total in completed:
        module = LiteracyModule.query.filter_by(slug=slug).first()
        if not module:
            continue
        db.session.add(
            LiteracyProgress(
                user_id=user_id,
                module_id=module.id,
                status="completed",
                last_viewed=datetime.now(timezone.utc).replace(tzinfo=None),
                completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                best_score=score,
                attempts=1,
            )
        )
        db.session.add(
            QuizAttempt(
                user_id=user_id,
                module_id=module.id,
                score=score,
                total=total,
                answers=[0] * total,
            )
        )


def seed_literacy() -> int:
    """Load or refresh the curriculum. Safe to call repeatedly."""
    return _seed_literacy()


def seed_demo(app) -> dict:
    """Create (or recreate) the demo account and all of its history."""
    with app.app_context():
        seed_literacy()
        existing = User.query.filter_by(email=DEMO_EMAIL).first()
        if existing:
            QuizAttempt.query.filter_by(user_id=existing.id).delete()
            db.session.delete(existing)
            db.session.commit()

        user = User(
            email=DEMO_EMAIL,
            name="Ananya Rao",
            currency="INR",
            language="en",
            risk_profile="moderate",
            monthly_income=_d(145000),
            onboarded=True,
        )
        user.set_password(DEMO_PASSWORD)
        db.session.add(user)
        db.session.commit()

        rng = random.Random(20251028)
        current = today().replace(day=1)
        transactions: list[Transaction] = []
        for offset in range(17, -1, -1):
            month = add_months(current, -offset)
            transactions.extend(_monthly_transactions(user.id, month, offset, rng))
        db.session.add_all(transactions)
        _seed_budgets(user.id)
        goals = _seed_goals(user.id)
        _seed_debts(user.id)
        _seed_assets(user.id)
        _seed_activity(user.id)
        _seed_nudge_history(user.id)
        _seed_literacy_progress(user.id)
        db.session.commit()

        return {
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            "transactions": len(transactions),
            "goals": len(goals),
            "months": 18,
            "first_month": month_key(add_months(current, -17)),
            "last_month": month_key(current),
        }
