from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel):
    role: str = Field(..., description="Role of the speaker (system, user, assistant)")
    content: str = Field(..., description="Message text content")


class ChatResponse(BaseModel):
    content: str
    model: str
    finish_reason: str = "stop"
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    total_tokens: int = 0


class ProviderHealth(BaseModel):
    is_healthy: bool
    provider_name: str
    available_models: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class AIProvider(ABC):
    """
    Abstract AI Provider Interface:
    Standard contract for local (Ollama) and cloud/external LLM engines.
    """

    @abstractmethod
    async def generate_chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        model: Optional[str] = None
    ) -> ChatResponse:
        """Generates conversational text or raw JSON string completion."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: List[ChatMessage],
        schema: Type[T],
        temperature: float = 0.2,
        max_retries: int = 2,
        model: Optional[str] = None
    ) -> T:
        """
        Generates and strictly validates response against a Pydantic schema.
        Includes automatic retry/repair if initial output fails validation.
        """
        pass

    @abstractmethod
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> EmbeddingResponse:
        """Generates normalized dense vector embeddings for input texts."""
        pass

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        """Verifies engine reachability and model availability without hanging."""
        pass
