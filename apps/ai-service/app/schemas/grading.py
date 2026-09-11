from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.exceptions import UnsupportedGradingTypeException

OBJECTIVE_QUESTION_TYPES = {
    "mcq",
    "multiple_choice",
    "true_false",
    "tf",
    "matching",
    "ordering",
    "fill_in_the_blank_exact"
}


class RubricCriterionInput(BaseModel):
    id: str = Field(..., description="Unique ID for this rubric criterion (e.g. 'c1', 'thesis')")
    name: str = Field(..., description="Name of criterion (e.g. 'Argumentation', 'Grammar', 'Evidence')")
    description: str = Field(..., description="Detailed expectations for this criterion")
    max_points: float = Field(..., gt=0, description="Maximum score for this criterion")


class EssayGradingRequest(BaseModel):
    question_prompt: str = Field(..., description="The prompt or question given to the student")
    student_submission: str = Field(..., min_length=1, description="The student's essay or subjective text answer")
    rubric: List[RubricCriterionInput] = Field(..., min_length=1, description="List of criteria to evaluate against")
    max_score: float = Field(..., gt=0, description="Total maximum score allowed for the submission")
    question_type: str = Field("essay", description="Type of question being graded")
    context_passage: Optional[str] = Field(None, description="Optional source text or reference material")


class CriterionGradingResult(BaseModel):
    criterion_id: str
    criterion_name: str
    score_awarded: float = Field(..., ge=0)
    max_points: float = Field(..., gt=0)
    feedback: str = Field(..., description="Constructive, criterion-specific feedback")


class EssayGradingResponse(BaseModel):
    total_score: float = Field(..., ge=0)
    max_score: float = Field(..., gt=0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    criteria_breakdown: List[CriterionGradingResult]
    feedback_summary: str = Field(..., description="Concise overall feedback with no exposed internal chain-of-thought")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence metric in the automated proposal")
    flagged_for_human_review: bool = Field(False, description="True if confidence is low (<0.75) or response has ambiguities")
    requires_teacher_approval: bool = True
    cached: bool = False
