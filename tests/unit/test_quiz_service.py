import pytest
from app.providers.mock_provider import MockProvider
from app.schemas.quiz import DifficultyLevel, GeneratedQuestion, QuestionOption, QuestionType, QuizGenerationRequest
from app.services.quiz_service import QuizService


@pytest.mark.asyncio
async def test_quiz_service_generates_exact_count():
    mock_provider = MockProvider()
    # Set mock to return 3 questions
    mock_provider.set_mock_structured_data({
        "title": "Photosynthesis Quiz",
        "description": "Assessment on light and dark reactions",
        "questions": [
            {
                "id": 1,
                "question_type": "multiple_choice",
                "difficulty": "easy",
                "topic": "Biology",
                "points": 1.0,
                "question_text": "Where does photosynthesis occur?",
                "options": [
                    {"key": "A", "text": "Chloroplasts", "is_correct": True},
                    {"key": "B", "text": "Mitochondria", "is_correct": False, "distractor_explanation": "Mitochondria produce ATP in respiration."}
                ],
                "correct_answer": "A",
                "explanation": "Chloroplasts contain chlorophyll."
            },
            {
                "id": 2,
                "question_type": "short_answer",
                "difficulty": "medium",
                "topic": "Biology",
                "points": 1.0,
                "question_text": "What is the primary pigment used in photosynthesis?",
                "correct_answer": "Chlorophyll",
                "explanation": "Chlorophyll absorbs red and blue light."
            },
            {
                "id": 3,
                "question_type": "short_answer",
                "difficulty": "hard",
                "topic": "Biology",
                "points": 1.0,
                "question_text": "Explain the Calvin cycle briefly.",
                "correct_answer": "Fixes CO2 into glucose.",
                "explanation": "Occurs in stroma."
            }
        ]
    })

    service = QuizService(provider=mock_provider)
    request = QuizGenerationRequest(
        lesson_contents=["Photosynthesis occurs in chloroplasts. Chlorophyll absorbs sunlight."],
        question_count=3,
        allowed_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_ANSWER]
    )

    draft = await service.generate_quiz_draft(request)
    assert len(draft.questions) == 3
    assert draft.questions[0].id == 1
    assert draft.questions[1].id == 2
    assert draft.questions[2].id == 3
    assert draft.requires_teacher_approval is True
    assert draft.cached is False


@pytest.mark.asyncio
async def test_quiz_service_caching():
    mock_provider = MockProvider()
    mock_provider.set_mock_structured_data({
        "title": "Cached Quiz",
        "description": "Cached assessment",
        "questions": [
            {
                "id": 1,
                "question_type": "short_answer",
                "difficulty": "easy",
                "topic": "Math",
                "points": 1.0,
                "question_text": "What is 5 x 5?",
                "correct_answer": "25",
                "explanation": "5 squared is 25."
            }
        ]
    })

    service = QuizService(provider=mock_provider)
    request = QuizGenerationRequest(
        lesson_contents=["Multiplication basics."],
        question_count=1,
        allowed_types=[QuestionType.SHORT_ANSWER]
    )

    first_call = await service.generate_quiz_draft(request)
    assert first_call.cached is False

    # Second call with identical constraints should hit cache
    second_call = await service.generate_quiz_draft(request)
    assert second_call.cached is True
    assert len(second_call.questions) == 1
