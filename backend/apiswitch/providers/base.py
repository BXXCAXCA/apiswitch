from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from apiswitch.schemas.gateway import AnthropicMessagesRequest, ChatCompletionRequest


class ProviderError(Exception):
    def __init__(self, message: str, error_type: str = "provider_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class ProviderAdapter(ABC):
    name: str
    provider_type: str

    @abstractmethod
    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        raise NotImplementedError

    async def messages(self, request: AnthropicMessagesRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Anthropic Messages is not supported by provider type: {self.provider_type}",
            "messages_not_supported",
        )

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        raise ProviderError(
            f"Streaming is not supported by provider type: {self.provider_type}",
            "streaming_not_supported",
        )
        yield b""

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        raise NotImplementedError
