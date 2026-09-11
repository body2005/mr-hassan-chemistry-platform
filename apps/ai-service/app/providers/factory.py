from typing import Optional
from app.config import get_settings
from app.core.exceptions import ProviderUnavailableException
from app.core.logging import logger
from app.providers.base import AIProvider
from app.providers.external_provider import ExternalAPIProvider
from app.providers.mock_provider import MockProvider
from app.providers.ollama_provider import OllamaProvider

_active_provider: Optional[AIProvider] = None


def get_ai_provider(provider_type: Optional[str] = None) -> AIProvider:
    """
    Factory function to retrieve or instantiate the configured AI Provider.
    Supported types: 'ollama' | 'local' (default), 'external', 'mock'.
    
    Zero Silent Fallbacks:
    If a provider is configured, the system strictly routes all requests to that provider.
    Any engine failure or timeout produces a direct 503 error rather than silently routing
    to an alternative or external provider.
    """
    global _active_provider
    settings = get_settings()
    target = (provider_type or settings.DEFAULT_PROVIDER).lower().strip()

    if target in ["ollama", "local"]:
        return OllamaProvider()
    elif target == "external":
        return ExternalAPIProvider()
    elif target == "mock":
        if _active_provider is None or not isinstance(_active_provider, MockProvider):
            _active_provider = MockProvider()
        return _active_provider
    else:
        raise ProviderUnavailableException(
            provider=target,
            message=f"Unknown or unconfigured AI provider '{target}'. Allowed values: 'ollama', 'local', 'external', 'mock'."
        )
