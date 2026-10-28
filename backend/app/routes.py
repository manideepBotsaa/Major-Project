import csv
import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, jsonify, request, session, Response
from sqlalchemy import or_

from . import db
from .finance import monthly_summary
from .models import Transaction, User

api = Blueprint("api", __name__)
CATEGORIES = {"Food", "Transportation", "Housing", "Education", "Healthcare", "Shopping", "Entertainment", "Utilities", "Subscriptions", "Loan payments", "Travel", "Other", "Salary", "Freelance", "Investment", "Other income"}


def require_user(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        user = db.session.get(User, session.get("user_id")) if session.get("user_id") else None
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapped


def transaction_data(data):
    kind = data.get("kind")
    if kind not in ("income", "expense"):
        raise ValueError("kind must be income or expense")
    try:
        amount = Decimal(str(data.get("amount", "")))
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a valid number")
    if not amount.is_finite() or amount <= 0 or amount.as_tuple().exponent < -2 or amount > Decimal("9999999999.99"):
        raise ValueError("amount must be positive and have at most 2 decimal places")
    category = str(data.get("category", "Other")).strip()
    if category not in CATEGORIES:
        category = "Other"
    try:
        trans_date = date.fromisoformat(str(data.get("date", date.today().isoformat())))
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD")
    recurring_value = data.get("recurring", False)
    if isinstance(recurring_value, str):
        recurring_value = recurring_value.strip().lower() in {"1", "true", "yes", "on"}
    return dict(kind=kind, amount=amount, category=category,
                description=str(data.get("description", "")).strip()[:200],
                notes=str(data.get("notes", "")).strip()[:1000], transaction_date=trans_date,
                recurring=bool(recurring_value))


@api.post("/auth/register")
def register():
    data = request.get_json(silent=True) or {}
    name, email, password = str(data.get("name", "")).strip(), str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    if not name or len(name) > 100 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "Enter a name and valid email address"}), 400
    if len(password) < 10:
        return jsonify({"error": "Password must be at least 10 characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists"}), 409
    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    session.clear(); session["user_id"] = user.id; session["csrf_token"] = api_csrf_token(); session.permanent = True
    return jsonify({"user": {"id": user.id, "name": user.name, "email": user.email, "currency": user.currency}, "csrf_token": session["csrf_token"]}), 201


@api.post("/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(email=str(data.get("email", "")).strip().lower()).first()
    if not user or not user.check_password(str(data.get("password", ""))):
        return jsonify({"error": "Email or password is incorrect"}), 401
    session.clear(); session["user_id"] = user.id; session["csrf_token"] = api_csrf_token(); session.permanent = True
    return jsonify({"user": {"id": user.id, "name": user.name, "email": user.email, "currency": user.currency}, "csrf_token": session["csrf_token"]})


def api_csrf_token():
    from flask import current_app
    return current_app.config["CSRF_TOKEN_FACTORY"](32)


@api.post("/auth/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@api.get("/auth/me")
@require_user
def me():
    u = request.current_user
    return jsonify({"user": {"id": u.id, "name": u.name, "email": u.email, "currency": u.currency, "language": u.language}, "csrf_token": session.get("csrf_token")})


@api.patch("/profile")
@require_user
def update_profile():
    data = request.get_json(silent=True) or {}
    user = request.current_user
    if "name" in data and str(data["name"]).strip(): user.name = str(data["name"]).strip()[:100]
    if "currency" in data and data["currency"] in {"INR", "USD", "EUR", "GBP"}: user.currency = data["currency"]
    if "language" in data and data["language"] in {"en", "hi", "te"}: user.language = data["language"]
    db.session.commit()
    return me()


@api.delete("/account")
@require_user
def delete_account():
    db.session.delete(request.current_user); db.session.commit(); session.clear()
    return jsonify({"ok": True})


@api.get("/transactions")
@require_user
def list_transactions():
    q = Transaction.query.filter_by(user_id=request.current_user.id)
    for param, column in (("kind", Transaction.kind), ("category", Transaction.category)):
        if request.args.get(param): q = q.filter(column == request.args[param])
    if request.args.get("from"): q = q.filter(Transaction.transaction_date >= request.args["from"])
    if request.args.get("to"): q = q.filter(Transaction.transaction_date <= request.args["to"])
    if request.args.get("q"):
        term = f"%{request.args['q']}%"; q = q.filter(or_(Transaction.description.ilike(term), Transaction.notes.ilike(term), Transaction.category.ilike(term)))
    items = q.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).limit(500).all()
    return jsonify({"transactions": [r.as_dict() for r in items]})


@api.post("/transactions")
@require_user
def create_transaction():
    try: values = transaction_data(request.get_json(silent=True) or {})
    except ValueError as e: return jsonify({"error": str(e)}), 400
    row = Transaction(user_id=request.current_user.id, **values); db.session.add(row); db.session.commit()
    return jsonify({"transaction": row.as_dict()}), 201


@api.patch("/transactions/<int:transaction_id>")
@require_user
def update_transaction(transaction_id):
    row = Transaction.query.filter_by(id=transaction_id, user_id=request.current_user.id).first_or_404()
    try: values = transaction_data({**row.as_dict(), **(request.get_json(silent=True) or {})})
    except ValueError as e: return jsonify({"error": str(e)}), 400
    for key, value in values.items(): setattr(row, key, value)
    db.session.commit(); return jsonify({"transaction": row.as_dict()})


@api.delete("/transactions/<int:transaction_id>")
@require_user
def delete_transaction(transaction_id):
    row = Transaction.query.filter_by(id=transaction_id, user_id=request.current_user.id).first_or_404()
    db.session.delete(row); db.session.commit(); return jsonify({"ok": True})


@api.get("/dashboard")
@require_user
def dashboard():
    try: year, month = int(request.args.get("year", date.today().year)), int(request.args.get("month", date.today().month))
    except ValueError: return jsonify({"error": "year and month must be numbers"}), 400
    if not 1 <= month <= 12: return jsonify({"error": "month must be between 1 and 12"}), 400
    return jsonify(monthly_summary(request.current_user.id, year, month))


@api.get("/transactions/export")
@require_user
def export_transactions():
    rows = Transaction.query.filter_by(user_id=request.current_user.id).order_by(Transaction.transaction_date.desc()).all()
    output = io.StringIO(); writer = csv.writer(output)
    writer.writerow(["date", "kind", "amount", "category", "description", "notes", "recurring"])
    for r in rows: writer.writerow([r.transaction_date.isoformat(), r.kind, str(r.amount), r.category, r.description, r.notes, str(r.recurring).lower()])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=transactions.csv"})


@api.post("/transactions/import")
@require_user
def import_transactions():
    file = request.files.get("file")
    if not file or not file.filename.lower().endswith(".csv"): return jsonify({"error": "Upload a CSV file"}), 400
    try:
        reader = csv.DictReader(io.StringIO(file.stream.read().decode("utf-8-sig")))
        required = {"date", "kind", "amount"}
        if not required.issubset(set(reader.fieldnames or [])): return jsonify({"error": "CSV needs date, kind and amount columns"}), 400
        created = []
        for line, item in enumerate(reader, start=2):
            try: created.append(Transaction(user_id=request.current_user.id, **transaction_data(item)))
            except ValueError as exc: return jsonify({"error": f"Row {line}: {exc}"}), 400
        db.session.add_all(created); db.session.commit()
        return jsonify({"imported": len(created)}), 201
    except (UnicodeDecodeError, csv.Error): return jsonify({"error": "Could not read CSV file"}), 400
