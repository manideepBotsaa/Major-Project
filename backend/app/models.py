"""Database models for Clearpath.

Money is stored as ``Numeric(14, 2)`` (never float) to avoid rounding drift.
Free-text transaction descriptions and notes are encrypted at rest via
``EncryptedText``; analytics only query non-sensitive columns.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .security import EncryptedText
from .utils import money_str, month_key


def utcnow() -> datetime:
    """Naive UTC timestamp, stored consistently by SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    language = db.Column(db.String(10), nullable=False, default="en")
    risk_profile = db.Column(db.String(20), nullable=False, default="moderate")
    monthly_income = db.Column(db.Numeric(14, 2), nullable=True)
    onboarded = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    transactions = db.relationship("Transaction", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    budgets = db.relationship("Budget", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    goals = db.relationship("Goal", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    debts = db.relationship("Debt", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    assets = db.relationship("Asset", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    nudges = db.relationship("Nudge", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    activities = db.relationship("ActivityEvent", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    chat_sessions = db.relationship("ChatSession", backref="user", cascade="all, delete-orphan", lazy="dynamic")
    literacy_progress = db.relationship("LiteracyProgress", backref="user", cascade="all, delete-orphan", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "currency": self.currency,
            "language": self.language,
            "risk_profile": self.risk_profile,
            "monthly_income": money_str(self.monthly_income) if self.monthly_income is not None else None,
            "onboarded": self.onboarded,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Transaction(db.Model):
    __tablename__ = "transaction"
    __table_args__ = (
        db.UniqueConstraint("user_id", "fingerprint", name="uq_transaction_user_fingerprint"),
        db.Index("ix_transaction_user_date", "user_id", "transaction_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False)  # income | expense
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    category = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(EncryptedText, nullable=False, default="")
    notes = db.Column(EncryptedText, nullable=False, default="")
    transaction_date = db.Column(db.Date, nullable=False, index=True)
    recurring = db.Column(db.Boolean, nullable=False, default=False)
    source = db.Column(db.String(20), nullable=False, default="manual")  # manual|csv|demo|import
    category_source = db.Column(db.String(20), nullable=False, default="manual")  # manual|rule|ml|memory
    category_confidence = db.Column(db.Float, nullable=False, default=1.0)
    is_flagged = db.Column(db.Boolean, nullable=False, default=False)
    fingerprint = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "amount": money_str(self.amount),
            "category": self.category,
            "description": self.description or "",
            "notes": self.notes or "",
            "date": self.transaction_date.isoformat(),
            "month": month_key(self.transaction_date),
            "recurring": bool(self.recurring),
            "source": self.source,
            "category_source": self.category_source,
            "category_confidence": round(float(self.category_confidence or 0), 3),
            "flagged": bool(self.is_flagged),
        }


class Budget(db.Model):
    __tablename__ = "budget"
    __table_args__ = (
        db.UniqueConstraint("user_id", "category", "month", name="uq_budget_user_category_month"),
        db.Index("ix_budget_user_month", "user_id", "month"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    category = db.Column(db.String(60), nullable=False)
    month = db.Column(db.Date, nullable=False)  # first day of month
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    rollover = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "month": month_key(self.month),
            "amount": money_str(self.amount),
            "rollover": bool(self.rollover),
        }


class Goal(db.Model):
    __tablename__ = "goal"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(40), nullable=False, default="General")
    target_amount = db.Column(db.Numeric(14, 2), nullable=False)
    initial_amount = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    monthly_contribution = db.Column(db.Numeric(14, 2), nullable=False, default=Decimal("0"))
    target_date = db.Column(db.Date, nullable=True)
    expected_return = db.Column(db.Float, nullable=False, default=8.0)  # annual %
    priority = db.Column(db.Integer, nullable=False, default=2)  # 1 high .. 3 low
    notes = db.Column(db.String(500), nullable=False, default="")
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    contributions = db.relationship(
        "GoalContribution", backref="goal", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def saved_amount(self) -> Decimal:
        return Decimal(self.initial_amount or 0) + sum(
            (Decimal(c.amount) for c in self.contributions), Decimal("0")
        )

    def as_dict(self) -> dict:
        saved = self.saved_amount
        target = Decimal(self.target_amount or 0)
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "target_amount": money_str(target),
            "saved_amount": money_str(saved),
            "initial_amount": money_str(self.initial_amount),
            "monthly_contribution": money_str(self.monthly_contribution),
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "expected_return": float(self.expected_return or 0),
            "priority": self.priority,
            "progress": round(float(saved / target * 100), 1) if target else 0.0,
            "notes": self.notes,
            "archived": bool(self.archived),
        }


class GoalContribution(db.Model):
    __tablename__ = "goal_contribution"

    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goal.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    contribution_date = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "goal_id": self.goal_id,
            "amount": money_str(self.amount),
            "date": self.contribution_date.isoformat(),
            "note": self.note,
        }


class Debt(db.Model):
    __tablename__ = "debt"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    debt_type = db.Column(db.String(40), nullable=False, default="personal_loan")
    balance = db.Column(db.Numeric(14, 2), nullable=False)
    apr = db.Column(db.Float, nullable=False, default=12.0)
    minimum_payment = db.Column(db.Numeric(14, 2), nullable=False)
    due_day = db.Column(db.Integer, nullable=True)
    credit_limit = db.Column(db.Numeric(14, 2), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "debt_type": self.debt_type,
            "balance": money_str(self.balance),
            "apr": round(float(self.apr or 0), 2),
            "minimum_payment": money_str(self.minimum_payment),
            "due_day": self.due_day,
            "credit_limit": money_str(self.credit_limit) if self.credit_limit is not None else None,
            "utilization": round(float(Decimal(self.balance) / Decimal(self.credit_limit) * 100), 1)
            if self.credit_limit else None,
        }


class Asset(db.Model):
    __tablename__ = "asset"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    asset_type = db.Column(db.String(40), nullable=False, default="cash")  # cash, investment, property, retirement, other
    value = db.Column(db.Numeric(14, 2), nullable=False)
    is_liquid = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "asset_type": self.asset_type,
            "value": money_str(self.value),
            "is_liquid": bool(self.is_liquid),
        }


class Nudge(db.Model):
    __tablename__ = "nudge"
    __table_args__ = (
        db.UniqueConstraint("user_id", "dedupe_key", name="uq_nudge_user_dedupe"),
        db.Index("ix_nudge_user_status", "user_id", "status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    rule_id = db.Column(db.String(60), nullable=False)
    dedupe_key = db.Column(db.String(160), nullable=False)
    severity = db.Column(db.String(20), nullable=False, default="info")  # info|attention|critical
    priority = db.Column(db.Integer, nullable=False, default=50)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.String(600), nullable=False)
    action_label = db.Column(db.String(80), nullable=False, default="Got it")
    action_type = db.Column(db.String(40), nullable=False, default="ack")
    payload = db.Column(db.JSON, nullable=False, default=dict)
    points = db.Column(db.Integer, nullable=False, default=5)
    status = db.Column(db.String(20), nullable=False, default="active")  # active|accepted|dismissed|snoozed|expired
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    responded_at = db.Column(db.DateTime, nullable=True)
    snoozed_until = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "priority": self.priority,
            "title": self.title,
            "body": self.body,
            "action_label": self.action_label,
            "action_type": self.action_type,
            "payload": self.payload or {},
            "points": self.points,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActivityEvent(db.Model):
    __tablename__ = "activity_event"
    __table_args__ = (db.Index("ix_activity_user_date", "user_id", "occurred_on"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    event_type = db.Column(db.String(40), nullable=False)
    description = db.Column(db.String(200), nullable=False, default="")
    points = db.Column(db.Integer, nullable=False, default=0)
    occurred_on = db.Column(db.Date, nullable=False, default=date.today)
    meta = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.event_type,
            "description": self.description,
            "points": self.points,
            "date": self.occurred_on.isoformat(),
            "meta": self.meta or {},
        }


class ChatSession(db.Model):
    __tablename__ = "chat_session"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False, default="New conversation")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    messages = db.relationship(
        "ChatMessage", backref="session", cascade="all, delete-orphan", lazy="selectin",
        order_by="ChatMessage.id",
    )

    def as_dict(self, include_messages: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages),
        }
        if include_messages:
            data["messages"] = [m.as_dict() for m in self.messages]
        return data


class ChatMessage(db.Model):
    __tablename__ = "chat_message"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # user|assistant|system
    content = db.Column(db.Text, nullable=False)
    tool_trace = db.Column(db.JSON, nullable=False, default=list)
    citations = db.Column(db.JSON, nullable=False, default=list)
    verification = db.Column(db.JSON, nullable=False, default=dict)
    provider = db.Column(db.String(40), nullable=False, default="mock")
    latency_ms = db.Column(db.Integer, nullable=False, default=0)
    rating = db.Column(db.Integer, nullable=True)  # -1 | 1
    feedback = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "tool_trace": self.tool_trace or [],
            "citations": self.citations or [],
            "verification": self.verification or {},
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "rating": self.rating,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class LiteracyModule(db.Model):
    __tablename__ = "literacy_module"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    level = db.Column(db.String(20), nullable=False)  # beginner|intermediate|advanced
    summary = db.Column(db.String(400), nullable=False)
    content = db.Column(db.Text, nullable=False)
    minutes = db.Column(db.Integer, nullable=False, default=6)
    tags = db.Column(db.JSON, nullable=False, default=list)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    questions = db.relationship(
        "QuizQuestion", backref="module", cascade="all, delete-orphan", lazy="selectin",
        order_by="QuizQuestion.id",
    )

    def as_dict(self, include_content: bool = False, include_answers: bool = False) -> dict:
        data = {
            "id": self.id,
            "slug": self.slug,
            "title": self.title,
            "level": self.level,
            "summary": self.summary,
            "minutes": self.minutes,
            "tags": self.tags or [],
            "sort_order": self.sort_order,
            "quiz_count": len(self.questions),
        }
        if include_content:
            data["content"] = self.content
            data["quiz"] = [
                q.as_dict(include_answer=include_answers) for q in self.questions
            ]
        return data


class QuizQuestion(db.Model):
    __tablename__ = "quiz_question"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("literacy_module.id"), nullable=False, index=True)
    prompt = db.Column(db.String(500), nullable=False)
    options = db.Column(db.JSON, nullable=False, default=list)
    correct_index = db.Column(db.Integer, nullable=False)
    explanation = db.Column(db.String(600), nullable=False, default="")

    def as_dict(self, include_answer: bool = False) -> dict:
        data = {"id": self.id, "prompt": self.prompt, "options": self.options}
        if include_answer:
            data["correct_index"] = self.correct_index
            data["explanation"] = self.explanation
        return data


class LiteracyProgress(db.Model):
    __tablename__ = "literacy_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "module_id", name="uq_progress_user_module"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("literacy_module.id"), nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="started")  # started|completed
    last_viewed = db.Column(db.DateTime, nullable=False, default=utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    best_score = db.Column(db.Integer, nullable=False, default=0)
    attempts = db.Column(db.Integer, nullable=False, default=0)

    module = db.relationship("LiteracyModule")


class QuizAttempt(db.Model):
    __tablename__ = "quiz_attempt"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    module_id = db.Column(db.Integer, db.ForeignKey("literacy_module.id"), nullable=False, index=True)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    answers = db.Column(db.JSON, nullable=False, default=list)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
