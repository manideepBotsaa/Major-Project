from __future__ import annotations

from app.models import LiteracyModule

from .helpers import make_user


def test_literacy_curriculum_is_seeded(client):
    make_user(client)
    response = client.get("/api/literacy/modules")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 12
    assert body["levels"] == {"beginner": 5, "intermediate": 5, "advanced": 2}
    assert sum(item["quiz_count"] for item in body["modules"]) == 36


def test_module_view_and_quiz_flow(client, app):
    make_user(client)
    detail = client.get("/api/literacy/modules/emergency-fund")
    assert detail.status_code == 200
    module = detail.get_json()["module"]
    assert module["content"].startswith("#")
    assert len(module["quiz"]) == 3
    assert "correct_index" not in module["quiz"][0]
    assert client.get("/api/literacy/progress").get_json()["completed"] == 0

    with app.app_context():
        row = LiteracyModule.query.filter_by(slug="emergency-fund").first()
        answers = [q.correct_index for q in row.questions]

    passed = client.post("/api/literacy/modules/emergency-fund/quiz", json={"answers": answers})
    assert passed.status_code == 200
    result = passed.get_json()
    assert result["passed"] is True
    assert result["score"] == 3
    assert result["points_awarded"] > 0
    progress = client.get("/api/literacy/progress").get_json()
    assert progress["completed"] == 1
    assert progress["completion_pct"] > 0

    failed = client.post("/api/literacy/modules/emergency-fund/quiz", json={"answers": [0, 0, 0]})
    assert failed.status_code == 200
    assert failed.get_json()["score"] <= 1


def test_quiz_validation_and_search(client):
    make_user(client)
    assert client.post("/api/literacy/modules/emergency-fund/quiz", json={"answers": [1]}).status_code == 400
    assert client.post("/api/literacy/modules/nope/quiz", json={"answers": []}).status_code == 404
    search = client.get("/api/literacy/search?q=emergency%20fund")
    assert search.status_code == 200
    assert search.get_json()["results"]
    assert client.get("/api/literacy/search?q=").status_code == 400
