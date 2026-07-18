import json
from collections.abc import AsyncIterator
from typing import Any

from apiswitch.schemas.gateway import ChatCompletionRequest, ChatMessage, GeminiGenerateContentRequest


def _parts_to_text(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    values: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        if isinstance(part.get("text"), str):
            values.append(part["text"])
        elif part:
            values.append(json.dumps(part, ensure_ascii=False))
    return "\n".join(value for value in values if value)


def gemini_request_to_chat(
    model: str,
    request: GeminiGenerateContentRequest,
    *,
    stream: bool = False,
) -> ChatCompletionRequest:
    messages: list[ChatMessage] = []
    if request.systemInstruction:
        system_text = _parts_to_text(request.systemInstruction.get("parts"))
        if system_text:
            messages.append(ChatMessage(role="system", content=system_text))

    for content in request.contents:
        role = content.get("role", "user")
        chat_role = "assistant" if role == "model" else "user"
        messages.append(ChatMessage(role=chat_role, content=_parts_to_text(content.get("parts"))))

    config = request.generationConfig or {}
    return ChatCompletionRequest(
        model=model,
        messages=messages,
        stream=stream,
        temperature=config.get("temperature"),
        top_p=config.get("topP"),
        max_tokens=config.get("maxOutputTokens"),
        tools=request.tools,
    )


def chat_response_to_gemini(response: dict[str, Any], model: str) -> dict[str, Any]:
    choices = response.get("choices", [])
    message = choices[0].get("message", {}) if choices else {}
    content = message.get("content", "")
    if not isinstance(content, str):
        content = json.dumps(content, ensure_ascii=False)

    usage = response.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0) or 0
    completion_tokens = usage.get("completion_tokens", 0) or 0
    return {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": content}]},
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": completion_tokens,
            "totalTokenCount": prompt_tokens + completion_tokens,
        },
        "modelVersion": model,
        "responseId": response.get("id"),
        "apiswitch": response.get("apiswitch", {}),
    }


async def chat_stream_to_gemini_sse(chunks: AsyncIterator[bytes], model: str) -> AsyncIterator[bytes]:
    """Translate the shared OpenAI streaming executor to Gemini REST SSE."""
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
            if not isinstance(payload, dict):
                continue
            choices = payload.get("choices", [])
            choice = choices[0] if isinstance(choices, list) and choices else {}
            delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
            text = delta.get("content") if isinstance(delta, dict) else None
            finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
            if not isinstance(text, str) and not finish_reason:
                continue
            candidate: dict[str, Any] = {
                "content": {"role": "model", "parts": [{"text": text or ""}]},
                "index": 0,
            }
            if finish_reason:
                candidate["finishReason"] = "STOP" if finish_reason == "stop" else str(finish_reason).upper()
            response: dict[str, Any] = {"candidates": [candidate], "modelVersion": model}
            if payload.get("apiswitch"):
                response["apiswitch"] = payload["apiswitch"]
            yield f"data: {json.dumps(response, ensure_ascii=False)}\n\n".encode("utf-8")
