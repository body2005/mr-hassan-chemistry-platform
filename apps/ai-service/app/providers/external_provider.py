import json
import time
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from app.config import get_settings
from app.core.exceptions import ModelInferenceException, ProviderUnavailableException, SchemaValidationException
from app.core.logging import logger
from app.core.telemetry import telemetry
from app.providers.base import AIProvider, ChatMessage, ChatResponse, EmbeddingResponse, ProviderHealth, T
from app.providers.utils import parse_and_validate


class ExternalAPIProvider(AIProvider):
    """
    External API Provider (OpenAI / OpenAI-Compatible endpoints):
    - Connects to external cloud model providers (OpenAI, Gemini via proxy, Anthropic via proxy, Groq, LiteLLM).
    - Supports JSON object mode and schema validation.
    - Tracks prompt and completion tokens accurately for cost accounting.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.EXTERNAL_BASE_URL.rstrip("/")
        self.api_key = self.settings.EXTERNAL_API_KEY
        self.default_model = self.settings.EXTERNAL_MODEL
        self.embed_model = self.settings.EXTERNAL_EMBED_MODEL
        self.timeout = httpx.Timeout(self.settings.EXTERNAL_REQUEST_TIMEOUT, connect=5.0)

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, headers=self._get_headers(), timeout=self.timeout)

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        model: Optional[str] = None
    ) -> ChatResponse:
        target_model = model or self.default_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": [msg.model_dump() for msg in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        start_time = time.perf_counter()
        try:
            async with await self._get_client() as client:
                resp = await client.post("/chat/completions", json=payload)
                if resp.status_code != 200:
                    raise ModelInferenceException(
                        message=f"External API returned HTTP {resp.status_code}: {resp.text}",
                        details={"status_code": resp.status_code, "response": resp.text}
                    )
                data = resp.json()
        except httpx.ConnectError as ce:
            logger.error(f"Failed connecting to external provider at {self.base_url}: {ce}")
            raise ProviderUnavailableException("external_api", f"Connection error: {ce}")
        except httpx.TimeoutException:
            logger.error(f"External API timed out after {self.settings.EXTERNAL_REQUEST_TIMEOUT}s")
            raise ProviderUnavailableException("external_api", "Inference request timed out.")
        except Exception as e:
            if isinstance(e, (ProviderUnavailableException, ModelInferenceException)):
                raise
            logger.error(f"Unexpected external API error: {e}", exc_info=True)
            raise ModelInferenceException(f"External provider failure: {str(e)}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)

        # Record external token consumption
        telemetry.record_tokens("external_api", prompt_tokens, completion_tokens)

        choices = data.get("choices", [])
        content = choices[0]["message"]["content"] if choices else ""
        finish_reason = choices[0].get("finish_reason", "stop") if choices else "stop"

        return ChatResponse(
            content=content,
            model=target_model,
            finish_reason=finish_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms
        )

    async def generate_structured(
        self,
        messages: List[ChatMessage],
        schema: Type[T],
        temperature: float = 0.2,
        max_retries: int = 2,
        model: Optional[str] = None
    ) -> T:
        target_model = model or self.default_model
        schema_json_str = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You MUST respond ONLY with a valid JSON object conforming to this JSON Schema:\n"
            f"{schema_json_str}\n"
            "Do not output markdown fences or explanatory text outside the JSON."
        )

        augmented_messages = [ChatMessage(role="system", content=system_instruction)] + [
            m for m in messages if m.role != "system"
        ]
        existing_sys = [m.content for m in messages if m.role == "system"]
        if existing_sys:
            augmented_messages[0].content = f"{existing_sys[0]}\n\n{system_instruction}"

        current_messages = list(augmented_messages)
        last_error: Optional[Exception] = None

        for attempt in range(max_retries + 1):
            chat_res = await self.generate_chat(
                messages=current_messages,
                temperature=temperature,
                json_mode=True,
                model=target_model
            )
            try:
                parsed = parse_and_validate(chat_res.content, schema)
                return parsed
            except SchemaValidationException as sve:
                last_error = sve
                logger.warning(f"External API structured attempt {attempt + 1}/{max_retries + 1} failed schema validation.")
                if attempt < max_retries:
                    current_messages.append(ChatMessage(role="assistant", content=chat_res.content))
                    current_messages.append(ChatMessage(
                        role="user",
                        content=f"Fix JSON schema errors:\n{json.dumps(sve.details)}\nOutput valid JSON only."
                    ))

        raise last_error or SchemaValidationException("Failed to generate valid structured data after retries.")

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> EmbeddingResponse:
        target_model = model or self.embed_model
        try:
            async with await self._get_client() as client:
                resp = await client.post("/embeddings", json={
                    "model": target_model,
                    "input": texts
                })
                if resp.status_code != 200:
                    raise ModelInferenceException(f"External embeddings error: {resp.text}")
                data = resp.json()
        except (httpx.ConnectError, httpx.TimeoutException) as err:
            raise ProviderUnavailableException("external_api", f"Embeddings endpoint unreachable: {err}")

        embeddings = [item["embedding"] for item in data.get("data", [])]
        total_tokens = data.get("usage", {}).get("total_tokens", 0)

        return EmbeddingResponse(
            embeddings=embeddings,
            model=target_model,
            total_tokens=total_tokens
        )

    async def health_check(self) -> ProviderHealth:
        if not self.api_key:
            return ProviderHealth(
                is_healthy=False,
                provider_name="external_api",
                error_message="EXTERNAL_API_KEY is not configured"
            )
        try:
            async with await self._get_client() as client:
                resp = await client.get("/models")
                if resp.status_code == 200:
                    models = [m.get("id", "") for m in resp.json().get("data", [])]
                    return ProviderHealth(
                        is_healthy=True,
                        provider_name="external_api",
                        available_models=models[:10]
                    )
                return ProviderHealth(
                    is_healthy=False,
                    provider_name="external_api",
                    error_message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            return ProviderHealth(
                is_healthy=False,
                provider_name="external_api",
                error_message=str(e)
            )
