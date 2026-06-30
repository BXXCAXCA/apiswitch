from typing import Any

from apiswitch.protocols.internal import InternalMessage, InternalRequest
from apiswitch.schemas.gateway import ResponsesRequest


def from_openai_responses(request: ResponsesRequest) -> InternalRequest:
    return InternalRequest(
        model=request.model,
        messages=[InternalMessage(role="user", content=request.input)],
        stream=request.stream,
        tools=request.tools or [],
        metadata={"inbound_protocol": "openai_responses", "raw_input": request.input},
    )


def to_openai_responses(content: str, model: str) -> dict[str, Any]:
    return {
        "object": "response",
        "model": model,
        "status": "completed",
        "output": [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": content}]}],
    }
