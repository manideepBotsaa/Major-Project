from __future__ import annotations

from sqlalchemy import text

from app.extensions import db
from app.models import User

from .helpers import PASSWORD, login, make_user, register


def test_register_validation_and_duplicate(client):
    assert register(client, password="short").status_code == 400
    assert register(client, email="not-an-email").status_code == 400
    response = register(client)
    assert response.status_code == 201
    body = response.get_json()
    assert body["user"]["email"] == "user@example.com"
    assert body["csrf_token"]
    duplicate = register(client)
    assert duplicate.status_code == 409


def test_login_logout_and_me(client):
    make_user(client)
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, password="wrong").status_code == 401
    response = login(client)
    assert response.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["user"]["name"] == "Test User"
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401


def test_profile_update_and_password_change(client):
    make_user(client)
    bad = client.patch("/api/profile", json={"currency": "XYZ"})
    assert bad.status_code == 400
    good = client.patch(
        "/api/profile",
        json={"name": "Updated Name", "currency": "USD", "risk_profile": "conservative", "monthly_income": "90000"},
    )
    assert good.status_code == 200
    assert good.get_json()["user"]["currency"] == "USD"
    assert good.get_json()["user"]["monthly_income"] == "90000.00"
    wrong = client.post(
        "/api/profile/password",
        json={"current_password": "wrong", "new_password": "AnotherPass123"},
    )
    assert wrong.status_code == 401
    changed = client.post(
        "/api/profile/password",
        json={"current_password": PASSWORD, "new_password": "AnotherPass123"},
    )
    assert changed.status_code == 200
    client.post("/api/auth/logout")
    assert login(client, password="AnotherPass123").status_code == 200


def test_account_export_and_delete(client, app):
    make_user(client)
    client.post(
        "/api/transactions",
        json={"kind": "expense", "amount": "500", "category": "Shopping", "description": "Book"},
    )
    export = client.get("/api/account/export")
    assert export.status_code == 200
    assert export.get_json()["transactions"][0]["description"] == "Book"
    assert "attachment" in export.headers["Content-Disposition"]
    assert client.delete("/api/account", json={"password": "wrong"}).status_code == 401
    assert client.delete("/api/account", json={"password": PASSWORD}).status_code == 200
    assert User.query.count() == 0


def test_descriptions_are_encrypted_at_rest(client, app):
    make_user(client)
    client.post(
        "/api/transactions",
        json={"kind": "expense", "amount": "450", "category": "Food & Dining", "description": "Secret Coffee"},
    )
    raw = db.session.execute(text('SELECT description FROM "transaction"')).scalar_one()
    assert raw != "Secret Coffee"
    assert "Secret Coffee" not in raw
    listed = client.get("/api/transactions").get_json()["transactions"][0]
    assert listed["description"] == "Secret Coffee"
