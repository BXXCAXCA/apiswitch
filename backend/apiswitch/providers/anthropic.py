import json
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx

from apiswitch.providers.base import ProviderAdapter, ProviderError
from apiswitch.schemas.gateway import AnthropicMessagesRequest, ChatCompletionRequest


DEFAULT_ANTHROPIC_MODELS = [
    {"id": "claude-3-5-sonnet-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
    {"id": "claude-3-5-haiku-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
    {"id": "claude-3-opus-latest", "owned_by": "anthropic", "capabilities": ["text", "vision", "tools"]},
]


class AnthropicProviderAdapter(ProviderAdapter):
    name = "anthropic"
    provider_type = "anthropic"

    def __init__(self, base_url: str, api_key: str | None, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise ProviderError("Missing Anthropic API key", "missing_api_key")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    async def chat(self, request: ChatCompletionRequest) -> dict[str, Any]:
        raise ProviderError("Use messages for Anthropic provider", "unsupported_protocol")

    async def stream_chat(self, request: ChatCompletionRequest) -> AsyncIterator[bytes]:
        """Bridge Anthropic Messages SSE to the shared OpenAI-compatible stream.

        Gateway streaming always consumes OpenAI-shaped chunks, including when the
        caller used the Anthropic or Gemini inbound protocol.  Converting the
        upstream event stream here preserves first-token latency and usage data.
        """
        payload = _openai_chat_to_anthropic_payload(request)
        stream_id = f"chatcmpl_anthropic_{uuid.uuid4().hex[:12]}"
        created = int(time.time())
        buffer = ""
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout_seconds,
                ) as response:
                    if response.status_code >= 400:
                        body = await response.aread()
                        raise ProviderError(
                            f"Anthropic Messages stream failed with status {response.status_code}: "
                            f"{body.decode('utf-8', errors='ignore')}",
                            "upstream_http_error",
                        )
                    self.record_response_headers(response.headers)
                    async for raw_chunk in response.aiter_text():
                        buffer += raw_chunk
                        while "\n\n" in buffer:
                            event, buffer = buffer.split("\n\n", 1)
                            converted = _anthropic_sse_event_to_openai(
                                event, stream_id, created, request.model
                            )
                            if converted is not None:
                                yield converted
            if buffer.strip():
                converted = _anthropic_sse_event_to_openai(buffer, stream_id, created, request.model)
                if converted is not None:
                    yield converted
            yield b"data: [DONE]\n\n"
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Anthropic Messages stream failed: {exc}") from exc

    async def messages(self, request: AnthropicMessagesRequest) -> dict[str, Any]:
        payload = request.model_dump(exclude_none=True)
        if payload.get("stream"):
            raise ProviderError("Use stream_chat for Anthropic streaming requests", "invalid_stream_path")
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self._headers(),
                    json=payload,
                )
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"Anthropic messages request failed: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(
                f"Anthropic messages request failed with status {response.status_code}: {response.text}",
                "upstream_http_error",
            )
        self.record_response_headers(response.headers)
        return response.json()

    async def list_models(self) -> list[dict[str, Any]]:
        return DEFAULT_ANTHROPIC_MODELS


def _openai_chat_to_anthropic_payload(request: ChatCompletionRequest) -> dict[str, Any]:
    """Translate the common chat request into Anthropic's Messages payload."""
    messages: list[dict[str, Any]] = []
    system_parts: list[str] = []
    for message in request.messages:
        text = _message_content_to_text(message.content)
        if message.role == "system":
            if text:
                system_parts.append(text)
            continue
        role = "assistant" if message.role == "assistant" else "user"
        messages.append({"role": role, "content": text})

    payload: dict[str, Any] = {
        "model": request.model,
        "messages": messages or [{"role": "user", "content": ""}],
        "max_tokens": request.max_tokens or 1024,
        "stream": True,
    }
    if system_parts:
        payload["system"] = "\n\n".join(system_parts)
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.top_p is not None:
        payload["top_p"] = request.top_p
    if request.tools:
        payload["tools"] = request.tools
    return payload


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"text", "input_text"} and "text" in item:
                    parts.append(str(item["text"]))
                elif "text" in item:
                    parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _anthropic_sse_event_to_openai(
    event: str, stream_id: str, created: int, model: str
) -> bytes | None:
    event_type: str | None = None
    payload: dict[str, Any] | None = None
    for line in event.splitlines():
        if line.startswith("event:"):
            event_type = line[len("event:") :].strip()
        elif line.startswith("data:"):
            try:
                candidate = json.loads(line[len("data:") :].strip())
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, dict):
                payload = candidate
    if payload is None:
        return None

    event_type = str(payload.get("type") or event_type or "")
    text: str | None = None
    finish_reason: str | None = None
    usage: dict[str, int] | None = None
    if event_type == "content_block_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("type") == "text_delta":
            candidate = delta.get("text")
            if isinstance(candidate, str):
                text = candidate
    elif event_type == "message_delta":
        delta = payload.get("delta")
        if isinstance(delta, dict) and delta.get("stop_reason"):
            finish_reason = _anthropic_finish_reason_to_openai(str(delta["stop_reason"]))

    raw_usage = payload.get("usage")
    if event_type == "message_start" and isinstance(payload.get("message"), dict):
        raw_usage = payload["message"].get("usage", raw_usage)
    if isinstance(raw_usage, dict):
        prompt = raw_usage.get("input_tokens")
        completion = raw_usage.get("output_tokens")
        if any(isinstance(value, int) for value in (prompt, completion)):
            usage = {
                "prompt_tokens": prompt or 0,
                "completion_tokens": completion or 0,
                "total_tokens": (prompt or 0) + (completion or 0),
            }

    if not text and finish_reason is None and usage is None:
        return None
    chunk: dict[str, Any] = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": text} if text else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage is not None:
        chunk["usage"] = usage
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n".encode("utf-8")


def _anthropic_finish_reason_to_openai(reason: str) -> str:
    if reason == "max_tokens":
        return "length"
    if reason in {"refusal", "safety"}:
        return "content_filter"
    if reason == "tool_use":
        return "tool_calls"
    return "stop"
