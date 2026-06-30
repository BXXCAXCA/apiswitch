from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import ChatCompletionRequest


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
            raise ProviderError("Compatible provider streaming is not implemented yet", "streaming_not_implemented")
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
