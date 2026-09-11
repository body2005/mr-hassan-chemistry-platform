from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QuestionStatistic(BaseModel):
    question_id: str
    topic: str
    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of students who answered correctly")
    average_score_ratio: float = Field(..., ge=0.0, le=1.0)
    discrimination_index: Optional[float] = Field(None, description="Correlation between question success and overall performance")


class AggregatedClassStatsRequest(BaseModel):
    course_name: str
    assessment_name: str
    total_students: int = Field(..., ge=1)
    completion_rate: float = Field(..., ge=0.0, le=1.0)
    average_score: float = Field(..., ge=0.0, le=100.0)
    median_score: float = Field(..., ge=0.0, le=100.0)
    score_std_dev: float = Field(..., ge=0.0)
    question_stats: List[QuestionStatistic] = Field(default_factory=list)
    common_distractor_themes: Optional[List[str]] = Field(default_factory=list)


class AnalyticsInterpretationResponse(BaseModel):
    key_findings: List[str] = Field(..., description="Specific statistical anomalies and mastery patterns identified")
    likely_root_causes: List[str] = Field(..., description="Why students struggled on particular concepts or questions")
    actionable_recommendations: List[str] = Field(..., description="Targeted pedagogical remedies for the instructor to try")
    ta_summary: str = Field(..., description="Thoughtful TA-style narrative interpretation")
    cached: bool = False
