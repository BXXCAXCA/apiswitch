import time
import uuid
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
