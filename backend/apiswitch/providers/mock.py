import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from apiswitch.providers.base import ProviderAdapter
from apiswitch.schemas.gateway import ChatCompletionRequest


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
        ]
