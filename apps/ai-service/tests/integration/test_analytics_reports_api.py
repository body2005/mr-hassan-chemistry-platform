import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_api_analytics_interpret(async_client: AsyncClient):
    payload = {
        "course_name": "Organic Chemistry",
        "assessment_name": "Quiz 2",
        "total_students": 50,
        "completion_rate": 0.98,
        "average_score": 68.5,
        "median_score": 70.0,
        "score_std_dev": 12.0,
        "question_stats": [
            {
                "question_id": "q1",
                "topic": "SN2 Reactions",
                "pass_rate": 0.50,
                "average_score_ratio": 0.52
            }
        ]
    }
    resp = await async_client.post("/api/v1/analytics/interpret", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "key_findings" in data
    assert "actionable_recommendations" in data
    assert "ta_summary" in data


@pytest.mark.asyncio
async def test_api_reports_narrative(async_client: AsyncClient):
    payload = {
        "course_title": "World History",
        "target_audience": "instructors",
        "total_enrolled": 100,
        "completion_rate_overall": 0.88,
        "at_risk_students_count": 12,
        "modules": [
            {
                "module_title": "The Renaissance",
                "completion_rate": 0.92,
                "average_quiz_score": 82.0
            }
        ]
    }
    resp = await async_client.post("/api/v1/reports/narrative", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "executive_summary" in data
    assert "full_markdown_report" in data
