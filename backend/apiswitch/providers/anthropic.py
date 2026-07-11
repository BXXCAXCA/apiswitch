from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import AnthropicMessagesRequest, ChatCompletionRequest


DEFAULT_ANTHROPIC_MODELS = [
    {"id": "claude-3-5-sonnet-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
    {"id": "claude-3-5-haiku-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
    {"id": "claude-3-opus-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
]


class AnthropicProviderAdapter(ProviderAdapter):
    name = "anthropic"
    provider_type = "anthropic"

    def __init__(self, base_url: str, api_key: str | None, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("Missing Anthropic API key", "missing_api_key")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        raise ProviderError("Use messages for Anthropic provider", "unsupported_protocol")

    async def messages(self, request: AnthropicMessagesRequest) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        if payload.get("stream"):
            raise ProviderError("Anthropic streaming is not implemented yet", "streaming_not_implemented")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Anthropic messages request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Anthropic messages request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def list_models(self) -> list[dict[str, Any]]:
        return DEFAULT_ANTHROPIC_MODELS
