"""Financial literacy curriculum, quizzes, and retrieval for grounded answers."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..extensions import db
from ..models import LiteracyModule, LiteracyProgress, QuizAttempt, QuizQuestion
from ..utils import clamp

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "literacy.json"
_index_cache: dict | None = None
_index_signature: tuple | None = None


class LiteracyModuleNotFound(ValueError):
    """Raised when a slug does not match a seeded literacy module."""


def _read_data() -> list[dict]:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def seed_literacy() -> int:
    modules = _read_data()
    for item in modules:
        module = LiteracyModule.query.filter_by(slug=item["slug"]).first()
        if module is None:
            module = LiteracyModule(slug=item["slug"])
            db.session.add(module)
        module.title = item["title"]
        module.level = item["level"]
        module.summary = item["summary"]
        module.content = item["content"]
        module.minutes = int(item.get("minutes", 6))
        module.tags = item.get("tags", [])
        module.sort_order = int(item.get("sort_order", 0))
        db.session.flush()
        existing = {q.prompt: q for q in module.questions}
        for question in item.get("quiz", []):
            row = existing.get(question["prompt"])
            if row is None:
                row = QuizQuestion(module_id=module.id, prompt=question["prompt"])
                db.session.add(row)
            row.options = question["options"]
            row.correct_index = int(question["correct_index"])
            row.explanation = question.get("explanation", "")
    db.session.commit()
    return len(modules)


def list_modules(user_id: int | None = None) -> dict:
    modules = LiteracyModule.query.order_by(LiteracyModule.sort_order, LiteracyModule.id).all()
    progress = {}
    if user_id:
        progress = {p.module_id: p for p in LiteracyProgress.query.filter_by(user_id=user_id).all()}
    items = []
    for module in modules:
        data = module.as_dict()
        state = progress.get(module.id)
        data["progress"] = {
            "status": state.status if state else "not_started",
            "best_score": state.best_score if state else 0,
            "attempts": state.attempts if state else 0,
        }
        items.append(data)
    completed = sum(1 for p in progress.values() if p.status == "completed") if progress else 0
    total = len(items)
    return {
        "modules": items,
        "total": total,
        "completed": completed,
        "completion_pct": round(completed / total * 100, 1) if total else 0,
        "levels": {
            level: sum(1 for m in items if m["level"] == level)
            for level in ("beginner", "intermediate", "advanced")
        },
    }


def get_module(user_id: int, slug: str) -> dict:
    module = LiteracyModule.query.filter_by(slug=slug).first()
    if not module:
        raise LiteracyModuleNotFound("Module not found")
    progress = LiteracyProgress.query.filter_by(user_id=user_id, module_id=module.id).first()
    data = module.as_dict(include_content=True, include_answers=False)
    data["progress"] = {
        "status": progress.status if progress else "not_started",
        "best_score": progress.best_score if progress else 0,
        "attempts": progress.attempts if progress else 0,
    }
    return data


def mark_viewed(user_id: int, slug: str) -> None:
    module = LiteracyModule.query.filter_by(slug=slug).first()
    if not module:
        raise LiteracyModuleNotFound("Module not found")
    progress = LiteracyProgress.query.filter_by(user_id=user_id, module_id=module.id).first()
    if progress is None:
        progress = LiteracyProgress(user_id=user_id, module_id=module.id)
        db.session.add(progress)
    progress.last_viewed = datetime.now(timezone.utc).replace(tzinfo=None)
    if progress.status == "not_started":
        progress.status = "started"
    db.session.commit()


def submit_quiz(user_id: int, slug: str, answers: list) -> dict:
    module = LiteracyModule.query.filter_by(slug=slug).first()
    if not module:
        raise LiteracyModuleNotFound("Module not found")
    questions = module.questions
    if not questions:
        raise ValueError("This module has no quiz")
    if not isinstance(answers, list) or len(answers) != len(questions):
        raise ValueError(f"Expected {len(questions)} answers")
    score = 0
    results = []
    for index, (question, answer) in enumerate(zip(questions, answers)):
        try:
            selected = int(answer)
        except (TypeError, ValueError):
            selected = -1
        correct = selected == question.correct_index
        score += 1 if correct else 0
        results.append(
            {
                "question_id": question.id,
                "prompt": question.prompt,
                "selected": selected,
                "correct_index": question.correct_index,
                "correct": correct,
                "explanation": question.explanation,
            }
        )
    total = len(questions)
    percent = round(score / total * 100, 1)
    progress = LiteracyProgress.query.filter_by(user_id=user_id, module_id=module.id).first()
    first_completion = not progress or progress.status != "completed"
    if progress is None:
        progress = LiteracyProgress(user_id=user_id, module_id=module.id)
        db.session.add(progress)
    progress.attempts += 1
    progress.best_score = max(progress.best_score, score)
    progress.last_viewed = datetime.now(timezone.utc).replace(tzinfo=None)
    if percent >= 60:
        progress.status = "completed"
        progress.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.add(
        QuizAttempt(
            user_id=user_id,
            module_id=module.id,
            score=score,
            total=total,
            answers=answers,
        )
    )
    db.session.commit()
    points = 30 if first_completion and percent >= 60 else 5 if percent >= 60 else 0
    if points:
        from .nudges import award_points

        award_points(
            user_id,
            "quiz_complete",
            points,
            f"Quiz: {module.title} ({score}/{total})",
            {"module": module.slug, "score": score},
            once_per_day=False,
        )
    return {
        "score": score,
        "total": total,
        "percent": percent,
        "passed": percent >= 60,
        "results": results,
        "points_awarded": points,
        "module": module.as_dict(),
    }


def progress_summary(user_id: int) -> dict:
    modules = list_modules(user_id)
    rows = LiteracyProgress.query.filter_by(user_id=user_id).all()
    by_level: dict[str, dict] = {}
    for module in modules["modules"]:
        level = module["level"]
        bucket = by_level.setdefault(level, {"completed": 0, "total": 0})
        bucket["total"] += 1
        if module["progress"]["status"] == "completed":
            bucket["completed"] += 1
    best = max((p.best_score for p in rows), default=0)
    return {
        "completion_pct": modules["completion_pct"],
        "completed": modules["completed"],
        "total": modules["total"],
        "by_level": by_level,
        "attempts": sum(p.attempts for p in rows),
        "best_score": best,
    }


def _build_index() -> dict:
    global _index_cache, _index_signature
    modules = LiteracyModule.query.order_by(LiteracyModule.sort_order).all()
    signature = tuple((m.id, m.slug, len(m.content or "")) for m in modules)
    if _index_cache is not None and _index_signature == signature:
        return _index_cache
    chunks = []
    for module in modules:
        paragraphs = re.split(r"\n\s*\n", module.content or "")
        heading = ""
        buffer = []
        for paragraph in paragraphs:
            stripped = paragraph.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if buffer:
                    chunks.append(_chunk(module, heading, "\n\n".join(buffer)))
                    buffer = []
                heading = stripped.lstrip("#").strip()
                continue
            buffer.append(stripped)
        if buffer:
            chunks.append(_chunk(module, heading, "\n\n".join(buffer)))
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    matrix = vectorizer.fit_transform([c["text"] for c in chunks]) if chunks else None
    _index_cache = {"chunks": chunks, "vectorizer": vectorizer, "matrix": matrix}
    _index_signature = signature
    return _index_cache


def _chunk(module: LiteracyModule, heading: str, text: str) -> dict:
    digest = hashlib.sha1((heading + text[:200]).encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"{module.slug}#{digest}",
        "module_slug": module.slug,
        "module_title": module.title,
        "level": module.level,
        "heading": heading or module.title,
        "text": text.strip(),
    }


def search_knowledge(query: str, k: int = 3) -> list[dict]:
    index = _build_index()
    if not index["chunks"]:
        return []
    if not (query or "").strip():
        return [
            {
                "id": c["id"],
                "title": c["module_title"],
                "heading": c["heading"],
                "text": c["text"][:600],
                "module_slug": c["module_slug"],
                "level": c["level"],
                "score": 0.0,
            }
            for c in index["chunks"][:k]
        ]
    vector = index["vectorizer"].transform([query])
    scores = cosine_similarity(vector, index["matrix"])[0]
    best = np.argsort(scores)[::-1][: max(k * 3, 6)]
    results = []
    seen = set()
    for index_number in best:
        chunk = index["chunks"][int(index_number)]
        key = (chunk["module_slug"], chunk["heading"])
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "id": chunk["id"],
                "title": chunk["module_title"],
                "heading": chunk["heading"],
                "text": chunk["text"][:900],
                "module_slug": chunk["module_slug"],
                "level": chunk["level"],
                "score": round(float(scores[int(index_number)]), 3),
            }
        )
        if len(results) >= k:
            break
    return results
