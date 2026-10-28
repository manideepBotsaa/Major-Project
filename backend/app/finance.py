from datetime import date
from decimal import Decimal

from sqlalchemy import func
from .models import Transaction


def monthly_summary(user_id, year=None, month=None):
    today = date.today()
    year, month = year or today.year, month or today.month
    rows = Transaction.query.filter(
        Transaction.user_id == user_id,
        func.strftime("%Y", Transaction.transaction_date) == f"{year:04d}",
        func.strftime("%m", Transaction.transaction_date) == f"{month:02d}",
    ).all()
    income = sum((Decimal(r.amount) for r in rows if r.kind == "income"), Decimal("0"))
    expenses = sum((Decimal(r.amount) for r in rows if r.kind == "expense"), Decimal("0"))
    categories = {}
    for row in rows:
        if row.kind == "expense":
            categories[row.category] = categories.get(row.category, Decimal("0")) + Decimal(row.amount)
    savings = income - expenses
    rate = (savings / income * 100) if income else None
    return {
        "year": year, "month": month, "income": str(income), "expenses": str(expenses),
        "balance": str(savings), "savings_rate": str(rate.quantize(Decimal("0.1"))) if rate is not None else None,
        "expense_categories": [{"category": k, "amount": str(v)} for k, v in sorted(categories.items(), key=lambda x: x[1], reverse=True)],
        "transaction_count": len(rows),
    }
