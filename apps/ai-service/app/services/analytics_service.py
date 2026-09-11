import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.logging import logger
from app.providers.base import AIProvider, ChatMessage
from app.providers.factory import get_ai_provider
from app.schemas.analytics import (
    AggregatedClassStatsRequest,
    AnalyticsInterpretationResponse,
)
from app.traffic.admission import admission_controller
from app.traffic.cache import request_cache


class _InternalLLMAnalyticsOutput(BaseModel):
    key_findings: List[str]
    likely_root_causes: List[str]
    actionable_recommendations: List[str]
    ta_summary: str


class AnalyticsService:
    """
    Class Analytics Interpretation Service:
    - Analyzes aggregate assessment metrics into sharp, pedagogical TA insights.
    - Pinpoints statistical anomalies, diagnoses misconceptions, and recommends interventions.
    - Never ingests raw student submissions or PII.
    """

    PROMPT_VERSION = "v1"

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        return self._provider or get_ai_provider()

    def _build_prompt(self, request: AggregatedClassStatsRequest) -> List[ChatMessage]:
        q_stats_summary = "\n".join([
            f"- Q[{q.question_id}] Topic '{q.topic}': Pass Rate {int(q.pass_rate * 100)}%, Avg Ratio {q.average_score_ratio:.2f}"
            + (f", Discrimination Index {q.discrimination_index:.2f}" if q.discrimination_index is not None else "")
            for q in request.question_stats
        ])

        system_instruction = (
            "You are an experienced, thoughtful academic Teaching Assistant (TA) analyzing aggregated class exam results.\n"
            "Your role is to diagnose underlying student misconceptions and provide actionable teaching advice.\n"
            "CRITICAL RULES:\n"
            "1. DO NOT simply restate the numerical statistics (e.g. avoid 'the average score was 74%').\n"
            "2. Identify specific bottlenecks: what went wrong, which conceptual topics failed, and why.\n"
            "3. Propose realistic, high-impact instructional adjustments for the professor to implement in next class."
        )

        user_content = (
            f"Course: {request.course_name}\n"
            f"Assessment: {request.assessment_name}\n"
            f"Total Students: {request.total_students} | Completion Rate: {int(request.completion_rate * 100)}%\n"
            f"Class Average: {request.average_score:.1f}% | Median: {request.median_score:.1f}% | Std Dev: {request.score_std_dev:.1f}\n\n"
            f"Question & Topic Breakdown:\n{q_stats_summary if q_stats_summary else 'No granular question stats provided.'}\n\n"
            f"Common Distractor Themes Observed: {', '.join(request.common_distractor_themes) if request.common_distractor_themes else 'None recorded.'}\n\n"
            "Please provide your TA diagnostic interpretation."
        )

        return [
            ChatMessage(role="system", content=system_instruction),
            ChatMessage(role="user", content=user_content),
        ]

    async def interpret_statistics(
        self,
        request: AggregatedClassStatsRequest,
        bypass_cache: bool = False
    ) -> AnalyticsInterpretationResponse:
        cache_key = request_cache.generate_key("analytics", request.model_dump(), self.PROMPT_VERSION)

        cached_data = await request_cache.get(cache_key, bypass_cache=bypass_cache)
        if cached_data:
            response = AnalyticsInterpretationResponse.model_validate(cached_data)
            response.cached = True
            return response

        async with admission_controller.acquire_slot():
            messages = self._build_prompt(request)
            
            llm_result: _InternalLLMAnalyticsOutput = await self.provider.generate_structured(
                messages=messages,
                schema=_InternalLLMAnalyticsOutput,
                temperature=0.3
            )

            response = AnalyticsInterpretationResponse(
                key_findings=llm_result.key_findings,
                likely_root_causes=llm_result.likely_root_causes,
                actionable_recommendations=llm_result.actionable_recommendations,
                ta_summary=llm_result.ta_summary,
                cached=False
            )

            await request_cache.set(cache_key, "analytics", response.model_dump())
            return response


analytics_service = AnalyticsService()
