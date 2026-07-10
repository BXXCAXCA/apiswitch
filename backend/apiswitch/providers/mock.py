import base64
import hashlib
import json
import math
import struct
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from apiswitch.providers.base import ProviderAdapter
from apiswitch.schemas.gateway import AnthropicMessagesRequest, ChatCompletionRequest, EmbeddingsRequest
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
