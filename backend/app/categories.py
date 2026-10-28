"""Canonical category taxonomy and presentation metadata."""
from __future__ import annotations

EXPENSE_CATEGORIES = [
    "Food & Dining",
    "Groceries",
    "Transport",
    "Housing",
    "Utilities",
    "Healthcare",
    "Shopping",
    "Entertainment",
    "Subscriptions",
    "Education",
    "Travel",
    "Loan EMI",
    "Insurance",
    "Investments",
    "Other",
]

INCOME_CATEGORIES = [
    "Salary",
    "Freelance",
    "Business",
    "Investment Returns",
    "Gift",
    "Other Income",
]

ALL_CATEGORIES = EXPENSE_CATEGORIES + INCOME_CATEGORIES

ESSENTIAL_CATEGORIES = {
    "Housing",
    "Groceries",
    "Utilities",
    "Healthcare",
    "Insurance",
    "Loan EMI",
    "Transport",
    "Education",
}

DISCRETIONARY_CATEGORIES = [
    "Food & Dining",
    "Shopping",
    "Entertainment",
    "Subscriptions",
    "Travel",
    "Other",
]

CATEGORY_META = {
    "Food & Dining": {"color": "#c9855f", "icon": "utensils"},
    "Groceries": {"color": "#7aa17a", "icon": "shopping-basket"},
    "Transport": {"color": "#6e8fa8", "icon": "car"},
    "Housing": {"color": "#2f5d4a", "icon": "home"},
    "Utilities": {"color": "#a58a5f", "icon": "plug"},
    "Healthcare": {"color": "#b06a6a", "icon": "heart-pulse"},
    "Shopping": {"color": "#9a7fb1", "icon": "shopping-bag"},
    "Entertainment": {"color": "#d0a45c", "icon": "clapperboard"},
    "Subscriptions": {"color": "#5d9c94", "icon": "repeat"},
    "Education": {"color": "#718ba6", "icon": "graduation-cap"},
    "Travel": {"color": "#c27d6a", "icon": "plane"},
    "Loan EMI": {"color": "#8c5f5f", "icon": "landmark"},
    "Insurance": {"color": "#7d8f7d", "icon": "shield"},
    "Investments": {"color": "#3f7d68", "icon": "trending-up"},
    "Other": {"color": "#9aa39d", "icon": "circle"},
    "Salary": {"color": "#2f5d4a", "icon": "banknote"},
    "Freelance": {"color": "#5d9c94", "icon": "briefcase"},
    "Business": {"color": "#718ba6", "icon": "store"},
    "Investment Returns": {"color": "#3f7d68", "icon": "trending-up"},
    "Gift": {"color": "#d0a45c", "icon": "gift"},
    "Other Income": {"color": "#7aa17a", "icon": "plus-circle"},
}

CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}
SUPPORTED_CURRENCIES = list(CURRENCY_SYMBOLS)


def normalize_category(value: str | None, kind: str = "expense") -> str:
    """Return a canonical category, tolerating older/aliased labels."""
    raw = (value or "").strip()
    if not raw:
        return "Other" if kind == "expense" else "Other Income"
    lookup = {c.lower(): c for c in ALL_CATEGORIES}
    aliases = {
        "food": "Food & Dining",
        "dining": "Food & Dining",
        "restaurant": "Food & Dining",
        "groceries": "Groceries",
        "grocery": "Groceries",
        "transportation": "Transport",
        "transport": "Transport",
        "fuel": "Transport",
        "rent": "Housing",
        "home": "Housing",
        "bills": "Utilities",
        "utilities": "Utilities",
        "health": "Healthcare",
        "medical": "Healthcare",
        "shopping": "Shopping",
        "entertainment": "Entertainment",
        "subscriptions": "Subscriptions",
        "education": "Education",
        "travel": "Travel",
        "loan payments": "Loan EMI",
        "loan": "Loan EMI",
        "emi": "Loan EMI",
        "insurance": "Insurance",
        "investment": "Investments",
        "investments": "Investments",
        "sip": "Investments",
        "salary": "Salary",
        "freelance": "Freelance",
        "business": "Business",
        "investment returns": "Investment Returns",
        "gift": "Gift",
        "other income": "Other Income",
        "other": "Other" if kind == "expense" else "Other Income",
    }
    if raw.lower() in lookup:
        return lookup[raw.lower()]
    if raw.lower() in aliases:
        return aliases[raw.lower()]
    return "Other" if kind == "expense" else "Other Income"
