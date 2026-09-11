import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.logging import logger
from app.providers.base import AIProvider, ChatMessage
from app.providers.factory import get_ai_provider
from app.schemas.reports import (
    ReportNarrativeRequest,
    ReportNarrativeResponse,
)
from app.traffic.admission import admission_controller
from app.traffic.cache import request_cache


class _InternalLLMReportOutput(BaseModel):
    executive_summary: str
    module_performance_narrative: str
    retention_and_risk_narrative: str
    pedagogical_interventions_narrative: str


class ReportNarrativeService:
    """
    Course Report Narrative Generation Service:
    - Generates narrative prose for academic course evaluation reports.
    - Synthesizes course module structure, grade trends, and retention risk patterns into polished prose.
    - Focuses strictly on narrative generation; PDF/spreadsheet rendering is left to the LMS platform.
    """

    PROMPT_VERSION = "v1"

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        return self._provider or get_ai_provider()

    def _build_prompt(self, request: ReportNarrativeRequest) -> List[ChatMessage]:
        module_text = "\n".join([
            f"- Module '{m.module_title}': Completion {int(m.completion_rate * 100)}%, Avg Score {m.average_quiz_score:.1f}%"
            + (f" [Flagged Topics: {', '.join(m.flagged_hard_topics)}]" if m.flagged_hard_topics else "")
            for m in request.modules
        ])

        system_instruction = (
            f"You are an academic report author writing a formal course narrative report for {request.target_audience}.\n"
            "Your output is the prose/narrative sections of the report.\n"
            "CRITICAL RULES:\n"
            "1. Write clear, analytical, and professional prose (no raw tables or code).\n"
            "2. Provide deep context: connect student engagement and module difficulty with retention trends.\n"
            "3. Formulate concrete, institutional recommendations."
        )

        user_content = (
            f"Course Title: {request.course_title} ({request.term})\n"
            f"Target Audience: {request.target_audience}\n"
            f"Total Enrolled: {request.total_enrolled} | Overall Completion Rate: {int(request.completion_rate_overall * 100)}%\n"
            f"Students Identified as At-Risk: {request.at_risk_students_count} ({int((request.at_risk_students_count / request.total_enrolled) * 100)}% of cohort)\n\n"
            f"Module Performance Overview:\n{module_text if module_text else 'No module-level breakdowns provided.'}\n\n"
            f"TA Analytics Notes:\n{request.ta_analytics_notes or 'None'}\n\n"
            f"Focus Areas: {', '.join(request.focus_areas) if request.focus_areas else 'General course health'}\n\n"
            "Please write the narrative sections for this report."
        )

        return [
            ChatMessage(role="system", content=system_instruction),
            ChatMessage(role="user", content=user_content),
        ]

    async def generate_report_narrative(
        self,
        request: ReportNarrativeRequest,
        bypass_cache: bool = False
    ) -> ReportNarrativeResponse:
        cache_key = request_cache.generate_key("reports", request.model_dump(), self.PROMPT_VERSION)

        cached_data = await request_cache.get(cache_key, bypass_cache=bypass_cache)
        if cached_data:
            response = ReportNarrativeResponse.model_validate(cached_data)
            response.cached = True
            return response

        async with admission_controller.acquire_slot():
            messages = self._build_prompt(request)

            llm_result: _InternalLLMReportOutput = await self.provider.generate_structured(
                messages=messages,
                schema=_InternalLLMReportOutput,
                temperature=0.3
            )

            full_markdown = (
                f"# Academic Evaluation Report: {request.course_title}\n"
                f"**Audience:** {request.target_audience.title()} | **Term:** {request.term}\n\n"
                f"## 1. Executive Summary\n{llm_result.executive_summary}\n\n"
                f"## 2. Module Performance & Curriculum Mastery\n{llm_result.module_performance_narrative}\n\n"
                f"## 3. Student Retention & Academic Risk Analysis\n{llm_result.retention_and_risk_narrative}\n\n"
                f"## 4. Strategic Interventions & Recommendations\n{llm_result.pedagogical_interventions_narrative}\n"
            )

            response = ReportNarrativeResponse(
                course_title=request.course_title,
                executive_summary=llm_result.executive_summary,
                module_performance_narrative=llm_result.module_performance_narrative,
                retention_and_risk_narrative=llm_result.retention_and_risk_narrative,
                pedagogical_interventions_narrative=llm_result.pedagogical_interventions_narrative,
                full_markdown_report=full_markdown,
                cached=False
            )

            await request_cache.set(cache_key, "reports", response.model_dump())
            return response


report_service = ReportNarrativeService()
