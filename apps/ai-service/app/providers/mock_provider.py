import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar, get_args, get_origin
import numpy as np
from app.core.telemetry import telemetry
from app.providers.base import AIProvider, ChatMessage, ChatResponse, EmbeddingResponse, ProviderHealth, T

T = TypeVar("T")


class MockProvider(AIProvider):
    """
    Mock AI Provider:
    - Provides deterministic, fast responses for testing and offline environments.
    - Accurately generates structured Pydantic model instances or custom response mocks.
    """

    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self.mock_chat_responses: List[str] = []
        self._custom_structured_data: Optional[Dict[str, Any]] = None

    def set_mock_chat_response(self, text: str):
        self.mock_chat_responses.append(text)

    def set_mock_structured_data(self, data: Dict[str, Any]):
        self._custom_structured_data = data

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        model: Optional[str] = None
    ) -> ChatResponse:
        start_time = time.perf_counter()
        
        if self.mock_chat_responses:
            content = self.mock_chat_responses.pop(0)
        else:
            last_msg = messages[-1].content if messages else ""
            if json_mode:
                content = json.dumps({"status": "mock_success", "received": last_msg})
            else:
                content = f"Mock response grounded in context for: {last_msg[:50]}"

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        prompt_tokens = sum(len(m.content.split()) for m in messages)
        completion_tokens = len(content.split())

        telemetry.record_tokens("mock", prompt_tokens, completion_tokens)

        return ChatResponse(
            content=content,
            model=model or "mock-model",
            finish_reason="stop",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )

    def _synthesize_mock_data(self, schema: Type[Any]) -> Any:
        # Check if schema has model_fields (is Pydantic model)
        if not hasattr(schema, "model_fields"):
            return None

        # Check for well-known models
        schema_name = schema.__name__
        if "_InternalLLMQuizOutput" in schema_name or "Quiz" in schema_name:
            return {
                "title": "Mock Assessment",
                "description": "Mock generated assessment",
                "questions": [
                    {
                        "id": 1,
                        "question_type": "multiple_choice",
                        "difficulty": "medium",
                        "topic": "General",
                        "points": 1.0,
                        "question_text": "Sample mock question 1?",
                        "options": [
                            {"key": "A", "text": "Option A (Correct)", "is_correct": True},
                            {"key": "B", "text": "Option B", "is_correct": False, "distractor_explanation": "Incorrect distractor"}
                        ],
                        "correct_answer": "A",
                        "explanation": "Option A is correct."
                    },
                    {
                        "id": 2,
                        "question_type": "short_answer",
                        "difficulty": "hard",
                        "topic": "General",
                        "points": 1.0,
                        "question_text": "Sample mock question 2?",
                        "correct_answer": "Sample answer",
                        "explanation": "Sample explanation."
                    }
                ]
            }

        if "_InternalLLMGradingOutput" in schema_name or "Grading" in schema_name:
            return {
                "criteria_scores": [
                    {
                        "criterion_id": "c1",
                        "criterion_name": "Accuracy",
                        "score_awarded": 8.0,
                        "max_points": 10.0,
                        "feedback": "Good understanding of the core concept."
                    }
                ],
                "feedback_summary": "Solid submission overall.",
                "confidence_score": 0.88
            }

        mock_data: Dict[str, Any] = {}
        for name, field in schema.model_fields.items():
            field_type = field.annotation
            origin = get_origin(field_type)
            args = get_args(field_type)

            if field_type == str or field_type == Optional[str]:
                mock_data[name] = f"Mock {name}"
            elif field_type == int or field_type == Optional[int]:
                mock_data[name] = 5
            elif field_type == float or field_type == Optional[float]:
                mock_data[name] = 0.85
            elif field_type == bool or field_type == Optional[bool]:
                mock_data[name] = True
            elif origin is list:
                mock_data[name] = []
            elif origin is dict:
                mock_data[name] = {}
            else:
                mock_data[name] = None

        return mock_data

    async def generate_structured(
        self,
        messages: List[ChatMessage],
        schema: Type[T],
        temperature: float = 0.2,
        max_retries: int = 2,
        model: Optional[str] = None
    ) -> T:
        if self._custom_structured_data is not None:
            data = self._custom_structured_data
            self._custom_structured_data = None
            return schema.model_validate(data)

        mock_data = self._synthesize_mock_data(schema)
        return schema.model_validate(mock_data)

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> EmbeddingResponse:
        embeddings: List[List[float]] = []
        for text in texts:
            np.random.seed(abs(hash(text)) % (2**32))
            vec = np.random.randn(self.embedding_dim)
            norm_vec = (vec / np.linalg.norm(vec)).tolist()
            embeddings.append(norm_vec)

        total_tokens = sum(len(t.split()) for t in texts)
        return EmbeddingResponse(
            embeddings=embeddings,
            model=model or "mock-embed",
            total_tokens=total_tokens
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            is_healthy=True,
            provider_name="mock",
            available_models=["mock-model", "mock-embed"]
        )
