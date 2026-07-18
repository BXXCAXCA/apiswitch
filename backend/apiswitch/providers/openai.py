from collections.abc import AsyncIterator
from typing import Any

import httpx

from apiswitch.providers.base import AudioBinaryResponse, ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import (
    AudioSpeechRequest,
    AudioTranscriptionRequest,
    ChatCompletionRequest,
    EmbeddingsRequest,
    ImageGenerationRequest,
    ImageEditRequest,
    ImageVariationRequest,
    ModerationRequest,
    MusicGenerationRequest,
    VideoGenerationRequest,
)


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
        self.record_response_headers(response.headers)
        return response.json()

    async def embeddings(self, request: EmbeddingsRequest) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers(),
                    json=request.model_dump(exclude_none=True),
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI embeddings request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI embeddings request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def image_generations(self, request: ImageGenerationRequest) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=self._headers(),
                    json=request.model_dump(exclude_none=True),
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI image generation request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI image generation failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def image_edits(self, request: ImageEditRequest) -> dict[str, Any]:
        return await self._image_multipart("edits", request)

    async def image_variations(self, request: ImageVariationRequest) -> dict[str, Any]:
        return await self._image_multipart("variations", request)

    async def _image_multipart(
        self, operation: str, request: ImageEditRequest | ImageVariationRequest
    ) -> dict[str, Any]:
        fields = request.model_dump(
            exclude={"image_bytes", "filename", "content_type", "mask_bytes", "mask_filename", "mask_content_type"},
            exclude_none=True,
        )
        files: dict[str, tuple[str, bytes, str]] = {
            "image": (request.filename, request.image_bytes, request.content_type or "application/octet-stream")
        }
        if isinstance(request, ImageEditRequest) and request.mask_bytes is not None:
            files["mask"] = (
                request.mask_filename or "mask",
                request.mask_bytes,
                request.mask_content_type or "application/octet-stream",
            )
        headers = self._headers()
        headers.pop("Content-Type", None)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/images/{operation}", headers=headers, data=fields, files=files
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI image {operation} request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI image {operation} failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def video_generations(self, request: VideoGenerationRequest) -> dict[str, Any]:
        return await self._json_post("/videos", request.model_dump(exclude_none=True), "video generation")

    async def music_generations(self, request: MusicGenerationRequest) -> dict[str, Any]:
        return await self._json_post("/music/generations", request.model_dump(exclude_none=True), "music generation")

    async def _json_post(self, path: str, payload: dict[str, Any], label: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}{path}", headers=self._headers(), json=payload)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI {label} request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI {label} failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def audio_speech(self, request: AudioSpeechRequest) -> AudioBinaryResponse:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/audio/speech",
                    headers=self._headers(),
                    json=request.model_dump(exclude_none=True),
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI speech request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI speech request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return AudioBinaryResponse(
            body=response.content,
            media_type=response.headers.get("content-type", "audio/mpeg").split(";", 1)[0],
        )

    async def audio_transcriptions(self, request: AudioTranscriptionRequest) -> dict[str, Any] | str:
        fields = request.model_dump(exclude={"file_bytes", "filename", "content_type"}, exclude_none=True)
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self._headers()['Authorization'].removeprefix('Bearer ')}"},
                    data=fields,
                    files={"file": (request.filename, request.file_bytes, request.content_type or "application/octet-stream")},
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI transcription request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI transcription request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        if "json" in response.headers.get("content-type", ""):
            return response.json()
        return response.text

    async def moderations(self, request: ModerationRequest) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/moderations",
                    headers=self._headers(),
                    json=request.model_dump(exclude_none=True),
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"OpenAI moderation request failed: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderError(
                f"OpenAI moderation failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
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
