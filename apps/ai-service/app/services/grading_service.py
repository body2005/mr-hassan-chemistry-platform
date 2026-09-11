import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.exceptions import UnsupportedGradingTypeException
from app.core.logging import logger
from app.providers.base import AIProvider, ChatMessage
from app.providers.factory import get_ai_provider
from app.schemas.grading import (
    CriterionGradingResult,
    EssayGradingRequest,
    EssayGradingResponse,
)
from app.traffic.admission import admission_controller
from app.traffic.cache import request_cache


class _InternalLLMGradingOutput(BaseModel):
    criteria_scores: List[CriterionGradingResult]
    feedback_summary: str = Field(..., description="Concise overall feedback without exposed chain-of-thought")
    confidence_score: float = Field(0.85, ge=0.0, le=1.0, description="Confidence metric in proposed evaluation")


class GradingService:
    """
    Subjective Essay & Free-Text Grading Service:
    - Evaluates submissions strictly against provided rubrics.
    - Produces per-criterion breakdowns, concise feedback, and confidence signals.
    - Exposes zero internal chain-of-thought.
    - Rejects objective question types (MCQ, True/False, etc.).
    - Gated by admission control and deterministic cache.
    """

    PROMPT_VERSION = "v1"

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        return self._provider or get_ai_provider()

    def _build_prompt(self, request: EssayGradingRequest) -> List[ChatMessage]:
        rubric_description = "\n".join([
            f"- Criterion [{c.id}] '{c.name}' (Max {c.max_points} pts): {c.description}"
            for c in request.rubric
        ])

        context_info = f"Reference Material / Context:\n{request.context_passage}\n\n" if request.context_passage else ""

        system_message = (
            "You are an impartial, highly rigorous academic teaching assistant grading a student's subjective answer.\n"
            "Evaluate the student's submission strictly and fairly according to the provided rubric criteria.\n"
            "CRITICAL RULES:\n"
            "1. Evaluate EVERY criterion listed in the rubric. Score each criterion between 0 and its specified max_points.\n"
            "2. Provide constructive, specific feedback per criterion explaining why points were awarded or deducted.\n"
            "3. Provide a concise overall feedback summary. DO NOT include scratchpad or chain-of-thought notes.\n"
            "4. Provide a confidence_score (between 0.0 and 1.0) indicating how unambiguously the submission aligns with the rubric."
        )

        user_content = (
            f"{context_info}"
            f"Question Prompt:\n{request.question_prompt}\n\n"
            f"Grading Rubric:\n{rubric_description}\n\n"
            f"Student Submission:\n{request.student_submission}\n\n"
            f"Total Maximum Score: {request.max_score} points."
        )

        return [
            ChatMessage(role="system", content=system_message),
            ChatMessage(role="user", content=user_content),
        ]

    async def grade_essay(
        self,
        request: EssayGradingRequest,
        bypass_cache: bool = False
    ) -> EssayGradingResponse:
        cache_key = request_cache.generate_key("grading", request.model_dump(), self.PROMPT_VERSION)

        # 1. Check deterministic cache
        cached_data = await request_cache.get(cache_key, bypass_cache=bypass_cache)
        if cached_data:
            response = EssayGradingResponse.model_validate(cached_data)
            response.cached = True
            return response

        # 2. Acquire GPU admission slot
        async with admission_controller.acquire_slot():
            messages = self._build_prompt(request)

            # 3. Call AI Provider
            llm_result: _InternalLLMGradingOutput = await self.provider.generate_structured(
                messages=messages,
                schema=_InternalLLMGradingOutput,
                temperature=0.1
            )

            # 4. Score normalization & validation
            rubric_map = {c.id: c for c in request.rubric}
            criteria_results: List[CriterionGradingResult] = []
            raw_total_score = 0.0
            rubric_max_total = sum(c.max_points for c in request.rubric)

            for cr in llm_result.criteria_scores:
                ref_crit = rubric_map.get(cr.criterion_id)
                max_pts = ref_crit.max_points if ref_crit else cr.max_points
                name = ref_crit.name if ref_crit else cr.criterion_name

                clamped_score = max(0.0, min(float(cr.score_awarded), float(max_pts)))
                raw_total_score += clamped_score

                criteria_results.append(CriterionGradingResult(
                    criterion_id=cr.criterion_id,
                    criterion_name=name,
                    score_awarded=round(clamped_score, 2),
                    max_points=round(max_pts, 2),
                    feedback=cr.feedback
                ))

            if rubric_max_total > 0 and rubric_max_total != request.max_score:
                scaled_total = (raw_total_score / rubric_max_total) * request.max_score
            else:
                scaled_total = min(raw_total_score, request.max_score)

            scaled_total = round(scaled_total, 2)
            percentage = round((scaled_total / request.max_score) * 100.0, 2)
            
            confidence = max(0.0, min(1.0, float(llm_result.confidence_score)))
            flagged = confidence < 0.75 or percentage < 30.0

            proposal = EssayGradingResponse(
                total_score=scaled_total,
                max_score=request.max_score,
                percentage=percentage,
                criteria_breakdown=criteria_results,
                feedback_summary=llm_result.feedback_summary,
                confidence_score=confidence,
                flagged_for_human_review=flagged,
                requires_teacher_approval=True,
                cached=False
            )

            # 5. Store in cache
            await request_cache.set(cache_key, "grading", proposal.model_dump())

            return proposal


grading_service = GradingService()
