from collections.abc import AsyncIterator
from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import ChatCompletionRequest, EmbeddingsRequest


class CompatibleProviderAdapter(ProviderAdapter):
    name = "compatible"
    provider_type = "compatible"

    def __init__(self, base_url: str, api_key: str | None = None, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Compatible provider chat failed: {exc}") from exc

    async def embeddings(self, request: EmbeddingsRequest) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers(),
                    json=request.model_dump(exclude_none=True),
                )
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Compatible provider embeddings failed: {exc}") from exc

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
                            f"Compatible stream failed with status {response.status_code}: {body.decode('utf-8', errors='ignore')}",
                            "upstream_http_error",
                        )
                    async for chunk in response.aiter_bytes():
                        if chunk:
                            yield chunk
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Compatible provider stream failed: {exc}") from exc

    async def list_models(self) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers())
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Failed to discover compatible provider models: {exc}") from exc

        data = payload.get("data", payload if isinstance(payload, list) else [])
        if not isinstance(data, list):
            raise ProviderError("Compatible provider /models response is not a list")
        return [item for item in data if isinstance(item, dict)]
