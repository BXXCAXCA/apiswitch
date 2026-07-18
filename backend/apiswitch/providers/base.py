from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from apiswitch.schemas.gateway import (
    AnthropicMessagesRequest,
    AudioSpeechRequest,
    AudioTranscriptionRequest,
    ChatCompletionRequest,
    EmbeddingsRequest,
    ImageGenerationRequest,
    ImageEditRequest,
    ImageVariationRequest,
    MusicGenerationRequest,
    ModerationRequest,
    RerankRequest,
    SearchRequest,
    VideoGenerationRequest,
)


@dataclass(frozen=True)
class AudioBinaryResponse:
    body: bytes
    media_type: str


class ProviderError(Exception):
    def __init__(self, message: str, error_type: str = "provider_error") -> None:
        super().__init__(message)
        self.error_type = error_type


class ProviderAdapter(ABC):
    name: str
    provider_type: str

    def record_response_headers(self, headers: Any) -> None:
        """Expose normalized upstream rate-limit metadata to the gateway."""
        self.last_response_headers = {str(key).lower(): str(value) for key, value in headers.items()}

    @abstractmethod
    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        raise NotImplementedError

    async def messages(self, request: AnthropicMessagesRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Anthropic Messages is not supported by provider type: {self.provider_type}",
            "messages_not_supported",
        )

    async def embeddings(self, request: EmbeddingsRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Embeddings is not supported by provider type: {self.provider_type}",
            "embeddings_not_supported",
        )

    async def image_generations(self, request: ImageGenerationRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Image generation is not supported by provider type: {self.provider_type}",
            "images_not_supported",
        )

    async def image_edits(self, request: ImageEditRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Image edits are not supported by provider type: {self.provider_type}",
            "image_edits_not_supported",
        )

    async def image_variations(self, request: ImageVariationRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Image variations are not supported by provider type: {self.provider_type}",
            "image_variations_not_supported",
        )

    async def video_generations(self, request: VideoGenerationRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Video generation is not supported by provider type: {self.provider_type}",
            "video_not_supported",
        )

    async def music_generations(self, request: MusicGenerationRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Music generation is not supported by provider type: {self.provider_type}",
            "music_not_supported",
        )

    async def audio_speech(self, request: AudioSpeechRequest) -> AudioBinaryResponse:
        raise ProviderError(
            f"Speech generation is not supported by provider type: {self.provider_type}",
            "audio_speech_not_supported",
        )

    async def audio_transcriptions(self, request: AudioTranscriptionRequest) -> dict[str, Any] | str:
        raise ProviderError(
            f"Audio transcription is not supported by provider type: {self.provider_type}",
            "audio_transcription_not_supported",
        )

    async def moderations(self, request: ModerationRequest) -> dict[str, Any]:
        raise ProviderError(
            f"Moderations are not supported by provider type: {self.provider_type}",
            "moderations_not_supported",
        )

    async def rerank(self, request: RerankRequest) -> dict[str, Any]:
        raise ProviderError(f"Rerank is not supported by provider type: {self.provider_type}", "rerank_not_supported")

    async def search(self, request: SearchRequest) -> dict[str, Any]:
        raise ProviderError(f"Search is not supported by provider type: {self.provider_type}", "search_not_supported")

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        raise ProviderError(
            f"Streaming is not supported by provider type: {self.provider_type}",
            "streaming_not_supported",
        )
        yield b""

    @abstractmethod
    async def list_models(self) -> list[dict[str, Any]]:
        raise NotImplementedError
