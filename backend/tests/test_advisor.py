from __future__ import annotations

from datetime import date

from app.models import User
from app.services.advisor.engine import catalog
from app.services.advisor.providers import LLMResponse
from app.services.advisor.verifier import verify_answer

from .helpers import add_transaction, make_user


def _fund_user(client):
    make_user(client)
    client.post(
        "/api/transactions",
        json={"kind": "income", "amount": "150000", "category": "Salary", "description": "Salary", "date": date.today().isoformat()},
    )
    client.post(
        "/api/transactions",
        json={"kind": "expense", "amount": "18000", "category": "Groceries", "description": "BigBasket", "date": date.today().isoformat()},
    )


def test_verifier_accepts_only_supported_numbers():
    results = [
        {
            "tool": "savings_capacity",
            "headline": "You saved ₹20,000.",
            "facts": {"avg_monthly_savings": 20000, "savings_rate": 13.3},
            "display": ["Savings rate: 13.3%"],
            "assumptions": [],
        }
    ]
    good = verify_answer("You saved ₹20,000, a 13.3% savings rate.", results)
    assert good["passed"] is True
    bad = verify_answer("You saved ₹99,999, a 13.3% savings rate.", results)
    assert bad["passed"] is False
    assert bad["unsupported"][0]["value"] == 99999


def test_advisor_status_tools_and_grounded_chat(client):
    _fund_user(client)
    status = client.get("/api/advisor/status")
    assert status.status_code == 200
    assert status.get_json()["llm"]["provider"] == "mock"
    tools = client.get("/api/advisor/tools").get_json()
    assert len(tools["tools"]) == 24
    assert {t["name"] for t in tools["tools"]} >= {"check_affordability", "debt_payoff", "literacy_lookup"}

    response = client.post("/api/advisor/chat", json={"message": "Can I afford a 25000 laptop?"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["planner"]["calls"][0]["tool"] == "check_affordability"
    assert body["verification"]["passed"] is True
    assert body["provider"] == "mock"
    assert "₹" in body["message"]["content"]
    assert body["session"]["message_count"] == 2


def test_advisor_uses_last_month_and_literacy(client):
    _fund_user(client)
    response = client.post("/api/advisor/chat", json={"message": "Where did my money go last month?"})
    body = response.get_json()
    assert body["planner"]["calls"][0]["tool"] == "category_spending"
    assert body["verification"]["passed"] is True

    learning = client.post("/api/advisor/chat", json={"message": "Explain emergency funds"})
    assert learning.status_code == 200
    assert learning.get_json()["message"]["content"]


def test_advisor_sessions_feedback_and_isolation(client, second_client):
    _fund_user(client)
    chat = client.post("/api/advisor/chat", json={"message": "How much can I save in 6 months?"}).get_json()
    session_id = chat["session"]["id"]
    message_id = chat["message"]["id"]
    assert client.get(f"/api/advisor/sessions/{session_id}").status_code == 200
    feedback = client.post(f"/api/advisor/messages/{message_id}/feedback", json={"rating": 1, "comment": "Useful"})
    assert feedback.status_code == 200
    assert feedback.get_json()["message"]["rating"] == 1

    make_user(second_client, email="other@example.com")
    assert second_client.get(f"/api/advisor/sessions/{session_id}").status_code == 404
    assert second_client.delete(f"/api/advisor/sessions/{session_id}").status_code == 404
    assert second_client.post(f"/api/advisor/messages/{message_id}/feedback", json={"rating": -1}).status_code == 404


def test_advisor_rejects_empty_question(client):
    make_user(client)
    assert client.post("/api/advisor/chat", json={"message": "  "}).status_code == 400


def test_unsupported_llm_answer_falls_back_to_deterministic(client, app, monkeypatch):
    _fund_user(client)
    with app.app_context():
        user = User.query.filter_by(email="user@example.com").first()
        from app.services.advisor import tools as registry

        results = [registry.execute("financial_overview", user, {}, date.today()).as_dict()]
        from app.services.advisor import composer

        class FakeProvider:
            name = "fake"
            model = "fake-model"

            def available(self):
                return True

            def complete(self, system, payload, json_mode=False):
                return LLMResponse(
                    text="Your income is ₹9,99,999 and your savings rate is 99%.",
                    provider="fake",
                    model="fake-model",
                    latency_ms=1,
                )

        monkeypatch.setattr(composer, "get_provider", lambda _app: FakeProvider())
        result = composer.compose(app, user, "What is my overview?", type("P", (), {"as_dict": lambda s: {}, "clarification": None})(), results, date.today())
        assert result["provider"] == "mock"
        assert result["verification"]["mode"] == "deterministic"
        assert result["verification"]["passed"] is True
        assert "9,99,999" not in result["answer"]


def test_nudges_and_gamification(client):
    make_user(client)
    client.post("/api/budgets", json={"category": "Food & Dining", "amount": "1000"})
    add_transaction(client, amount="1500", category="Food & Dining")
    client.post(
        "/api/debts",
        json={"name": "Card", "balance": "50000", "apr": 36, "minimum_payment": "2500"},
    )
    response = client.get("/api/nudges")
    assert response.status_code == 200
    body = response.get_json()
    assert body["nudges"]
    rules = {n["rule_id"] for n in body["nudges"]}
    assert "high_interest_debt" in rules
    nudge = next(n for n in body["nudges"] if n["rule_id"] == "high_interest_debt")
    acted = client.post(f"/api/nudges/{nudge['id']}/respond", json={"action": "accept"})
    assert acted.status_code == 200
    assert acted.get_json()["nudge"]["status"] == "accepted"
    effectiveness = client.get("/api/nudges/effectiveness").get_json()
    assert effectiveness["accepted"] >= 1
    points = client.get("/api/gamification").get_json()
    assert points["points"] >= 5
    assert client.post(f"/api/nudges/{nudge['id']}/respond", json={"action": "nope"}).status_code == 400
