from __future__ import annotations

from datetime import date

from app.utils import add_months

from .helpers import add_transaction, make_user, seed_months


def test_budget_crud_and_pacing(client):
    make_user(client)
    created = client.post(
        "/api/budgets",
        json={"category": "Food & Dining", "amount": "1000", "month": date.today().strftime("%Y-%m")},
    )
    assert created.status_code == 201
    budget = created.get_json()["budget"]
    add_transaction(client, amount="1200", category="Food & Dining")
    status = client.get("/api/budgets").get_json()["status"]
    row = next(c for c in status["categories"] if c["category"] == "Food & Dining")
    assert row["state"] == "over"
    assert status["overall_state"] == "over"

    patched = client.patch(f"/api/budgets/{budget['id']}", json={"amount": "2000"})
    assert patched.status_code == 200
    assert patched.get_json()["budget"]["amount"] == "2000.00"
    assert client.delete(f"/api/budgets/{budget['id']}").status_code == 200


def test_budget_suggestions_and_copy(client):
    make_user(client)
    previous = add_months(date.today().replace(day=1), -1).replace(day=15)
    add_transaction(client, amount="3000", category="Groceries", date=previous.isoformat())
    suggestions = client.get("/api/budgets").get_json()["suggestions"]
    assert any(item["category"] == "Groceries" for item in suggestions)
    target = add_months(date.today().replace(day=1), 1).strftime("%Y-%m")
    client.post(
        "/api/budgets",
        json={"category": "Groceries", "amount": "3200", "month": date.today().strftime("%Y-%m")},
    )
    copied = client.post(
        "/api/budgets/copy",
        json={"from_month": date.today().strftime("%Y-%m"), "to_month": target},
    )
    assert copied.status_code == 200
    assert copied.get_json()["copied"] == 1


def test_goals_and_contributions(client):
    make_user(client)
    created = client.post(
        "/api/goals",
        json={
            "name": "Laptop",
            "target_amount": "120000",
            "initial_amount": "20000",
            "monthly_contribution": "5000",
            "target_date": add_months(date.today(), 12).isoformat(),
            "expected_return": 6,
        },
    )
    assert created.status_code == 201
    goal = created.get_json()["goal"]
    assert goal["name"] == "Laptop"
    contribution = client.post(
        f"/api/goals/{goal['id']}/contributions",
        json={"amount": "5000", "date": date.today().isoformat(), "note": "First"},
    )
    assert contribution.status_code == 201
    detail = client.get(f"/api/goals/{goal['id']}")
    assert float(detail.get_json()["goal"]["saved_amount"]) == 25000
    overview = client.get("/api/goals").get_json()
    assert overview["count"] == 1
    assert overview["goals"][0]["probability"] is not None
    assert client.delete(f"/api/goals/{goal['id']}/contributions/{contribution.get_json()['contribution']['id']}").status_code == 200
    assert client.post("/api/goals", json={"name": "Bad", "target_amount": "0"}).status_code == 400


def test_goal_ownership(client, second_client):
    make_user(client)
    goal = client.post("/api/goals", json={"name": "Trip", "target_amount": "100000"}).get_json()["goal"]
    make_user(second_client, email="other@example.com")
    assert second_client.get(f"/api/goals/{goal['id']}").status_code == 404
    assert second_client.delete(f"/api/goals/{goal['id']}").status_code == 404


def test_debts_assets_and_payoff_warning(client):
    make_user(client)
    debt = client.post(
        "/api/debts",
        json={"name": "Card", "balance": "100000", "apr": 36, "minimum_payment": "1000", "due_day": 5},
    )
    assert debt.status_code == 201
    plan = client.get("/api/debts/plan")
    assert plan.status_code == 200
    assert plan.get_json()["plan"]["avalanche"]["order"] == ["Card"]
    assert plan.get_json()["warnings"]
    asset = client.post("/api/assets", json={"name": "Savings", "value": "50000", "asset_type": "cash"})
    assert asset.status_code == 201
    worth = client.get("/api/insights/net-worth").get_json()
    assert worth["assets"] == "50000.00"
    assert worth["debts"] == "100000.00"
    assert worth["net_worth"] == "-50000.00"


def test_dashboard_forecast_and_what_if(client, app):
    user = make_user(client)["user"]
    seed_months(app, user["id"], 12)
    overview = client.get("/api/insights/overview")
    assert overview.status_code == 200
    payload = overview.get_json()
    for key in ("month", "cashflow", "budgets", "goals", "financial_health", "safe_to_spend", "nudges"):
        assert key in payload
    forecast = client.get("/api/insights/forecast?horizon=3").get_json()
    assert forecast["method"] in {"ridge_lag_seasonal", "moving_average"}
    assert len(forecast["forecast"]) == 3
    what_if = client.post("/api/insights/what-if", json={"category": "Groceries", "reduction_pct": 20, "months": 12})
    assert what_if.status_code == 200
    assert float(what_if.get_json()["monthly_improvement"]) > 0


def test_affordability_is_deterministic_and_arithmetic(client, app):
    user = make_user(client)["user"]
    seed_months(app, user["id"], 6, amount=12000)
    # Add a modest cash buffer so the verdict has a basis to reason about.
    add_transaction(client, kind="expense", amount="9000", category="Groceries", date=date.today().isoformat())
    client.post("/api/assets", json={"name": "Savings", "value": "150000", "asset_type": "cash"})
    result = client.post(
        "/api/insights/affordability",
        json={"amount": 20000, "category": "Shopping", "apr": 18, "months": 6},
    )
    assert result.status_code == 200
    payload = result.get_json()
    assert payload["amount"] == "20000.00"
    assert "verdict" in payload
    assert "max_safe_amount" in payload
    assert payload["financing"]["monthly_payment"]
    assert float(payload["financing"]["total_cost"]) > 20000


def test_calculators(client):
    make_user(client)
    emi = client.post("/api/calculators/emi", json={"principal": 1000000, "annual_rate": 10, "months": 60})
    assert emi.status_code == 200
    assert 20000 < emi.get_json()["monthly_payment"] < 23000
    sip = client.post("/api/calculators/sip", json={"monthly_investment": 10000, "annual_return": 12, "years": 10})
    assert sip.get_json()["future_value"] > sip.get_json()["invested"]
    compound = client.post("/api/calculators/compound", json={"principal": 1000, "annual_rate": 10, "years": 5})
    assert compound.get_json()["amount"] > 1600
    swp = client.post("/api/calculators/swp", json={"corpus": 1000000, "monthly_withdrawal": 10000})
    assert swp.get_json()["months_lasted"] > 0
    fire = client.post("/api/calculators/fire", json={"annual_expenses": 600000, "current_age": 30})
    assert fire.status_code == 200
    assert fire.get_json()["fi_number_today"] > 0
