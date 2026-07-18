import base64
import hashlib
import json
import math
import struct
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from apiswitch.providers.base import AudioBinaryResponse, ProviderAdapter
from apiswitch.schemas.gateway import (
    AnthropicMessagesRequest,
    AudioSpeechRequest,
    AudioTranscriptionRequest,
    ChatCompletionRequest,
    EmbeddingsRequest,
    ImageGenerationRequest,
    ImageEditRequest,
    ImageVariationRequest,
    ModerationRequest,
    MusicGenerationRequest,
    RerankRequest,
    SearchRequest,
    VideoGenerationRequest,
)
from apiswitch.services.routing_controls import estimate_token_count


class MockProviderAdapter(ProviderAdapter):
    name = "mock-main"
    provider_type = "mock"

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        return {
            "id": f"chatcmpl_mock_{uuid.uuid4().hex[:12]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request.model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Mock response from APISwitch.",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "apiswitch": {
                "provider": self.name,
                "upstream_model": "mock-chat",
                "retry_chain": [self.name],
            },
        }

    async def messages(self, request: AnthropicMessagesRequest) -> dict[str, Any]:
        return {
            "id": f"msg_mock_{uuid.uuid4().hex[:12]}",
            "type": "message",
            "role": "assistant",
            "model": request.model,
            "content": [{"type": "text", "text": "Mock response from APISwitch Messages."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }

    async def embeddings(self, request: EmbeddingsRequest) -> dict[str, Any]:
        values = request.input if isinstance(request.input, list) and all(
            isinstance(item, str) for item in request.input
        ) else [request.input]
        dimensions = request.dimensions or 8
        data = []
        for index, value in enumerate(values):
            source = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
            digest = hashlib.sha256(source).digest()
            vector = [((digest[position % len(digest)] / 255.0) * 2.0) - 1.0 for position in range(dimensions)]
            norm = math.sqrt(sum(component * component for component in vector)) or 1.0
            vector = [round(component / norm, 8) for component in vector]
            embedding: list[float] | str
            if request.encoding_format == "base64":
                binary = b"".join(struct.pack("<f", component) for component in vector)
                embedding = base64.b64encode(binary).decode("ascii")
            else:
                embedding = vector
            data.append({"object": "embedding", "index": index, "embedding": embedding})

        prompt_tokens = estimate_token_count(request.input)
        return {
            "object": "list",
            "data": data,
            "model": request.model,
            "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens},
        }

    async def image_generations(self, request: ImageGenerationRequest) -> dict[str, Any]:
        # A valid transparent 1x1 PNG keeps local protocol tests fully offline.
        transparent_png = (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4"
            "z8DwHwAFgAI/ScLIIQAAAABJRU5ErkJggg=="
        )
        count = request.n or 1
        if request.response_format == "url":
            data = [{"url": f"https://example.invalid/apiswitch/mock-image-{index}.png"} for index in range(count)]
        else:
            data = [{"b64_json": transparent_png} for _ in range(count)]
        return {"created": int(time.time()), "data": data}

    async def image_edits(self, request: ImageEditRequest) -> dict[str, Any]:
        return await self.image_generations(
            ImageGenerationRequest(model=request.model, prompt=request.prompt, n=request.n, size=request.size, response_format=request.response_format)
        )

    async def image_variations(self, request: ImageVariationRequest) -> dict[str, Any]:
        return await self.image_generations(
            ImageGenerationRequest(model=request.model, prompt="variation", n=request.n, size=request.size, response_format=request.response_format)
        )

    async def video_generations(self, request: VideoGenerationRequest) -> dict[str, Any]:
        return {
            "id": f"video_mock_{uuid.uuid4().hex[:12]}",
            "object": "video",
            "status": "completed",
            "model": request.model,
            "data": [{"url": "https://example.invalid/apiswitch/mock-video.mp4"} for _ in range(request.n or 1)],
        }

    async def music_generations(self, request: MusicGenerationRequest) -> dict[str, Any]:
        return {
            "id": f"music_mock_{uuid.uuid4().hex[:12]}",
            "object": "music",
            "status": "completed",
            "model": request.model,
            "data": [{"url": "https://example.invalid/apiswitch/mock-music.wav"} for _ in range(request.n or 1)],
        }

    async def audio_speech(self, request: AudioSpeechRequest) -> AudioBinaryResponse:
        # A short valid PCM WAV header with no samples is enough for offline contract tests.
        wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        return AudioBinaryResponse(body=wav, media_type="audio/wav")

    async def audio_transcriptions(self, request: AudioTranscriptionRequest) -> dict[str, Any] | str:
        text = f"Mock transcription of {request.filename}."
        if request.response_format in {"text", "srt", "vtt"}:
            return text
        return {"text": text}

    async def moderations(self, request: ModerationRequest) -> dict[str, Any]:
        values = request.input if isinstance(request.input, list) else [request.input]
        return {
            "id": f"modr_mock_{uuid.uuid4().hex[:12]}",
            "model": request.model,
            "results": [
                {
                    "flagged": False,
                    "categories": {},
                    "category_scores": {},
                }
                for _ in values
            ],
        }

    async def rerank(self, request: RerankRequest) -> dict[str, Any]:
        query_words = set(request.query.lower().split())
        scored = [
            {"index": index, "relevance_score": len(query_words & set(document.lower().split()))}
            for index, document in enumerate(request.documents)
        ]
        scored.sort(key=lambda item: item["relevance_score"], reverse=True)
        return {"model": request.model, "results": scored[: request.top_n or len(scored)]}

    async def search(self, request: SearchRequest) -> dict[str, Any]:
        return {"object": "list", "data": [{"title": f"Mock result {index + 1}", "url": f"https://example.invalid/search/{index + 1}", "snippet": request.query} for index in range(request.max_results)]}

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        stream_id = f"chatcmpl_mock_{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        for token in ["Mock", " response", " from", " APISwitch", "."]:
            chunk = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": request.model,
                "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")
        final_chunk = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": request.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk, ensure_ascii=False)}\n\n".encode("utf-8")
        yield b"data: [DONE]\n\n"

    async def list_models(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "code-best",
                "object": "model",
                "owned_by": "apiswitch",
                "capabilities": ["text", "tools", "files"],
            },
            {
                "id": "vision-helper",
                "object": "model",
                "owned_by": "apiswitch",
                "capabilities": ["text", "vision", "files"],
            },
            {
                "id": "embedding-best",
                "object": "model",
                "owned_by": "apiswitch",
                "capabilities": ["embeddings"],
            },
        ]
