"""Hybrid transaction categorisation: merchant memory + rules + TF-IDF model.

The model is trained on a bundled merchant lexicon, so the application works
offline.  Rules are applied first for high-precision cases (e.g. "amazon
prime"), and the learned model handles unseen descriptions.  Manual edits are
remembered per user and take precedence.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, make_pipeline

from ..categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES, normalize_category
from ..models import Transaction
from ..utils import normalize_text

TRAINING_MERCHANTS: dict[str, list[str]] = {
    "Food & Dining": [
        "Swiggy", "Zomato", "Dominos", "Pizza Hut", "KFC", "McDonalds", "Burger King",
        "Starbucks", "Third Wave Coffee", "Blue Tokai", "Chaayos", "Haldirams",
        "Barbeque Nation", "Punjab Grill", "Social", "Toit", "Biryani Blues", "Wow Momo",
        "Faasos", "EatFit", "Cafe Coffee Day", "Mainland China", "Empire Restaurant",
        "Anand Sweets", "Bakery", "Food Court", "Restaurant", "Dhaba", "Juice Junction",
    ],
    "Groceries": [
        "BigBasket", "Blinkit", "Zepto", "Instamart", "DMart", "Reliance Fresh",
        "More Supermarket", "Spar", "Natures Basket", "Kirana Store", "Vegetable Vendor",
        "Milk Booth", "Amul Parlour", "Grofers", "JioMart", "Easyday", "Star Bazaar",
        "Ratnadeep", "Heritage Fresh", "FreshToHome", "Licious", "Country Delight",
    ],
    "Transport": [
        "Uber", "Ola", "Rapido", "Namma Metro", "BMTC", "IndianOil", "HP Petrol",
        "Shell", "BPCL", "FASTag", "Parking", "Toll Plaza", "Auto Rickshaw", "Yulu",
        "Bounce", "Delhi Metro", "Mumbai Local", "RedBus", "Abhibus", "BluSmart",
    ],
    "Housing": [
        "Rent", "NoBroker", "MagicBricks", "Housing Society", "Maintenance Charges",
        "Landlord", "PG Rent", "UrbanClap Home", "MyGate", "Sobha Dream Acres",
        "Prestige Apartments", "Brigade Gateway", "House Rent", "Society Maintenance",
    ],
    "Utilities": [
        "BESCOM", "Electricity Bill", "Tata Power", "Adani Electricity", "Jio",
        "Airtel", "Vi Recharge", "ACT Fibernet", "Broadband", "Water Bill",
        "Indane Gas", "Piped Gas", "Municipal Tax", "BSNL", "Hathway", "Excitel",
    ],
    "Healthcare": [
        "Apollo Pharmacy", "PharmEasy", "1mg", "Practo", "Fortis", "Manipal Hospital",
        "Max Hospital", "Dentist", "Diagnostic Lab", "Health Checkup", "Gym",
        "Cult Fit", "MedPlus", "Netmeds", "Thyrocare", "Dr Lal PathLabs", "Physiotherapy",
    ],
    "Shopping": [
        "Amazon", "Flipkart", "Myntra", "Ajio", "Nykaa", "Meesho", "Tata Cliq",
        "Decathlon", "Croma", "Reliance Digital", "IKEA", "Zara", "H&M", "Nike",
        "Adidas", "Lifestyle", "Shopper Stop", "Westside", "Pantaloons", "Pepperfry",
        "FirstCry", "Lenskart", "Titan", "Tanishq", "Bata",
    ],
    "Entertainment": [
        "BookMyShow", "PVR", "INOX", "Steam", "PlayStation", "Gaming", "Concert",
        "Movie Ticket", "Cinepolis", "Wonderla", "Timezone", "Smaaash", "Bowling",
        "Comedy Club", "Music Festival",
    ],
    "Subscriptions": [
        "Netflix", "Spotify", "Amazon Prime", "Disney Hotstar", "YouTube Premium",
        "Apple Music", "Google One", "iCloud", "ChatGPT Plus", "Adobe Creative Cloud",
        "Microsoft 365", "Zee5", "Sony LIV", "Audible", "Kindle Unlimited",
        "Notion", "Canva Pro", "Dropbox", "LinkedIn Premium", "JioCinema",
    ],
    "Education": [
        "Coursera", "Udemy", "Byjus", "Unacademy", "Vedantu", "School Fees",
        "College Fee", "Tuition", "Books", "Stationery", "Kindle Store", "Skillshare",
        "Great Learning", "Simplilearn", "UpGrad", "Exam Fee", "Hostel Fee",
    ],
    "Travel": [
        "IRCTC", "MakeMyTrip", "Goibibo", "Cleartrip", "IndiGo", "Air India",
        "Vistara", "SpiceJet", "Airbnb", "OYO", "Booking.com", "Hotel", "Flight",
        "Train Ticket", "Visa Application", "Travel Insurance", "Redbus Travel",
        "Thomas Cook", "Yatra",
    ],
    "Loan EMI": [
        "EMI", "Loan Repayment", "Credit Card Payment", "HDFC Loan", "SBI Loan",
        "Bajaj Finance", "Home Loan", "Car Loan", "Personal Loan", "Student Loan",
        "ICICI Loan", "Axis Loan", "Kotak Loan", "Loan Interest", "Credit Card Bill",
    ],
    "Insurance": [
        "LIC", "HDFC Life", "ICICI Prudential", "Max Life", "Star Health",
        "HDFC Ergo", "Policy Premium", "Term Insurance", "Health Insurance",
        "Car Insurance", "Bajaj Allianz", "Tata AIG", "SBI Life", "New India Assurance",
    ],
    "Investments": [
        "Zerodha", "Groww", "Upstox", "Kuvera", "Coin", "INDmoney", "SIP",
        "Mutual Fund", "NPS", "PPF", "ELSS", "Stocks", "Gold ETF", "Recurring Deposit",
        "Smallcase", "Angel One", "5paisa", "Motilal Oswal", "ICICI Direct",
    ],
    "Other": [
        "ATM Withdrawal", "Bank Charges", "Forex", "Donation", "Miscellaneous",
        "Notary", "Post Office", "Courier", "Laundry", "Tailor", "Salon", "Barber",
        "Pet Care", "Repair", "Plumber", "Electrician",
    ],
}

INCOME_KEYWORDS: dict[str, list[str]] = {
    "Salary": ["salary", "payroll", "monthly pay", "stipend", "wages", "bonus credit"],
    "Freelance": ["freelance", "upwork", "fiverr", "client payment", "consulting", "invoice", "contract payment"],
    "Business": ["business income", "sales settlement", "shopify payout", "razorpay settlement", "merchant settlement"],
    "Investment Returns": ["dividend", "interest credit", "capital gains", "mutual fund redemption", "fd interest", "stock sale"],
    "Gift": ["gift", "wedding gift", "birthday gift"],
    "Other Income": ["refund", "reimbursement", "cashback", "tax refund", "other income"],
}

_AMBIGUOUS_INCOME = {"cashback", "refund", "interest credit"}


def _suffix_variants(merchant: str) -> list[str]:
    base = merchant.strip()
    digits = sum(ord(ch) for ch in base) % 900000 + 100000
    return [
        base,
        f"UPI/{base}/TXN{digits}",
        f"POS {base} BANGALORE",
        f"payment to {base}",
        f"{base} order 8842",
        f"DEBIT {base} 21OCT",
        f"{base} india",
        f"paid {base} online",
    ]


def build_training_rows() -> tuple[list[str], list[str]]:
    texts: list[str] = []
    labels: list[str] = []
    for category, merchants in TRAINING_MERCHANTS.items():
        for merchant in merchants:
            for variant in _suffix_variants(merchant):
                texts.append(variant)
                labels.append(category)
    return texts, labels


_RULE_EXPENSE: dict[str, str] = {}
for _category, _merchants in TRAINING_MERCHANTS.items():
    for _merchant in _merchants:
        _RULE_EXPENSE[normalize_text(_merchant)] = _category
# Curated phrases that override shorter merchant names.
_RULE_EXPENSE.update(
    {
        "amazon prime": "Subscriptions",
        "amazon music": "Subscriptions",
        "amazon pay": "Shopping",
        "google one": "Subscriptions",
        "apple music": "Subscriptions",
        "credit card payment": "Loan EMI",
        "credit card bill": "Loan EMI",
        "house rent": "Housing",
        "rent landlord": "Housing",
        "society maintenance": "Housing",
        "electricity bill": "Utilities",
        "water bill": "Utilities",
        "gas bill": "Utilities",
        "school fees": "Education",
        "college fee": "Education",
        "exam fee": "Education",
        "health insurance": "Insurance",
        "car insurance": "Insurance",
        "term insurance": "Insurance",
        "train ticket": "Travel",
        "movie ticket": "Entertainment",
        "mutual fund": "Investments",
        "recurring deposit": "Investments",
        "atm withdrawal": "Other",
        "bank charges": "Other",
    }
)
_RULE_EXPENSE = {k: v for k, v in sorted(_RULE_EXPENSE.items(), key=lambda kv: len(kv[0]), reverse=True)}

_RULE_INCOME: dict[str, str] = {}
for _category, _keywords in INCOME_KEYWORDS.items():
    for _keyword in _keywords:
        _RULE_INCOME[_keyword] = _category
_RULE_INCOME = {k: v for k, v in sorted(_RULE_INCOME.items(), key=lambda kv: len(kv[0]), reverse=True)}


@dataclass
class Categorization:
    category: str
    confidence: float
    source: str


class Categorizer:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _train(self):
        texts, labels = build_training_rows()
        word = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_features=12000)
        char = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1, max_features=18000)
        model = make_pipeline(
            FeatureUnion([("word", word), ("char", char)]),
            LogisticRegression(max_iter=1500, C=6.0, class_weight="balanced", n_jobs=None),
        )
        model.fit(texts, labels)
        return model

    @property
    def model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._model = self._train()
        return self._model

    def _match_rule(self, text: str, kind: str) -> tuple[str, float] | None:
        normalized = normalize_text(text)
        rules = _RULE_INCOME if kind == "income" else _RULE_EXPENSE
        for phrase, category in rules.items():
            if not phrase:
                continue
            pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
            if re.search(pattern, normalized):
                confidence = 0.97 if " " in phrase else 0.92
                return category, confidence
        return None

    def predict(self, description: str, kind: str = "expense") -> Categorization:
        if not (description or "").strip():
            return Categorization("Other" if kind == "expense" else "Other Income", 0.0, "fallback")
        rule = self._match_rule(description, kind)
        if kind == "income":
            if rule:
                return Categorization(*rule, "rule")
            return Categorization("Other Income", 0.35, "fallback")
        if rule and rule[1] >= 0.95:
            return Categorization(*rule, "rule")
        probabilities = self.model.predict_proba([description])[0]
        classes = self.model.classes_
        best = int(np.argmax(probabilities))
        ml_category = str(classes[best])
        ml_confidence = float(probabilities[best])
        if rule and (rule[0] == ml_category or rule[1] >= 0.92):
            return Categorization(rule[0], max(rule[1], ml_confidence), "rule")
        if ml_confidence >= 0.32:
            return Categorization(ml_category, ml_confidence, "ml")
        if rule:
            return Categorization(*rule, "rule")
        return Categorization("Other", ml_confidence, "fallback")

    def predict_proba(self, description: str) -> dict[str, float]:
        probabilities = self.model.predict_proba([description])[0]
        return {str(c): round(float(p), 4) for c, p in zip(self.model.classes_, probabilities)}


categorizer = Categorizer()


def categorise_transaction(
    description: str,
    kind: str,
    provided_category: str | None = None,
    user_id: int | None = None,
) -> Categorization:
    if provided_category:
        normalized = normalize_category(provided_category, kind)
        if normalized in (EXPENSE_CATEGORIES if kind == "expense" else INCOME_CATEGORIES):
            return Categorization(normalized, 1.0, "manual")
    if kind == "income":
        return categorizer.predict(description, "income")
    if user_id:
        memory = (
            Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.kind == "expense",
                Transaction.category_source == "manual",
            )
            .order_by(Transaction.id.desc())
            .limit(25)
            .all()
        )
        target = normalize_text(description)
        for previous in memory:
            if target and normalize_text(previous.description) == target:
                return Categorization(previous.category, 1.0, "memory")
    return categorizer.predict(description, "expense")


def category_distribution(description: str) -> list[dict]:
    proba = categorizer.predict_proba(description)
    return [
        {"category": category, "probability": probability}
        for category, probability in sorted(proba.items(), key=lambda kv: kv[1], reverse=True)[:5]
    ]
