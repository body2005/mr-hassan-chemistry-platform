from unittest.mock import MagicMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_task_status_endpoint(async_client: AsyncClient):
    with patch("app.api.v1.tasks.AsyncResult") as mock_async_res:
        mock_instance = MagicMock()
        mock_instance.state = "SUCCESS"
        mock_instance.result = {"questions": [{"id": 1, "question_text": "Sample"}]}
        mock_async_res.return_value = mock_instance

        resp = await async_client.get("/api/v1/tasks/mock-task-123")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task_id"] == "mock-task-123"
        assert data["status"] == "completed"
        assert data["result"] is not None


@pytest.mark.asyncio
async def test_api_generate_quiz_draft_async_mode(async_client: AsyncClient):
    with patch("app.tasks.background_jobs.task_batch_generate_quiz.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "async-quiz-task-456"
        mock_delay.return_value = mock_task

        payload = {
            "lesson_contents": ["Lesson text"],
            "question_count": 3,
            "allowed_types": ["multiple_choice"],
            "async_mode": True
        }

        resp = await async_client.post("/api/v1/quiz/draft", json=payload)
        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"] == "async-quiz-task-456"
        assert data["status"] == "queued"
