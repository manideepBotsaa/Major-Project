from __future__ import annotations

from datetime import date, timedelta

PASSWORD = "StrongPass123"


def register(client, email="user@example.com", name="Test User", password=PASSWORD, **extra):
    payload = {"name": name, "email": email, "password": password, **extra}
    return client.post("/api/auth/register", json=payload)


def login(client, email="user@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def make_user(client, email="user@example.com", name="Test User"):
    response = register(client, email=email, name=name)
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def add_transaction(client, **overrides):
    payload = {
        "kind": "expense",
        "amount": "1200.00",
        "category": "Food & Dining",
        "description": "Swiggy order",
        "date": date.today().isoformat(),
    }
    payload.update(overrides)
    return client.post("/api/transactions", json=payload)


def seed_months(app, user_id, months=12, amount=20000.0):
    from app.extensions import db
    from app.models import Transaction

    today = date.today().replace(day=1)
    for offset in range(1, months + 1):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        when = date(year, month, 15)
        db.session.add(
            Transaction(
                user_id=user_id,
                kind="expense",
                amount=amount + (offset % 3) * 900,
                category="Groceries",
                description=f"Month {offset} groceries",
                transaction_date=when,
                source="test",
                category_source="test",
            )
        )
    db.session.commit()
