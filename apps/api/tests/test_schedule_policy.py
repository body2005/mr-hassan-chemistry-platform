from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_video_protection import _csrf, _login, _setup_world

from app.main import app
from app.services.scheduling import require_upcoming_time


def test_schedule_policy_keeps_current_minute_and_unchanged_history():
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    require_upcoming_time(now)
    require_upcoming_time(None)
    past = now - timedelta(days=1)
    require_upcoming_time(past, existing=past)
    with pytest.raises(HTTPException) as error:
        require_upcoming_time(past)
    assert error.value.status_code == 422


def test_api_rejects_past_lesson_and_calendar_schedules(db, tmp_path, monkeypatch):
    inst, teacher, student, _, lesson = _setup_world(db, tmp_path, monkeypatch)
    client = TestClient(app)
    _login(client, teacher, inst.slug)
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    lesson_payload = {
        "title": "Scheduled lesson",
        "kind": "video",
        "position": 2,
        "publish_at": past,
    }
    response = client.post(
        f"/api/v1/courses/{lesson.course_id}/lessons", json=lesson_payload, headers=_csrf(client)
    )
    assert response.status_code == 422 and "الماضي" in response.text
    calendar = {
        "title": "Scheduled event",
        "event_type": "lesson",
        "starts_at": past,
        "course_id": str(lesson.course_id),
    }
    assert client.post("/api/v1/calendar", json=calendar, headers=_csrf(client)).status_code == 422
    for path, body in (
        (
            "quizzes",
            {"course_id": str(lesson.course_id), "title": "Scheduled exam", "starts_at": past},
        ),
        (
            "assignments",
            {
                "course_id": str(lesson.course_id),
                "title": "Scheduled homework",
                "prompt": "Explain the answer",
                "starts_at": past,
            },
        ),
        (
            "notifications",
            {
                "recipient_id": str(student.id),
                "kind": "lesson",
                "title": "Scheduled notice",
                "message": "New lesson",
                "scheduled_for": past,
            },
        ),
    ):
        rejected = client.post(f"/api/v1/{path}", json=body, headers=_csrf(client))
        assert rejected.status_code == 422, rejected.text
        assert "الماضي" in rejected.text
    lesson_payload["publish_at"] = future
    assert (
        client.post(
            f"/api/v1/courses/{lesson.course_id}/lessons",
            json=lesson_payload,
            headers=_csrf(client),
        ).status_code
        == 201
    )
    # Existing schedules remain editable without changing their historical time.
    lesson.publish_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    original = lesson.publish_at.replace(tzinfo=UTC).isoformat()
    publication = {
        "publication_status": "published",
        "publish_at": original,
        "announce_to_students": False,
    }
    assert (
        client.patch(
            f"/api/v1/lessons/{lesson.id}/publication", json=publication, headers=_csrf(client)
        ).status_code
        == 200
    )
    publication["publish_at"] = past
    assert (
        client.patch(
            f"/api/v1/lessons/{lesson.id}/publication", json=publication, headers=_csrf(client)
        ).status_code
        == 422
    )
