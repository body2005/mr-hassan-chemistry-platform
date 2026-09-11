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


class OllamaProvider(AIProvider):
    """
    Ollama Local Serving Provider:
    - Communicates with local Ollama instance on shared 8GB GPU.
    - Uses native `format: "json"` for structured constraints.
    - Employs strict timeouts to fail fast when models hang or VRAM runs out.
    - Auto-resolves installed model tags if specific quantization tag is missing.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.OLLAMA_BASE_URL.rstrip("/")
        self.default_model = self.settings.OLLAMA_MODEL
        self.embed_model = self.settings.OLLAMA_EMBED_MODEL
        self.timeout = httpx.Timeout(self.settings.OLLAMA_REQUEST_TIMEOUT, connect=10.0, read=self.settings.OLLAMA_REQUEST_TIMEOUT)
        self._resolved_model: Optional[str] = None

    async def _get_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout)

    async def _resolve_model(self, client: httpx.AsyncClient, requested_model: Optional[str] = None) -> str:
        if requested_model:
            return requested_model
        if self._resolved_model:
            return self._resolved_model

        try:
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                available = [m.get("name", "") for m in resp.json().get("models", [])]
                if self.default_model in available:
                    self._resolved_model = self.default_model
                    return self._resolved_model
                
                # Check for prefix matches (e.g. qwen3:8b or qwen2.5)
                for m in available:
                    if "qwen" in m.lower():
                        self._resolved_model = m
                        return self._resolved_model

                if available:
                    self._resolved_model = available[0]
                    return self._resolved_model
        except Exception as e:
            logger.debug(f"Could not auto-resolve Ollama tags: {e}")

        self._resolved_model = self.default_model
        return self._resolved_model

    async def generate_chat(
        self,
        messages: List[ChatMessage],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        model: Optional[str] = None
    ) -> ChatResponse:
        start_time = time.perf_counter()
        try:
            async with await self._get_client() as client:
                target_model = await self._resolve_model(client, model)
                payload: Dict[str, Any] = {
                    "model": target_model,
                    "messages": [msg.model_dump() for msg in messages],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    }
                }
                if max_tokens:
                    payload["options"]["num_predict"] = max_tokens
                if json_mode:
                    payload["format"] = "json"

                resp = await client.post("/api/chat", json=payload)
                if resp.status_code != 200:
                    raise ModelInferenceException(
                        message=f"Ollama returned HTTP {resp.status_code}: {resp.text}",
                        details={"status_code": resp.status_code, "response": resp.text}
                    )
                data = resp.json()
        except httpx.ConnectError as ce:
            logger.error(f"Failed connecting to local Ollama at {self.base_url}: {ce}")
            raise ProviderUnavailableException("ollama", f"Connection refused at {self.base_url}. Please ensure Ollama is running (`ollama serve`).")
        except httpx.TimeoutException:
            logger.error(f"Ollama request timed out after {self.settings.OLLAMA_REQUEST_TIMEOUT}s")
            raise ProviderUnavailableException("ollama", f"Inference timed out after {self.settings.OLLAMA_REQUEST_TIMEOUT}s")
        except Exception as e:
            if isinstance(e, (ProviderUnavailableException, ModelInferenceException)):
                raise
            logger.error(f"Unexpected error in Ollama chat: {e}", exc_info=True)
            raise ModelInferenceException(f"Ollama execution error: {str(e)}")

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

        telemetry.record_tokens("ollama", prompt_tokens, completion_tokens)

        content = data.get("message", {}).get("content", "")
        return ChatResponse(
            content=content,
            model=target_model,
            finish_reason=data.get("done_reason", "stop"),
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
        schema_json_str = json.dumps(schema.model_json_schema(), indent=2)
        system_instruction = (
            f"You MUST respond ONLY with valid JSON conforming exactly to this JSON Schema:\n"
            f"{schema_json_str}\n"
            "Do not include any conversational filler, markdown explanations outside the JSON, or markdown code fences."
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
                model=model
            )
            try:
                parsed = parse_and_validate(chat_res.content, schema)
                return parsed
            except SchemaValidationException as sve:
                last_error = sve
                logger.warning(f"Ollama structured attempt {attempt + 1}/{max_retries + 1} failed schema validation: {sve.message}")
                if attempt < max_retries:
                    current_messages.append(ChatMessage(role="assistant", content=chat_res.content))
                    current_messages.append(ChatMessage(
                        role="user",
                        content=f"Your previous response had validation errors:\n{json.dumps(sve.details)}\nFix these errors and output the corrected JSON only."
                    ))

        raise last_error or SchemaValidationException("Failed to produce schema-compliant output after retries.")

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> EmbeddingResponse:
        embeddings: List[List[float]] = []

        try:
            async with await self._get_client() as client:
                target_model = await self._resolve_model(client, model or self.embed_model)
                for text in texts:
                    resp = await client.post("/api/embeddings", json={
                        "model": target_model,
                        "prompt": text
                    })
                    if resp.status_code != 200:
                        raise ModelInferenceException(f"Ollama embeddings error: {resp.text}")
                    embeddings.append(resp.json().get("embedding", []))
        except (httpx.ConnectError, httpx.TimeoutException) as err:
            raise ProviderUnavailableException("ollama", f"Embedding endpoint unavailable: {str(err)}")

        return EmbeddingResponse(
            embeddings=embeddings,
            model=target_model,
            total_tokens=sum(len(t.split()) for t in texts)
        )

    async def health_check(self) -> ProviderHealth:
        try:
            async with await self._get_client() as client:
                resp = await client.get("/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    return ProviderHealth(
                        is_healthy=True,
                        provider_name="ollama",
                        available_models=models
                    )
                return ProviderHealth(
                    is_healthy=False,
                    provider_name="ollama",
                    error_message=f"HTTP {resp.status_code}: {resp.text}"
                )
        except Exception as e:
            return ProviderHealth(
                is_healthy=False,
                provider_name="ollama",
                error_message=str(e)
            )
