from __future__ import annotations

from app import create_app

from .helpers import login, register


def test_csrf_is_required_for_session_writes():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "CSRF_ENABLED": True,
            "ALLOW_DEMO_LOGIN": False,
            "AUTO_SEED_LITERACY": False,
            "SECRET_KEY": "csrf-test",
            "FIELD_ENCRYPTION_KEY": "csrf-test-encryption-key",
        }
    )
    client = app.test_client()
    response = register(client)
    assert response.status_code == 201
    token = response.get_json()["csrf_token"]
    blocked = client.post(
        "/api/transactions",
        json={"kind": "expense", "amount": "100", "category": "Other", "description": "No token"},
    )
    assert blocked.status_code == 403
    allowed = client.post(
        "/api/transactions",
        json={"kind": "expense", "amount": "100", "category": "Other", "description": "Token"},
        headers={"X-CSRF-Token": token},
    )
    assert allowed.status_code == 201
    me = client.get("/api/auth/me")
    assert me.get_json()["csrf_token"] == token
    client.post("/api/auth/logout", headers={"X-CSRF-Token": token})
    assert login(client).status_code == 200


def test_public_auth_routes_do_not_require_csrf(client):
    response = register(client)
    assert response.status_code == 201
    client.post("/api/auth/logout")
    assert login(client).status_code == 200
