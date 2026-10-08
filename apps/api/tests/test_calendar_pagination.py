"""Calendar retrieval must not silently lose saved events after row500."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.platform import CalendarEvent
from app.models.user import UserRole
from tests.test_security_and_tenancy import make_institution, make_user, login


def calendar_event(institution, author, ordinal, **changes):
    return CalendarEvent(
        id=uuid.UUID(int=ordinal), institution_id=institution.id,
        creator_id=author.id, title=f"Calendar record {ordinal}",
        event_type="lesson", starts_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        **changes,
    )


def test_calendar_paginates_tied_dates_without_missing_or_repeated_rows(db):
    institution = make_institution(db, "calendar-pages")
    author = make_user(db, institution.id, UserRole.TEACHER, "calendar-author")
    foreign = make_institution(db, "calendar-foreign")
    other = make_user(db, foreign.id, UserRole.TEACHER, "calendar-other")
    db.add_all([calendar_event(institution, author, ordinal) for ordinal in range(1, 502)])
    db.add(calendar_event(foreign, other, 9000))
    db.commit()
    with TestClient(app) as client:
        login(client, author, institution.slug)
        ids = []
        for offset, expected in ((0, 200), (200, 200), (400, 101), (600, 0)):
            page = client.get(f"/api/v1/calendar?limit=200&offset={offset}")
            assert page.status_code == 200, page.text
            records = page.json()
            assert len(records) == expected
            ids.extend(record["id"] for record in records)
        assert ids == [str(uuid.UUID(int=ordinal)) for ordinal in range(1, 502)]
        assert len(set(ids)) == 501
        assert len(client.get("/api/v1/calendar").json()) == 500  # legacy default, not an unbounded read


def test_calendar_student_paging_preserves_publication_and_tenancy_filters(db):
    institution = make_institution(db, "calendar-student-pages")
    author = make_user(db, institution.id, UserRole.TEACHER, "calendar-author")
    learner = make_user(db, institution.id, UserRole.STUDENT, "calendar-learner")
    foreign = make_institution(db, "calendar-student-foreign")
    other = make_user(db, foreign.id, UserRole.TEACHER, "calendar-other")
    db.add_all([
        calendar_event(institution, author, 1, is_published=True),
        calendar_event(institution, author, 2, is_published=False),
        calendar_event(institution, author, 3, is_published=True,
                       cancelled_at=datetime(2026, 10, 1, tzinfo=timezone.utc)),
        calendar_event(foreign, other, 4, is_published=True),
    ])
    db.commit()
    with TestClient(app) as client:
        login(client, learner, institution.slug)
        first = client.get("/api/v1/calendar?limit=1&offset=0")
        assert first.status_code == 200, first.text
        assert [item["id"] for item in first.json()] == [str(uuid.UUID(int=1))]
        second = client.get("/api/v1/calendar?limit=1&offset=1")
        assert second.status_code == 200, second.text
        assert second.json() == []


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "offset=-1", "limit=invalid"])
def test_calendar_rejects_invalid_paging_parameters(db, query):
    institution = make_institution(db, "calendar-invalid-pages")
    author = make_user(db, institution.id, UserRole.TEACHER, "calendar-author")
    with TestClient(app) as client:
        login(client, author, institution.slug)
        assert client.get(f"/api/v1/calendar?{query}").status_code == 422
