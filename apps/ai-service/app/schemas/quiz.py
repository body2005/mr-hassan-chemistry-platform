from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class QuestionType(str, Enum):
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    CODING = "coding"
    ESSAY = "essay"
    FILL_IN_THE_BLANK = "fill_in_the_blank"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionOption(BaseModel):
    key: str = Field(..., description="Option identifier, e.g. 'A', 'B', 'C', 'D'")
    text: str = Field(..., description="Text of the option")
    is_correct: bool = Field(False, description="Whether this option is the correct answer")
    distractor_explanation: Optional[str] = Field(None, description="Why this distractor is plausible but incorrect")


class RubricCriterion(BaseModel):
    name: str = Field(..., description="Name of the grading criterion (e.g. 'Clarity', 'Accuracy')")
    description: str = Field(..., description="Explanation of what is expected")
    max_points: float = Field(..., gt=0, description="Max points allocatable to this criterion")


class TestCase(BaseModel):
    input: str
    expected_output: str
    is_hidden: bool = False


class GeneratedQuestion(BaseModel):
    id: int = Field(..., ge=1, description="Sequential question number (1-indexed)")
    question_type: QuestionType
    difficulty: DifficultyLevel
    topic: str
    points: float = Field(1.0, gt=0)
    question_text: str
    options: Optional[List[QuestionOption]] = None
    correct_answer: str = Field(..., description="Correct answer text or option key")
    explanation: str = Field(..., description="Pedagogical explanation of the solution")
    rubric: Optional[List[RubricCriterion]] = None
    starter_code: Optional[str] = None
    test_cases: Optional[List[TestCase]] = None
    image_asset_ids: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_question_constraints(self):
        if self.question_type == QuestionType.MULTIPLE_CHOICE:
            if not self.options or len(self.options) < 2:
                raise ValueError("Multiple choice questions must have at least 2 options.")
            correct_opts = [opt for opt in self.options if opt.is_correct]
            if len(correct_opts) != 1:
                raise ValueError(f"Multiple choice question must have exactly 1 correct option, found {len(correct_opts)}.")
        return self


class QuizGenerationRequest(BaseModel):
    lesson_contents: List[str] = Field(..., min_length=1, description="Lesson texts from which to derive questions")
    question_count: int = Field(..., ge=1, le=50, description="Exact number of questions required")
    allowed_types: List[QuestionType] = Field(
        default_factory=lambda: [QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_ANSWER],
        description="Allowed question types"
    )
    difficulty_distribution: Optional[Dict[DifficultyLevel, int]] = Field(
        None,
        description="Desired counts per difficulty, e.g. {'easy': 2, 'medium': 2, 'hard': 1}"
    )
    topics: Optional[List[str]] = Field(None, description="Specific topics/subtopics to focus on")
    target_points_per_question: Optional[float] = 1.0
    async_mode: bool = Field(False, description="Set True to queue as asynchronous Celery task")


class QuizDraftResponse(BaseModel):
    title: str = "Draft Quiz"
    description: str = "Generated draft questions based on course lesson content."
    questions: List[GeneratedQuestion]
    is_complete: bool = True
    total_points: float = 0.0
    requires_teacher_approval: bool = True
    cached: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
