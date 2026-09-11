from typing import Any, Optional


class AIServiceException(Exception):
    """Base exception for all AI Service domain errors."""
    def __init__(self, message: str, status_code: int = 500, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class AdmissionLimitExceededException(AIServiceException):
    """Raised when GPU inference capacity is exhausted and interactive slot cannot be acquired in time."""
    def __init__(self, message: str = "GPU inference capacity currently saturated. Please retry shortly or queue as background job.", retry_after: int = 5):
        super().__init__(message, status_code=503, details={"retry_after": retry_after})
        self.retry_after = retry_after


class RateLimitExceededException(AIServiceException):
    """Raised when client exceeds allowed request rate."""
    def __init__(self, message: str = "Rate limit exceeded. Please throttle your requests.", retry_after: int = 60):
        super().__init__(message, status_code=429, details={"retry_after": retry_after})
        self.retry_after = retry_after


class ProviderUnavailableException(AIServiceException):
    """Raised when the configured AI model provider (Ollama/External API) is unreachable or failing."""
    def __init__(self, provider: str, message: str = "AI Provider unreachable or unhealthy."):
        super().__init__(f"[{provider}] {message}", status_code=503, details={"provider": provider})


class ModelInferenceException(AIServiceException):
    """Raised when an inference call fails mid-execution or produces malformed unfixable output."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message, status_code=502, details=details)


class SchemaValidationException(AIServiceException):
    """Raised when LLM output violates required strict schema constraints after repair attempts."""
    def __init__(self, message: str, validation_errors: Optional[Any] = None):
        super().__init__(message, status_code=422, details={"validation_errors": validation_errors})


class UnsupportedGradingTypeException(AIServiceException):
    """Raised when a caller attempts to use LLM grading on objective questions (MCQ, True/False, Matching)."""
    def __init__(self, question_type: str):
        message = (
            f"Question type '{question_type}' is an objective item and must be scored directly by the LMS platform "
            "via deterministic lookup, not through this AI service."
        )
        super().__init__(message, status_code=400, details={"question_type": question_type, "allowed": "subjective_essay_only"})


class GroundingRefusalException(AIServiceException):
    """Raised/used when tutor RAG finds insufficient context to reliably answer a course query."""
    def __init__(self, message: str = "I do not have enough material in the course content to answer this accurately."):
        super().__init__(message, status_code=200, details={"is_grounded": False, "refusal": True})
