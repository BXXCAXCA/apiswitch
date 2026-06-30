from fastapi import APIRouter

from apiswitch.schemas.gateway import AnthropicMessagesRequest

router = APIRouter(prefix="/v1", tags=["Gateway - Anthropic Messages"])


@router.post("/messages")
async def create_message(payload: AnthropicMessagesRequest) -> dict:
    return {
        "id": "msg_mock_001",
        "type": "message",
        "role": "assistant",
        "model": payload.model,
        "content": [{"type": "text", "text": "Mock response from APISwitch Messages."}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }
