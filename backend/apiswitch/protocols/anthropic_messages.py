from apiswitch.protocols.internal import InternalMessage, InternalRequest
from apiswitch.schemas.gateway import AnthropicMessagesRequest


def from_anthropic_messages(request: AnthropicMessagesRequest) -> InternalRequest:
    messages = []
    if request.system:
        messages.append(InternalMessage(role="system", content=request.system))
    messages.extend(InternalMessage(role=msg.role, content=msg.content) for msg in request.messages)
    return InternalRequest(
        model=request.model,
        messages=messages,
        stream=request.stream,
        tools=request.tools or [],
        metadata={"inbound_protocol": "anthropic_messages"},
    )
