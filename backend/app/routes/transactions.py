"""Transaction CRUD, search, CSV import/export and auto-categorisation."""
from __future__ import annotations

import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import Blueprint, Response, jsonify, request

from ..categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, normalize_category
from ..errors import body, current_user, error, require_user
from ..extensions import db
from ..models import Transaction
from ..services.categorization import categorise_transaction, category_distribution
from ..services.nudges import award_points
from ..utils import (
    as_float,
    fingerprint,
    json_safe,
    money_str,
    month_key,
    normalize_text,
    parse_date,
)

transactions_bp = Blueprint("transactions", __name__)
MAX_IMPORT_ROWS = 2500


def _recurring(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _amount(value) -> Decimal:
    try:
        amount = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("Amount must be a valid number")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Amount must be positive")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Amount can have at most two decimal places")
    if amount > Decimal("9999999999.99"):
        raise ValueError("Amount is too large")
    return amount.quantize(Decimal("0.01"))


def _payload(data: dict, user_id: int, existing: Transaction | None = None) -> dict:
    kind = str(data.get("kind", existing.kind if existing else "expense")).lower()
    if kind not in {"income", "expense"}:
        raise ValueError("kind must be income or expense")
    amount = _amount(data.get("amount")) if "amount" in data or not existing else Decimal(existing.amount)
    try:
        if "date" in data and str(data.get("date") or "").strip():
            trans_date = parse_date(data["date"])
        else:
            trans_date = existing.transaction_date if existing else date.today()
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD")
    description = str(data.get("description", existing.description if existing else "") or "").strip()[:200]
    notes = str(data.get("notes", existing.notes if existing else "") or "").strip()[:1000]
    recurring = _recurring(data.get("recurring", existing.recurring if existing else False))
    raw_category = data.get("category", None)
    if raw_category is None and existing is not None:
        category = existing.category
        source = existing.category_source
        confidence = existing.category_confidence
    elif raw_category in (None, "", "auto", "Auto", "suggested"):
        result = categorise_transaction(description, kind, user_id=user_id)
        category, source, confidence = result.category, result.source, result.confidence
    else:
        category = normalize_category(str(raw_category), kind)
        allowed = INCOME_CATEGORIES if kind == "income" else EXPENSE_CATEGORIES
        if category not in allowed:
            category = "Other Income" if kind == "income" else "Other"
        source, confidence = "manual", 1.0
    if kind == "income" and category not in INCOME_CATEGORIES:
        category = "Other Income"
    if kind == "expense" and category not in EXPENSE_CATEGORIES:
        category = "Other"
    return {
        "kind": kind,
        "amount": amount,
        "category": category,
        "description": description,
        "notes": notes,
        "transaction_date": trans_date,
        "recurring": recurring,
        "category_source": source,
        "category_confidence": float(confidence),
    }


@transactions_bp.get("/transactions")
@require_user
def list_transactions():
    user = current_user()
    query = Transaction.query.filter_by(user_id=user.id)
    if request.args.get("kind") in {"income", "expense"}:
        query = query.filter(Transaction.kind == request.args["kind"])
    if request.args.get("category"):
        query = query.filter(Transaction.category == request.args["category"])
    if request.args.get("from"):
        try:
            query = query.filter(Transaction.transaction_date >= parse_date(request.args["from"]))
        except ValueError:
            return error("Invalid from date")
    if request.args.get("to"):
        try:
            query = query.filter(Transaction.transaction_date <= parse_date(request.args["to"]))
        except ValueError:
            return error("Invalid to date")
    if request.args.get("month"):
        try:
            first = parse_date(request.args["month"] + "-01")
        except ValueError:
            return error("Invalid month")
        from ..utils import month_bounds

        first, last = month_bounds(first)
        query = query.filter(Transaction.transaction_date >= first, Transaction.transaction_date <= last)
    rows = query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(3000).all()
    term = (request.args.get("q") or "").strip().lower()
    if term:
        rows = [
            row
            for row in rows
            if term in (row.description or "").lower()
            or term in (row.notes or "").lower()
            or term in row.category.lower()
            or term in row.transaction_date.isoformat()
        ]
    total = len(rows)
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 50))))
    except ValueError:
        return error("page and per_page must be numbers")
    start = (page - 1) * per_page
    items = rows[start : start + per_page]
    return jsonify(
        {
            "transactions": [t.as_dict() for t in items],
            "total": total,
            "page": page,
            "per_page": per_page,
            "has_more": start + per_page < total,
        }
    )


@transactions_bp.get("/transactions/<int:transaction_id>")
@require_user
def get_transaction(transaction_id):
    row = Transaction.query.filter_by(id=transaction_id, user_id=current_user().id).first()
    if not row:
        return error("Transaction not found", 404, "not_found")
    return jsonify({"transaction": row.as_dict()})


@transactions_bp.post("/transactions")
@require_user
def create_transaction():
    user = current_user()
    try:
        values = _payload(body(), user.id)
    except ValueError as exc:
        return error(str(exc))
    row = Transaction(user_id=user.id, source="manual", fingerprint=None, **values)
    db.session.add(row)
    db.session.commit()
    award_points(user.id, "transaction_log", 2, "Logged a transaction", {"transaction_id": row.id})
    return jsonify({"transaction": row.as_dict()}), 201


@transactions_bp.patch("/transactions/<int:transaction_id>")
@require_user
def update_transaction(transaction_id):
    user = current_user()
    row = Transaction.query.filter_by(id=transaction_id, user_id=user.id).first()
    if not row:
        return error("Transaction not found", 404, "not_found")
    try:
        values = _payload(body(), user.id, row)
    except ValueError as exc:
        return error(str(exc))
    for key, value in values.items():
        setattr(row, key, value)
    row.fingerprint = None
    db.session.commit()
    return jsonify({"transaction": row.as_dict()})


@transactions_bp.delete("/transactions/<int:transaction_id>")
@require_user
def delete_transaction(transaction_id):
    row = Transaction.query.filter_by(id=transaction_id, user_id=current_user().id).first()
    if not row:
        return error("Transaction not found", 404, "not_found")
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})


@transactions_bp.post("/transactions/suggest-category")
@require_user
def suggest_category():
    data = body()
    description = str(data.get("description", "")).strip()
    kind = str(data.get("kind", "expense"))
    if not description:
        return error("description is required")
    result = categorise_transaction(description, kind, user_id=current_user().id)
    return jsonify(
        {
            "category": result.category,
            "confidence": round(result.confidence, 3),
            "source": result.source,
            "alternatives": category_distribution(description) if kind == "expense" else [],
        }
    )


@transactions_bp.post("/transactions/import")
@require_user
def import_transactions():
    user = current_user()
    file = request.files.get("file")
    if not file or not file.filename or not file.filename.lower().endswith(".csv"):
        return error("Upload a CSV file")
    try:
        raw = file.stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return error("CSV must be UTF-8 encoded")
    try:
        reader = csv.DictReader(io.StringIO(raw))
        if not reader.fieldnames:
            return error("CSV is empty")
        fieldnames = {name.strip().lower() for name in reader.fieldnames}
        required = {"date", "kind", "amount"}
        if not required.issubset(fieldnames):
            return error("CSV needs date, kind and amount columns")
        existing = {
            row[0]
            for row in db.session.query(Transaction.fingerprint)
            .filter(Transaction.user_id == user.id, Transaction.fingerprint.isnot(None))
            .all()
        }
        created = []
        skipped = 0
        errors = []
        for line, item in enumerate(reader, start=2):
            if len(created) >= MAX_IMPORT_ROWS:
                errors.append({"line": line, "error": f"Import limited to {MAX_IMPORT_ROWS} rows"})
                break
            if line > MAX_IMPORT_ROWS + 10:
                break
            data = {str(key).strip().lower(): value for key, value in item.items() if key is not None}
            try:
                values = _payload(data, user.id)
                key = fingerprint(
                    user.id,
                    values["transaction_date"].isoformat(),
                    values["kind"],
                    money_str(values["amount"]),
                    normalize_text(values["description"]),
                )
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                created.append(Transaction(user_id=user.id, source="csv", fingerprint=key, **values))
            except (ValueError, TypeError) as exc:
                if len(errors) < 12:
                    errors.append({"line": line, "error": str(exc)})
        if created:
            db.session.add_all(created)
            db.session.commit()
            award_points(user.id, "transaction_log", 2, f"Imported {len(created)} transactions")
        return (
            jsonify(
                {
                    "imported": len(created),
                    "skipped_duplicates": skipped,
                    "errors": errors,
                    "total_rows": len(created) + skipped + len(errors),
                }
            ),
            201 if created else 200,
        )
    except csv.Error:
        return error("Could not read CSV file")


@transactions_bp.get("/transactions/export")
@require_user
def export_transactions():
    user = current_user()
    rows = (
        Transaction.query.filter_by(user_id=user.id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["date", "kind", "amount", "category", "description", "notes", "recurring", "source"])
    for row in rows:
        writer.writerow(
            [
                row.transaction_date.isoformat(),
                row.kind,
                money_str(row.amount),
                row.category,
                row.description or "",
                row.notes or "",
                str(bool(row.recurring)).lower(),
                row.source,
            ]
        )
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=clearpath-transactions.csv"},
    )
