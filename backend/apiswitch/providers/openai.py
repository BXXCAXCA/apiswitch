from collections.abc import AsyncIterator
from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import ChatCompletionRequest


class OpenAIProviderAdapter(ProviderAdapter):
    name = "openai"
    provider_type = "openai"

    def __init__(self, base_url: str, api_key: str | None, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("Missing OpenAI API key", "missing_api_key")
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        if payload.get("stream"):
            raise ProviderError("Use stream_chat for streaming requests", "invalid_stream_path")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI chat request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI chat request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        return response.json()

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        payload = request.model_dump(exclude_none=True)
        payload["stream"] = True
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout_seconds,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderError(
                            f"OpenAI stream request failed with status {response.status_code}: {body.decode('utf-8', errors='ignore')}",
                            "upstream_http_error",
                        )
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI stream request failed: {exc}") from exc

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI model discovery failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI model discovery failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise ProviderError("OpenAI /models response data is not a list", "invalid_upstream_response")
        return [item for item in data if isinstance(item, dict)]
