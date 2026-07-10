import json
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
        stream=False,
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
