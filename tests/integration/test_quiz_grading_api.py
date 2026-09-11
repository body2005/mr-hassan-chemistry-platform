import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_generate_quiz_draft(async_client: AsyncClient):
    payload = {
        "lesson_contents": [
            "Photosynthesis is the process by which green plants convert light energy into chemical energy."
        ],
        "question_count": 2,
        "allowed_types": ["multiple_choice", "short_answer"],
        "target_points_per_question": 2.0
    }
    response = await async_client.post("/api/v1/quiz/draft", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["questions"]) == 2
    assert data["requires_teacher_approval"] is True
    assert data["cached"] is False

    # Second identical call should hit cache
    response_cached = await async_client.post("/api/v1/quiz/draft", json=payload)
    assert response_cached.status_code == 200
    assert response_cached.json()["cached"] is True


@pytest.mark.asyncio
async def test_api_grade_essay(async_client: AsyncClient):
    payload = {
        "question_prompt": "Explain Newton's third law of motion.",
        "student_submission": "For every action in nature there is an equal and opposite reaction.",
        "rubric": [
            {
                "id": "c1",
                "name": "Scientific Accuracy",
                "description": "States the law accurately",
                "max_points": 10.0
            }
        ],
        "max_score": 10.0,
        "question_type": "essay"
    }
    response = await async_client.post("/api/v1/grading/essay", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_score"] >= 0
    assert data["max_score"] == 10.0
    assert "confidence_score" in data
    assert data["requires_teacher_approval"] is True


@pytest.mark.asyncio
async def test_api_grade_essay_rejects_objective_type(async_client: AsyncClient):
    payload = {
        "question_prompt": "Select the correct option",
        "student_submission": "B",
        "rubric": [
            {"id": "c1", "name": "Correctness", "description": "Accurate option", "max_points": 1.0}
        ],
        "max_score": 1.0,
        "question_type": "multiple_choice"
    }
    response = await async_client.post("/api/v1/grading/essay", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "UNSUPPORTED_OBJECTIVE_GRADING_TYPE"
