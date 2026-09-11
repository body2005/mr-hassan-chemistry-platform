import pytest
from app.providers.mock_provider import MockProvider
from app.schemas.analytics import AggregatedClassStatsRequest, QuestionStatistic
from app.schemas.reports import ModulePerformanceSummary, ReportNarrativeRequest
from app.services.analytics_service import AnalyticsService
from app.services.report_service import ReportNarrativeService


@pytest.mark.asyncio
async def test_analytics_service():
    mock_provider = MockProvider()
    mock_provider.set_mock_structured_data({
        "key_findings": ["Students struggled with pointer arithmetic on Q3."],
        "likely_root_causes": ["Confusion between value dereferencing and address offsetting."],
        "actionable_recommendations": ["Conduct a visual memory-layout walkthrough in next lecture."],
        "ta_summary": "Overall good performance, but pointer arithmetic remains a significant stumbling block."
    })

    service = AnalyticsService(provider=mock_provider)
    req = AggregatedClassStatsRequest(
        course_name="CS50",
        assessment_name="Midterm Exam",
        total_students=120,
        completion_rate=0.95,
        average_score=72.4,
        median_score=75.0,
        score_std_dev=14.2,
        question_stats=[
            QuestionStatistic(question_id="q3", topic="Pointers", pass_rate=0.42, average_score_ratio=0.45)
        ]
    )

    resp = await service.interpret_statistics(req)
    assert len(resp.key_findings) == 1
    assert "pointer" in resp.key_findings[0].lower()
    assert len(resp.actionable_recommendations) == 1
    assert resp.cached is False


@pytest.mark.asyncio
async def test_report_narrative_service():
    mock_provider = MockProvider()
    mock_provider.set_mock_structured_data({
        "executive_summary": "The Fall term demonstrated strong overall student retention of 91%.",
        "module_performance_narrative": "Module 1 and 2 showed 85%+ mastery.",
        "retention_and_risk_narrative": "8 students flagged for potential drop-off.",
        "pedagogical_interventions_narrative": "Targeted TA office hours are recommended for Module 3."
    })

    service = ReportNarrativeService(provider=mock_provider)
    req = ReportNarrativeRequest(
        course_title="Introduction to Data Science",
        target_audience="department_head",
        total_enrolled=80,
        completion_rate_overall=0.91,
        at_risk_students_count=8,
        modules=[
            ModulePerformanceSummary(module_title="Python Basics", completion_rate=0.95, average_quiz_score=88.0)
        ]
    )

    resp = await service.generate_report_narrative(req)
    assert "Fall term" in resp.executive_summary
    assert "# Academic Evaluation Report" in resp.full_markdown_report
    assert resp.cached is False
