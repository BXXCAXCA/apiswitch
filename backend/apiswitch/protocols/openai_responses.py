import json
import time
import uuid
from typing import Any

from apiswitch.protocols.internal import InternalMessage, InternalRequest
from apiswitch.schemas.gateway import ChatCompletionRequest, ChatMessage, ResponsesRequest


def from_openai_responses(request: ResponsesRequest) -> InternalRequest:
    return InternalRequest(
        model=request.model,
        messages=[InternalMessage(role=message.role, content=message.content) for message in responses_input_to_messages(request.input)],
        stream=request.stream,
        tools=request.tools or [],
        metadata={"inbound_protocol": "openai_responses", "raw_input": request.input},
    )


def responses_input_to_messages(input_value: Any) -> list[ChatMessage]:
    if isinstance(input_value, str):
        return [ChatMessage(role="user", content=input_value)]

    if isinstance(input_value, list):
        messages: list[ChatMessage] = []
        buffered_parts: list[str] = []
        for item in input_value:
            if isinstance(item, dict) and item.get("type") == "message":
                if buffered_parts:
                    messages.append(ChatMessage(role="user", content="\n".join(buffered_parts)))
                    buffered_parts = []
                messages.append(
                    ChatMessage(
                        role=str(item.get("role") or "user"),
                        content=_content_to_text(item.get("content")),
                    )
                )
            else:
                buffered_parts.append(_content_to_text(item))
        if buffered_parts:
            messages.append(ChatMessage(role="user", content="\n".join(buffered_parts)))
        return messages or [ChatMessage(role="user", content="")]

    return [ChatMessage(role="user", content=_content_to_text(input_value))]


def responses_to_chat_completion(request: ResponsesRequest) -> ChatCompletionRequest:
    return ChatCompletionRequest(
        model=request.model,
        messages=responses_input_to_messages(request.input),
        stream=False,
        temperature=request.temperature,
        top_p=request.top_p,
        max_tokens=request.max_output_tokens,
        tools=request.tools,
    )


def chat_completion_to_openai_responses(chat_response: dict[str, Any], model: str) -> dict[str, Any]:
    choice = (chat_response.get("choices") or [{}])[0]
    message = choice.get("message") or {}
    text = _content_to_text(message.get("content"))
    usage = chat_response.get("usage") or {}
    output_message = {
        "id": f"msg_{uuid.uuid4().hex[:16]}",
        "type": "message",
        "status": "completed",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }
    response = {
        "id": f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "status": "completed",
        "output": [output_message],
        "usage": {
            "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens", 0)),
            "output_tokens": usage.get("completion_tokens", usage.get("output_tokens", 0)),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }
    if chat_response.get("apiswitch"):
        response["apiswitch"] = chat_response["apiswitch"]
    return response


def to_openai_responses(content: str, model: str) -> dict[str, Any]:
    return {
        "id": f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": int(time.time()),
        "model": model,
        "status": "completed",
        "output": [
            {
                "id": f"msg_{uuid.uuid4().hex[:16]}",
                "type": "message",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content}],
            }
        ],
    }


def _content_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                if item.get("type") in {"input_text", "output_text", "text"}:
                    parts.append(str(item.get("text") or ""))
                elif "content" in item:
                    parts.append(_content_to_text(item.get("content")))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(_content_to_text(item))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if value.get("type") in {"input_text", "output_text", "text"}:
            return str(value.get("text") or "")
        if "content" in value:
            return _content_to_text(value.get("content"))
        return json.dumps(value, ensure_ascii=False)
    return str(value)
