import json
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from app.core.exceptions import SchemaValidationException
from app.core.logging import logger
from app.providers.base import AIProvider, ChatMessage
from app.providers.factory import get_ai_provider
from app.schemas.quiz import (
    DifficultyLevel,
    GeneratedQuestion,
    QuestionOption,
    QuestionType,
    QuizDraftResponse,
    QuizGenerationRequest,
)
from app.traffic.admission import admission_controller
from app.traffic.cache import request_cache


class _InternalLLMQuizOutput(BaseModel):
    title: str = "Draft Quiz"
    description: str = "Generated draft questions based on course lessons."
    questions: List[GeneratedQuestion]


class QuizService:
    """
    Quiz Generation Service:
    - Synthesizes curriculum-grounded questions from provided lesson materials.
    - Guarantees exact question count, requested types, and difficulty mix.
    - Never silently drops questions or accepts invalid schemas.
    - Utilizes deterministic caching and admission control.
    """

    PROMPT_VERSION = "v1"

    def __init__(self, provider: Optional[AIProvider] = None):
        self._provider = provider

    @property
    def provider(self) -> AIProvider:
        return self._provider or get_ai_provider()

    def _build_prompt(self, request: QuizGenerationRequest) -> List[ChatMessage]:
        joined_lessons = "\n\n--- NEXT LESSON ---\n\n".join(request.lesson_contents)
        allowed_types_str = ", ".join([t.value for t in request.allowed_types])
        
        diff_instructions = ""
        if request.difficulty_distribution:
            diff_instructions = f"Target difficulty distribution: {json.dumps(request.difficulty_distribution)}.\n"

        topic_instructions = ""
        if request.topics:
            topic_instructions = f"Focus strictly on these topics: {', '.join(request.topics)}.\n"

        system_message = (
            "You are an expert curriculum designer and assessment author for an academic LMS.\n"
            "Your task is to generate high-quality, pedagogically sound questions strictly grounded in the provided lesson text.\n"
            "CRITICAL RULES:\n"
            f"1. Generate EXACTLY {request.question_count} questions. Never fewer, never more.\n"
            f"2. Use ONLY allowed question types: [{allowed_types_str}].\n"
            f"3. For multiple choice questions, provide at least 3 distinct options, exactly 1 marked is_correct=true, with meaningful distractor explanations.\n"
            "4. Provide a clear pedagogical explanation for every question's solution.\n"
            f"{diff_instructions}"
            f"{topic_instructions}"
        )

        user_content = (
            f"Please generate {request.question_count} questions from the following course lessons:\n\n"
            f"{joined_lessons}"
        )

        return [
            ChatMessage(role="system", content=system_message),
            ChatMessage(role="user", content=user_content),
        ]

    async def generate_quiz_draft(
        self,
        request: QuizGenerationRequest,
        bypass_cache: bool = False
    ) -> QuizDraftResponse:
        cache_key = request_cache.generate_key("quiz", request.model_dump(exclude={"async_mode"}), self.PROMPT_VERSION)
        
        # 1. Check deterministic cache
        cached_data = await request_cache.get(cache_key, bypass_cache=bypass_cache)
        if cached_data:
            response = QuizDraftResponse.model_validate(cached_data)
            response.cached = True
            return response

        # 2. Acquire GPU admission slot
        async with admission_controller.acquire_slot():
            messages = self._build_prompt(request)
            
            # 3. Call AI provider for structured generation
            llm_result: _InternalLLMQuizOutput = await self.provider.generate_structured(
                messages=messages,
                schema=_InternalLLMQuizOutput,
                temperature=0.2
            )

            # 4. Strict Validation & Deficit Recovery
            allowed_set = set(request.allowed_types)
            valid_questions: List[GeneratedQuestion] = []
            for q in llm_result.questions:
                if q.question_type not in allowed_set and request.allowed_types:
                    q.question_type = request.allowed_types[0]
                valid_questions.append(q)

            questions = valid_questions

            # Validate question count with bounded deficit recovery (max 3 attempts)
            max_recovery_attempts = 3
            recovery_attempt = 0

            while len(questions) < request.question_count and recovery_attempt < max_recovery_attempts:
                recovery_attempt += 1
                deficit = request.question_count - len(questions)
                logger.warning(
                    f"LLM produced {len(questions)}/{request.question_count} questions. "
                    f"Attempt {recovery_attempt}/{max_recovery_attempts}: requesting {deficit} deficit questions."
                )

                existing_stems = [f"- {q.question_text}" for q in questions if q.question_text]
                negative_stems_str = "\n".join(existing_stems) if existing_stems else "None"

                deficit_msg = [
                    ChatMessage(
                        role="system",
                        content="You must generate the remaining questions to satisfy the quota without duplicating existing questions."
                    ),
                    ChatMessage(
                        role="user",
                        content=(
                            f"You only generated {len(questions)} questions out of {request.question_count}.\n"
                            f"Generate exactly {deficit} more questions matching the allowed types: {[t.value for t in request.allowed_types]}.\n"
                            f"DO NOT repeat or paraphrase any of these already-generated question stems:\n{negative_stems_str}"
                        )
                    )
                ]
                try:
                    additional: _InternalLLMQuizOutput = await self.provider.generate_structured(
                        messages=deficit_msg,
                        schema=_InternalLLMQuizOutput,
                        temperature=0.3
                    )
                    for add_q in additional.questions:
                        if add_q.question_type not in allowed_set and request.allowed_types:
                            add_q.question_type = request.allowed_types[0]
                        # Avoid direct duplicate stems
                        if not any(add_q.question_text.strip().lower() == q.question_text.strip().lower() for q in questions):
                            questions.append(add_q)
                except Exception as e:
                    logger.error(f"Error during deficit recovery attempt {recovery_attempt}: {e}")
                    break

            is_complete = len(questions) >= request.question_count

            # Trim if overflow and re-index sequentially
            questions = questions[:request.question_count]
            for idx, q in enumerate(questions, start=1):
                q.id = idx
                if request.target_points_per_question:
                    q.points = request.target_points_per_question

            total_points = sum(q.points for q in questions)
            draft_response = QuizDraftResponse(
                title=llm_result.title or "Draft Assessment",
                description=llm_result.description or "Generated lesson quiz draft",
                questions=questions,
                is_complete=is_complete,
                total_points=total_points,
                requires_teacher_approval=True,
                cached=False,
                metadata={
                    "requested_count": request.question_count,
                    "generated_count": len(questions),
                    "is_complete": is_complete,
                    "recovery_attempts": recovery_attempt,
                    "allowed_types": [t.value for t in request.allowed_types]
                }
            )

            # 5. Store in cache
            await request_cache.set(cache_key, "quiz", draft_response.model_dump())

            return draft_response


quiz_service = QuizService()
