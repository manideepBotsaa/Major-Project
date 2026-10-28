"""Budgets, goals, debts and assets endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from flask import Blueprint, jsonify, request

from ..categories import EXPENSE_CATEGORIES, normalize_category
from ..errors import body, current_user, error, require_user
from ..extensions import db
from ..models import Asset, Budget, Debt, Goal, GoalContribution
from ..services.analytics import net_worth
from ..services.budgeting import budget_status, copy_budgets, delete_budget, suggest_budgets, upsert_budget
from ..services.calculators import debt_plan
from ..services.goals import goal_overview, goal_status
from ..services.nudges import award_points
from ..utils import as_float, money_str, parse_date, parse_month, today


planning_bp = Blueprint("planning", __name__)


# ---------------------------------------------------------------------------
# Budgets
# ---------------------------------------------------------------------------
def _month_param(default: date | None = None) -> date:
    raw = request.args.get("month") or body().get("month")
    return parse_month(raw, default or today().replace(day=1))


@planning_bp.get("/budgets")
@require_user
def get_budgets():
    user = current_user()
    try:
        month = _month_param()
    except ValueError:
        return error("month must use YYYY-MM")
    status = budget_status(user.id, month)
    return jsonify(
        {
            "status": status,
            "suggestions": suggest_budgets(user.id, month),
            "available_categories": EXPENSE_CATEGORIES,
        }
    )


@planning_bp.post("/budgets")
@require_user
def create_budget():
    user = current_user()
    data = body()
    category = normalize_category(str(data.get("category", "")))
    amount = as_float(data.get("amount"))
    if amount <= 0:
        return error("Budget amount must be positive")
    try:
        month = parse_month(data.get("month"), today().replace(day=1))
    except ValueError:
        return error("month must use YYYY-MM")
    budget = upsert_budget(user.id, category, month, amount, bool(data.get("rollover")))
    return jsonify({"budget": budget.as_dict(), "status": budget_status(user.id, month)}), 201


@planning_bp.patch("/budgets/<int:budget_id>")
@require_user
def update_budget(budget_id):
    user = current_user()
    budget = Budget.query.filter_by(id=budget_id, user_id=user.id).first()
    if not budget:
        return error("Budget not found", 404, "not_found")
    data = body()
    if "amount" in data:
        amount = as_float(data["amount"])
        if amount <= 0:
            return error("Budget amount must be positive")
        budget.amount = Decimal(str(round(amount, 2)))
    if "rollover" in data:
        budget.rollover = bool(data["rollover"])
    db.session.commit()
    return jsonify({"budget": budget.as_dict(), "status": budget_status(user.id, budget.month)})


@planning_bp.delete("/budgets/<int:budget_id>")
@require_user
def remove_budget(budget_id):
    if not delete_budget(current_user().id, budget_id):
        return error("Budget not found", 404, "not_found")
    return jsonify({"ok": True})


@planning_bp.post("/budgets/copy")
@require_user
def copy_month_budgets():
    data = body()
    try:
        source = parse_month(data.get("from_month"), today().replace(day=1))
        target = parse_month(data.get("to_month"), today().replace(day=1))
    except ValueError:
        return error("from_month and to_month must use YYYY-MM")
    count = copy_budgets(current_user().id, source, target)
    return jsonify({"copied": count, "status": budget_status(current_user().id, target)})


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------
@planning_bp.get("/goals")
@require_user
def get_goals():
    return jsonify(goal_overview(current_user().id))


@planning_bp.post("/goals")
@require_user
def create_goal():
    user = current_user()
    data = body()
    try:
        target = as_float(data.get("target_amount"))
        if target <= 0:
            return error("Target amount must be positive")
        target_date = parse_date(data["target_date"]) if data.get("target_date") else None
        goal = Goal(
            user_id=user.id,
            name=str(data.get("name", "")).strip()[:120] or "New goal",
            category=str(data.get("category", "General"))[:40],
            target_amount=Decimal(str(round(target, 2))),
            initial_amount=Decimal(str(round(max(0.0, as_float(data.get("initial_amount"))), 2))),
            monthly_contribution=Decimal(str(round(max(0.0, as_float(data.get("monthly_contribution"))), 2))),
            target_date=target_date,
            expected_return=max(0.0, min(30.0, as_float(data.get("expected_return"), 8.0))),
            priority=max(1, min(3, int(as_float(data.get("priority"), 2)))),
            notes=str(data.get("notes", ""))[:500],
        )
        db.session.add(goal)
        db.session.commit()
    except ValueError as exc:
        return error(str(exc))
    return jsonify({"goal": goal_status(goal), "overview": goal_overview(user.id)}), 201


def _get_goal(user_id: int, goal_id: int) -> Goal | None:
    return Goal.query.filter_by(id=goal_id, user_id=user_id).first()


@planning_bp.get("/goals/<int:goal_id>")
@require_user
def get_goal(goal_id):
    goal = _get_goal(current_user().id, goal_id)
    if not goal:
        return error("Goal not found", 404, "not_found")
    return jsonify(
        {
            "goal": goal_status(goal),
            "contributions": [c.as_dict() for c in sorted(goal.contributions, key=lambda c: c.contribution_date, reverse=True)],
        }
    )


@planning_bp.patch("/goals/<int:goal_id>")
@require_user
def update_goal(goal_id):
    user = current_user()
    goal = _get_goal(user.id, goal_id)
    if not goal:
        return error("Goal not found", 404, "not_found")
    data = body()
    try:
        if "name" in data:
            name = str(data["name"]).strip()
            if name:
                goal.name = name[:120]
        if "target_amount" in data:
            target = as_float(data["target_amount"])
            if target <= 0:
                return error("Target amount must be positive")
            goal.target_amount = Decimal(str(round(target, 2)))
        if "monthly_contribution" in data:
            goal.monthly_contribution = Decimal(str(round(max(0.0, as_float(data["monthly_contribution"])), 2)))
        if "target_date" in data:
            goal.target_date = parse_date(data["target_date"]) if data["target_date"] else None
        if "expected_return" in data:
            goal.expected_return = max(0.0, min(30.0, as_float(data["expected_return"], 8.0)))
        if "priority" in data:
            goal.priority = max(1, min(3, int(as_float(data["priority"], 2))))
        if "category" in data:
            goal.category = str(data["category"])[:40]
        if "notes" in data:
            goal.notes = str(data["notes"])[:500]
        if "archived" in data:
            goal.archived = bool(data["archived"])
        db.session.commit()
    except ValueError as exc:
        return error(str(exc))
    return jsonify({"goal": goal_status(goal), "overview": goal_overview(user.id)})


@planning_bp.delete("/goals/<int:goal_id>")
@require_user
def delete_goal(goal_id):
    goal = _get_goal(current_user().id, goal_id)
    if not goal:
        return error("Goal not found", 404, "not_found")
    db.session.delete(goal)
    db.session.commit()
    return jsonify({"ok": True})


@planning_bp.post("/goals/<int:goal_id>/contributions")
@require_user
def add_goal_contribution(goal_id):
    user = current_user()
    goal = _get_goal(user.id, goal_id)
    if not goal:
        return error("Goal not found", 404, "not_found")
    data = body()
    amount = as_float(data.get("amount"))
    if amount <= 0:
        return error("Contribution must be positive")
    try:
        contribution_date = parse_date(data.get("date"), today())
    except ValueError:
        return error("date must use YYYY-MM-DD")
    contribution = GoalContribution(
        goal_id=goal.id,
        amount=Decimal(str(round(amount, 2))),
        contribution_date=contribution_date,
        note=str(data.get("note", ""))[:300],
    )
    db.session.add(contribution)
    db.session.commit()
    award_points(user.id, "goal_contribution", 10, f"Contributed to {goal.name}", {"goal_id": goal.id})
    return jsonify({"contribution": contribution.as_dict(), "goal": goal_status(goal)}), 201


@planning_bp.delete("/goals/<int:goal_id>/contributions/<int:contribution_id>")
@require_user
def delete_goal_contribution(goal_id, contribution_id):
    user = current_user()
    goal = _get_goal(user.id, goal_id)
    if not goal:
        return error("Goal not found", 404, "not_found")
    contribution = GoalContribution.query.filter_by(id=contribution_id, goal_id=goal.id).first()
    if not contribution:
        return error("Contribution not found", 404, "not_found")
    db.session.delete(contribution)
    db.session.commit()
    return jsonify({"ok": True, "goal": goal_status(goal)})


# ---------------------------------------------------------------------------
# Debts
# ---------------------------------------------------------------------------
def _debt_payload(data: dict, existing: Debt | None = None) -> dict:
    name = str(data.get("name", existing.name if existing else "")).strip()
    if not name:
        raise ValueError("Debt name is required")
    balance = as_float(data.get("balance", existing.balance if existing else 0))
    if balance < 0:
        raise ValueError("Balance cannot be negative")
    apr = as_float(data.get("apr", existing.apr if existing else 12))
    if apr < 0 or apr > 100:
        raise ValueError("APR must be between 0 and 100")
    minimum = as_float(data.get("minimum_payment", existing.minimum_payment if existing else 0))
    if minimum <= 0:
        raise ValueError("Minimum payment must be positive")
    due_day = data.get("due_day", existing.due_day if existing else None)
    if due_day not in (None, ""):
        due_day = int(as_float(due_day))
        if not 1 <= due_day <= 31:
            raise ValueError("Due day must be between 1 and 31")
    else:
        due_day = None
    credit_limit = data.get("credit_limit", existing.credit_limit if existing else None)
    credit_limit = None if credit_limit in (None, "") else as_float(credit_limit)
    return {
        "name": name[:120],
        "debt_type": str(data.get("debt_type", existing.debt_type if existing else "personal_loan"))[:40],
        "balance": Decimal(str(round(balance, 2))),
        "apr": round(apr, 2),
        "minimum_payment": Decimal(str(round(minimum, 2))),
        "due_day": due_day,
        "credit_limit": Decimal(str(round(credit_limit, 2))) if credit_limit else None,
    }


@planning_bp.get("/debts")
@require_user
def get_debts():
    user = current_user()
    debts = Debt.query.filter_by(user_id=user.id).order_by(Debt.apr.desc()).all()
    extra = as_float(request.args.get("extra"), 0)
    plan = None
    if debts:
        plan = debt_plan(
            [
                {
                    "name": d.name,
                    "balance": float(d.balance),
                    "apr": float(d.apr),
                    "minimum_payment": float(d.minimum_payment),
                }
                for d in debts
            ],
            extra,
        )
    return jsonify({"debts": [d.as_dict() for d in debts], "plan": plan})


@planning_bp.post("/debts")
@require_user
def create_debt():
    user = current_user()
    try:
        values = _debt_payload(body())
    except ValueError as exc:
        return error(str(exc))
    debt = Debt(user_id=user.id, **values)
    db.session.add(debt)
    db.session.commit()
    return jsonify({"debt": debt.as_dict()}), 201


@planning_bp.patch("/debts/<int:debt_id>")
@require_user
def update_debt(debt_id):
    user = current_user()
    debt = Debt.query.filter_by(id=debt_id, user_id=user.id).first()
    if not debt:
        return error("Debt not found", 404, "not_found")
    try:
        values = _debt_payload(body(), debt)
    except ValueError as exc:
        return error(str(exc))
    for key, value in values.items():
        setattr(debt, key, value)
    db.session.commit()
    return jsonify({"debt": debt.as_dict()})


@planning_bp.delete("/debts/<int:debt_id>")
@require_user
def delete_debt(debt_id):
    debt = Debt.query.filter_by(id=debt_id, user_id=current_user().id).first()
    if not debt:
        return error("Debt not found", 404, "not_found")
    db.session.delete(debt)
    db.session.commit()
    return jsonify({"ok": True})


@planning_bp.get("/debts/plan")
@require_user
def get_debt_plan():
    user = current_user()
    debts = Debt.query.filter_by(user_id=user.id).all()
    extra = as_float(request.args.get("extra"), 0)
    plan = debt_plan(
        [
            {
                "name": d.name,
                "balance": float(d.balance),
                "apr": float(d.apr),
                "minimum_payment": float(d.minimum_payment),
            }
            for d in debts
        ],
        extra,
    )
    warnings = []
    for debt in debts:
        if float(debt.minimum_payment) <= float(debt.balance) * float(debt.apr) / 1200:
            warnings.append(
                f"{debt.name}: the minimum payment does not cover monthly interest at {debt.apr:.1f}% APR."
            )
    return jsonify({"plan": plan, "warnings": warnings})


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------
@planning_bp.get("/assets")
@require_user
def get_assets():
    user = current_user()
    assets = Asset.query.filter_by(user_id=user.id).all()
    return jsonify({"assets": [a.as_dict() for a in assets], "net_worth": net_worth(user.id)})


@planning_bp.post("/assets")
@require_user
def create_asset():
    user = current_user()
    data = body()
    name = str(data.get("name", "")).strip()
    value = as_float(data.get("value"))
    if not name or value < 0:
        return error("Asset name and a non-negative value are required")
    asset = Asset(
        user_id=user.id,
        name=name[:120],
        asset_type=str(data.get("asset_type", "cash"))[:40],
        value=Decimal(str(round(value, 2))),
        is_liquid=bool(data.get("is_liquid", True)),
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify({"asset": asset.as_dict(), "net_worth": net_worth(user.id)}), 201


@planning_bp.patch("/assets/<int:asset_id>")
@require_user
def update_asset(asset_id):
    user = current_user()
    asset = Asset.query.filter_by(id=asset_id, user_id=user.id).first()
    if not asset:
        return error("Asset not found", 404, "not_found")
    data = body()
    if "name" in data and str(data["name"]).strip():
        asset.name = str(data["name"]).strip()[:120]
    if "value" in data:
        value = as_float(data["value"])
        if value < 0:
            return error("Asset value cannot be negative")
        asset.value = Decimal(str(round(value, 2)))
    if "asset_type" in data:
        asset.asset_type = str(data["asset_type"])[:40]
    if "is_liquid" in data:
        asset.is_liquid = bool(data["is_liquid"])
    db.session.commit()
    return jsonify({"asset": asset.as_dict(), "net_worth": net_worth(user.id)})


@planning_bp.delete("/assets/<int:asset_id>")
@require_user
def delete_asset(asset_id):
    asset = Asset.query.filter_by(id=asset_id, user_id=current_user().id).first()
    if not asset:
        return error("Asset not found", 404, "not_found")
    db.session.delete(asset)
    db.session.commit()
    return jsonify({"ok": True})
