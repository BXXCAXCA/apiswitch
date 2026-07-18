from typing import Any

from apiswitch.providers.anthropic import AnthropicProviderAdapter
from apiswitch.providers.base import ProviderError


DEFAULT_SENSENOVA_MODELS: list[dict[str, Any]] = [
    {
        "id": "deepseek-v4-flash",
        "owned_by": "sensenova",
        "capabilities": ["text", "tools"],
    }
]


class SenseNovaProviderAdapter(AnthropicProviderAdapter):
    """SenseNova's Anthropic Messages-compatible endpoint.

    It shares the request and streaming event format with Anthropic, but uses a
    standard Bearer token instead of Anthropic's ``x-api-key`` headers.
    """

    name = "sensenova"
    provider_type = "sensenova"

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("Missing SenseNova API key", "missing_api_key")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

    async def list_models(self) -> list[dict[str, Any]]:
        # The token endpoint tested for this integration does not expose a
        # model-list API, so provide the confirmed compatible model locally.
        return DEFAULT_SENSENOVA_MODELS
