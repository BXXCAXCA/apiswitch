import json
from collections.abc import AsyncIterator

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


def _sse(event: str, payload: dict) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")


async def chat_stream_to_anthropic_sse(
    chunks: AsyncIterator[bytes], model: str
) -> AsyncIterator[bytes]:
    """Translate the shared OpenAI event stream to Anthropic Messages SSE."""
    message_id = "msg_apiswitch"
    yield _sse(
        "message_start",
        {
            "type": "message_start",
            "message": {
                "id": message_id,
                "type": "message",
                "role": "assistant",
                "model": model,
                "content": [],
                "stop_reason": None,
                "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        },
    )
    yield _sse(
        "content_block_start",
        {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
    )
    async for chunk in chunks:
        for line in chunk.decode("utf-8", errors="replace").splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[len("data:") :].strip()
            if raw == "[DONE]":
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            choices = payload.get("choices", []) if isinstance(payload, dict) else []
            delta = choices[0].get("delta", {}) if choices else {}
            text = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(text, str) and text:
                yield _sse(
                    "content_block_delta",
                    {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}},
                )
    yield _sse("content_block_stop", {"type": "content_block_stop", "index": 0})
    yield _sse(
        "message_delta",
        {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None}, "usage": {"output_tokens": 0}},
    )
    yield _sse("message_stop", {"type": "message_stop"})
