from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.platform import AIInvocation
from app.models.user import User
from app.schemas import AIInvocationRequest


class AIProviderError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _ollama_generate(prompt: str, model: str, timeout: float | None = None) -> dict | list:
    settings = get_settings()
    _timeout = min(float(timeout if timeout is not None else os.getenv("OLLAMA_TIMEOUT", "3.0")), 5.0)
    body = json.dumps(
        {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    ).encode()
    request = urllib.request.Request(
        f"{settings.ollama_base_url.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AIProviderError(
            "provider_unavailable", "Configured AI provider is unavailable"
        ) from exc
    raw_response = payload.get("response")
    if not isinstance(raw_response, str):
        raise AIProviderError(
            "malformed_provider_response", "AI provider returned no structured response"
        )
    try:
        structured = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise AIProviderError("malformed_structured_output", "AI output is not valid JSON") from exc
    if not isinstance(structured, (dict, list)):
        raise AIProviderError("invalid_structured_output", "AI output must be an object or array")
    return structured


PROVIDERS: dict[str, Callable[[str, str, float], dict | list]] = {"ollama": _ollama_generate}


def invoke(db: Session, user: User, payload: AIInvocationRequest) -> AIInvocation:
    settings = get_settings()
    model = payload.model or settings.ollama_model
    provider = PROVIDERS.get(payload.provider)
    invocation = AIInvocation(
        institution_id=user.institution_id,
        actor_id=user.id,
        task=payload.task,
        provider=payload.provider,
        model=model,
        prompt_version=payload.prompt_version,
        status="running",
    )
    db.add(invocation)
    db.flush()
    started = time.perf_counter()
    if provider is None:
        invocation.status = "failed"
        invocation.error_code = "unsupported_provider"
        invocation.latency_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        raise AIProviderError("unsupported_provider", "Requested AI provider is not configured")
    try:
        output = provider(payload.prompt, model, 20.0)
    except AIProviderError as exc:
        invocation.status = "failed"
        invocation.error_code = exc.code
        invocation.latency_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        raise
    invocation.status = "succeeded"
    invocation.output_json = output
    invocation.latency_ms = int((time.perf_counter() - started) * 1000)
    db.commit()
    db.refresh(invocation)
    return invocation


def approve(db: Session, user: User, invocation_id: uuid.UUID) -> AIInvocation:
    invocation = db.get(AIInvocation, invocation_id)
    if invocation is None or invocation.institution_id != user.institution_id:
        raise LookupError("AI invocation not found")
    invocation.approved_by = user.id
    db.commit()
    db.refresh(invocation)
    return invocation
