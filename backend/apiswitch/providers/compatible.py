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

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        raise ProviderError("Compatible provider chat is not implemented yet", "not_implemented")

    async def list_models(self) -> list[dict[str, Any]]:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.get(f"{self.base_url}/models", headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Failed to discover compatible provider models: {exc}") from exc

        data = payload.get("data", payload if isinstance(payload, list) else [])
        if not isinstance(data, list):
            raise ProviderError("Compatible provider /models response is not a list")
        return [item for item in data if isinstance(item, dict)]
