from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ModulePerformanceSummary(BaseModel):
    module_title: str
    completion_rate: float = Field(..., ge=0.0, le=1.0)
    average_quiz_score: float = Field(..., ge=0.0, le=100.0)
    flagged_hard_topics: List[str] = Field(default_factory=list)


class ReportNarrativeRequest(BaseModel):
    course_title: str
    target_audience: str = Field("instructors", description="'instructors' | 'department_head' | 'academic_dean'")
    term: Optional[str] = "Current Term"
    total_enrolled: int = Field(..., ge=1)
    completion_rate_overall: float = Field(..., ge=0.0, le=1.0)
    at_risk_students_count: int = Field(0, ge=0)
    modules: List[ModulePerformanceSummary] = Field(default_factory=list)
    ta_analytics_notes: Optional[str] = Field(None, description="Optional qualitative TA insights from analytics engine")
    focus_areas: Optional[List[str]] = Field(default_factory=list)


class ReportNarrativeResponse(BaseModel):
    course_title: str
    executive_summary: str
    module_performance_narrative: str
    retention_and_risk_narrative: str
    pedagogical_interventions_narrative: str
    full_markdown_report: str
    cached: bool = False
