import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_predict_student_risk(async_client: AsyncClient):
    payload = {
        "students": [
            {
                "student_id": "std_101",
                "cohort_id": "cs101_fall",
                "course_id": "cs101",
                "login_frequency_weekly": 1.2,
                "assignments_submitted_ratio": 0.45,
                "average_quiz_score": 52.0,
                "late_submissions_count": 3,
                "forum_posts_count": 0,
                "time_spent_hours_weekly": 1.5,
                "video_watch_completion_ratio": 0.25,
                "days_since_last_activity": 8
            }
        ]
    }
    response = await async_client.post("/api/v1/risk/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["total_students"] == 1
    assert len(data["predictions"]) == 1
    pred = data["predictions"][0]
    assert 0.0 <= pred["risk_score"] <= 1.0
    assert pred["risk_level"] in ["moderate", "high", "critical"]
    assert len(pred["top_risk_factors"]) > 0


@pytest.mark.asyncio
async def test_api_train_risk_model(async_client: AsyncClient):
    payload = {
        "training_data": [
            {
                "student_id": f"s_{i}",
                "cohort_id": f"cohort_{i % 2}",
                "login_frequency_weekly": 3.0 + (i % 5),
                "assignments_submitted_ratio": 0.5 + (0.05 * (i % 10)),
                "average_quiz_score": 60.0 + (i % 30),
                "late_submissions_count": i % 2,
                "forum_posts_count": i % 3,
                "time_spent_hours_weekly": 4.0,
                "video_watch_completion_ratio": 0.7,
                "days_since_last_activity": i % 4,
                "is_at_risk": int(i % 2 == 0)
            }
            for i in range(20)
        ],
        "model_type": "logistic_regression",
        "n_splits": 2
    }
    response = await async_client.post("/api/v1/risk/train", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "Stratified" in data["grouping_strategy_used"]
