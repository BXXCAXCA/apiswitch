from apiswitch.protocols.internal import InternalMessage, InternalRequest
from apiswitch.schemas.gateway import ChatCompletionRequest


def from_openai_chat(request: ChatCompletionRequest) -> InternalRequest:
    return InternalRequest(
        model=request.model,
        messages=[InternalMessage(role=msg.role, content=msg.content) for msg in request.messages],
        stream=request.stream,
        tools=request.tools or [],
        metadata={"inbound_protocol": "openai_chat"},
    )
