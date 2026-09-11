import pytest
from app.core.exceptions import UnsupportedGradingTypeException
from app.providers.mock_provider import MockProvider
from app.schemas.grading import OBJECTIVE_QUESTION_TYPES, EssayGradingRequest, RubricCriterionInput
from app.services.grading_service import GradingService


@pytest.mark.asyncio
async def test_grading_service_proposes_score_with_confidence():
    mock_provider = MockProvider()
    mock_provider.set_mock_structured_data({
        "criteria_scores": [
            {
                "criterion_id": "c1",
                "criterion_name": "Thesis Clarity",
                "score_awarded": 4.5,
                "max_points": 5.0,
                "feedback": "Clear and well-formulated thesis statement."
            },
            {
                "criterion_id": "c2",
                "criterion_name": "Evidence & Analysis",
                "score_awarded": 4.0,
                "max_points": 5.0,
                "feedback": "Good evidence cited, could deepen historical analysis."
            }
        ],
        "feedback_summary": "Strong submission demonstrating clear analytical grasp.",
        "confidence_score": 0.92
    })

    service = GradingService(provider=mock_provider)
    request = EssayGradingRequest(
        question_prompt="Analyze the primary causes of the Industrial Revolution.",
        student_submission="The Industrial Revolution began in Britain due to coal access, capital from trade, and agricultural improvements.",
        rubric=[
            RubricCriterionInput(id="c1", name="Thesis Clarity", description="Well-defined thesis", max_points=5.0),
            RubricCriterionInput(id="c2", name="Evidence & Analysis", description="Support from historical data", max_points=5.0)
        ],
        max_score=10.0
    )

    result = await service.grade_essay(request)
    assert result.total_score == 8.5
    assert result.percentage == 85.0
    assert result.confidence_score == 0.92
    assert result.flagged_for_human_review is False
    assert result.requires_teacher_approval is True
    assert len(result.criteria_breakdown) == 2


def test_grading_service_rejects_objective_question_types():
    assert "mcq" in OBJECTIVE_QUESTION_TYPES
    assert "multiple_choice" in OBJECTIVE_QUESTION_TYPES
    assert "true_false" in OBJECTIVE_QUESTION_TYPES
    assert "matching" in OBJECTIVE_QUESTION_TYPES
    assert "ordering" in OBJECTIVE_QUESTION_TYPES

    exc = UnsupportedGradingTypeException("mcq")
    assert exc.status_code == 400
    assert "objective" in exc.message.lower()
