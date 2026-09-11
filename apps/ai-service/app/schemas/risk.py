from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StudentFeatures(BaseModel):
    student_id: str = Field(..., description="Student unique ID")
    cohort_id: Optional[str] = Field(None, description="Class / Section / Cohort group ID for leakage-free validation")
    course_id: Optional[str] = Field(None, description="Course ID")
    
    # Quantitative Behavioral & Academic Signals
    login_frequency_weekly: float = Field(..., ge=0, description="Average logins per week")
    assignments_submitted_ratio: float = Field(..., ge=0.0, le=1.0, description="Submitted / Total assigned")
    average_quiz_score: float = Field(..., ge=0.0, le=100.0, description="Average percentage across quizzes")
    late_submissions_count: int = Field(0, ge=0, description="Number of past-deadline submissions")
    forum_posts_count: int = Field(0, ge=0, description="Total discussion forum contributions")
    time_spent_hours_weekly: float = Field(..., ge=0, description="Hours spent in LMS weekly")
    video_watch_completion_ratio: float = Field(..., ge=0.0, le=1.0, description="Fraction of lecture videos watched")
    days_since_last_activity: int = Field(..., ge=0, description="Inactivity recency in days")


class RiskFactor(BaseModel):
    feature: str
    impact: str  # "high", "moderate", "low"
    description: str


class StudentRiskPrediction(BaseModel):
    student_id: str
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Calibrated probability of falling behind")
    risk_level: str = Field(..., description="'low' | 'moderate' | 'high' | 'critical'")
    top_risk_factors: List[RiskFactor] = Field(default_factory=list)
    confidence_interval: Dict[str, float] = Field(default_factory=dict)
    model_version: str = "v1.0-calibrated"


class BatchRiskPredictionRequest(BaseModel):
    students: List[StudentFeatures] = Field(..., min_length=1)


class BatchRiskPredictionResponse(BaseModel):
    predictions: List[StudentRiskPrediction]
    total_students: int
    at_risk_count: int
    model_metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskModelTrainRequest(BaseModel):
    training_data: List[Dict[str, Any]] = Field(..., min_length=10, description="Historical student interaction records with 'is_at_risk' label")
    model_type: Optional[str] = Field("calibrated_ensemble", description="'logistic_regression' | 'random_forest' | 'xgboost' | 'calibrated_ensemble'")
    n_splits: Optional[int] = Field(5, ge=2, le=10)


class RiskModelTrainResponse(BaseModel):
    status: str = "success"
    cv_roc_auc: float
    cv_brier_score: float
    cv_f1_score: float
    grouping_strategy_used: str  # "StratifiedGroupKFold" or "StratifiedKFold"
    sample_size: int
    model_version: str
    message: str
