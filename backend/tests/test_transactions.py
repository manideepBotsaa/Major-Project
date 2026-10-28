from __future__ import annotations

import io
from datetime import date

from .helpers import add_transaction, make_user


def test_transaction_crud_and_validation(client):
    make_user(client)
    created = add_transaction(client, amount="349.50", notes="Lunch")
    assert created.status_code == 201
    row = created.get_json()["transaction"]
    assert row["kind"] == "expense"
    assert row["amount"] == "349.50"
    assert row["notes"] == "Lunch"

    bad_date = add_transaction(client, date="31-12-2025")
    assert bad_date.status_code == 400
    invalid_amount = add_transaction(client, amount="-5")
    assert invalid_amount.status_code == 400
    too_precise = add_transaction(client, amount="1.999")
    assert too_precise.status_code == 400

    listed = client.get("/api/transactions?kind=expense&q=swiggy")
    assert listed.status_code == 200
    assert listed.get_json()["total"] == 1

    updated = client.patch(
        f"/api/transactions/{row['id']}",
        json={"amount": "400", "category": "Groceries", "description": "Weekly groceries"},
    )
    assert updated.status_code == 200
    assert updated.get_json()["transaction"]["category"] == "Groceries"

    assert client.delete(f"/api/transactions/{row['id']}").status_code == 200
    assert client.get(f"/api/transactions/{row['id']}").status_code == 404


def test_transaction_ownership_isolation(client, second_client):
    make_user(client)
    tx = add_transaction(client).get_json()["transaction"]
    make_user(second_client, email="other@example.com")
    assert second_client.get(f"/api/transactions/{tx['id']}").status_code == 404
    assert second_client.patch(f"/api/transactions/{tx['id']}", json={"amount": "1"}).status_code == 404
    assert second_client.delete(f"/api/transactions/{tx['id']}").status_code == 404
    assert second_client.get("/api/transactions").get_json()["total"] == 0


def test_category_suggestion(client):
    make_user(client)
    response = client.post(
        "/api/transactions/suggest-category",
        json={"description": "UPI/Swiggy/ORDER 9182", "kind": "expense"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["category"] == "Food & Dining"
    assert body["confidence"] > 0.5
    assert len(body["alternatives"]) == 5


def test_csv_import_export_and_deduplication(client):
    make_user(client)
    csv_text = (
        "date,kind,amount,description,category\n"
        f"{date.today().isoformat()},expense,1200,Swiggy order,\n"
        f"{date.today().isoformat()},expense,1200,Swiggy order,\n"
        f"{date.today().isoformat()},income,90000,Salary,Salary\n"
        "not-a-date,expense,50,Broken,\n"
    )
    response = client.post(
        "/api/transactions/import",
        data={"file": (io.BytesIO(csv_text.encode("utf-8")), "transactions.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["imported"] == 2
    assert body["skipped_duplicates"] == 1
    assert body["errors"]

    exported = client.get("/api/transactions/export")
    assert exported.status_code == 200
    assert exported.mimetype == "text/csv"
    assert "Swiggy order" in exported.get_data(as_text=True)
    assert "salary" in exported.get_data(as_text=True).lower()


def test_csv_import_rejects_missing_columns(client):
    make_user(client)
    response = client.post(
        "/api/transactions/import",
        data={"file": (io.BytesIO(b"date,amount\n2025-01-01,100\n"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400


def test_transaction_list_filters_by_month(client):
    make_user(client)
    add_transaction(client, date=date.today().replace(day=1).isoformat())
    month = date.today().strftime("%Y-%m")
    response = client.get(f"/api/transactions?month={month}")
    assert response.status_code == 200
    assert response.get_json()["total"] == 1
    assert client.get("/api/transactions?month=not-a-month").status_code == 400
