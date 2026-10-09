"""Actual overlapping PostgreSQL writes for newly found telemetry defect."""
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.progress import LessonProgress, VideoEvent
from .live_helpers import BASE, clear_auth, lesson, pg_engine, session
from .test_audit_concurrency import overlap


@pytest.mark.parametrize('scenario', ['distinct-batches', 'same-batch-replay', 'complete-and-batch'])
def test_concurrent_new_video_batches_have_one_progress_and_exact_watch_time(scenario):
    clear_auth()  # Read-only real limiter wait, not counter erasure.
    engine = pg_engine()
    try:
        with session() as teacher, session('student02@demo.com', 'qa-student-pass') as student:
            course, item = lesson(teacher, 'video')
            assert student.post(f"{BASE}/courses/{course['id']}/enroll", timeout=15).status_code == 200
            def batch(prefix):
                return {'events': [{'lesson_id': item['id'], 'client_event_id': f'{prefix}-{n}', 'event_type': 'play',
                                    'position_seconds': 10, 'watched_delta_seconds': 2, 'duration_seconds': 100} for n in (1, 2)]}
            payload = batch(uuid.uuid4().hex)
            requests = [('POST', '/telemetry/video-events', payload)]
            requests += [('POST', f"/progress/lessons/{item['id']}/complete", {})] if scenario == 'complete-and-batch' else [
                ('POST', '/telemetry/video-events', payload if scenario == 'same-batch-replay' else batch(uuid.uuid4().hex))]
            responses = overlap(student, requests)
            try:
                statuses = [response.status_code for _, response in responses]
                assert statuses == ([202, 200] if scenario == 'complete-and-batch' else [202, 202]), statuses
                if scenario == 'same-batch-replay':
                    assert sorted(response.json()['accepted'] for _, response in responses) == [0, 2]
                    assert sorted(response.json()['duplicates'] for _, response in responses) == [0, 2]
                expected_events = 4 if scenario == 'distinct-batches' else 2
                with Session(engine) as db:
                    rows = db.scalars(select(LessonProgress).where(LessonProgress.lesson_id == uuid.UUID(item['id']))).all()
                    assert len(rows) == 1
                    assert rows[0].watched_duration_seconds == expected_events * 2
                    assert rows[0].completion_percent == (100 if scenario == 'complete-and-batch' else 10)
                    assert db.scalar(select(func.count()).select_from(VideoEvent).where(VideoEvent.lesson_id == uuid.UUID(item['id']))) == expected_events
            finally:
                for client, _ in responses:
                    client.close()
    finally:
        engine.dispose()
