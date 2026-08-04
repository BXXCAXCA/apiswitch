from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from apiswitch import __version__
from apiswitch.protocols.canonical import to_openai_responses_usage

ASGIApp = Callable[
    [
        dict[str, Any],
        Callable[[], Awaitable[dict[str, Any]]],
        Callable[[dict[str, Any]], Awaitable[None]],
    ],
    Awaitable[None],
]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]

_OPENAI_CHAT_PATHS = {"/v1/chat/completions", "/v1/v1/chat/completions"}
_OPENAI_RESPONSES_PATHS = {"/v1/responses", "/v1/v1/responses"}
_FRAME_DELIMITER = b"\n\n"
_DONE_FRAME = b"data: [DONE]\n\n"


def _stream_mode(path: str) -> str | None:
    if path in _OPENAI_CHAT_PATHS:
        return "openai_chat"
    if path in _OPENAI_RESPONSES_PATHS:
        return "openai_responses"
    return None


class SSECompatibilityMiddleware:
    """Normalize decisive terminal SSE frames for strict AI SDK clients.

    Cherry Studio rejects the final AI SDK ``finish`` event unless its normalized
    reason is ``stop`` or ``tool-calls``. Both OpenAI-compatible Chat and OpenAI
    Responses providers initialize that reason as ``other`` and only replace it
    after parsing a valid protocol terminal frame. This middleware keeps all
    incremental content untouched, normalizes an explicit terminal frame, and
    only synthesizes ``stop`` when APISwitch completed a successful Chat stream
    but the generated terminal frame was absent before ``[DONE]`` or EOF.

    Explicit ``length``, ``content_filter``, ``tool_calls``, and unknown provider
    finish reasons are preserved verbatim; they are never silently rewritten.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        mode = _stream_mode(str(scope.get("path") or ""))
        if mode is None:
            await self.app(scope, receive, send)
            return

        stream = _CompatibilityStream(send, mode)
        await self.app(scope, receive, stream.send)


class _CompatibilityStream:
    def __init__(self, send: Send, mode: str) -> None:
        self._send = send
        self._mode = mode
        self._enabled = False
        self._buffer = b""
        self._done_sent = False
        self._terminal_seen = False
        self._saw_payload = False
        self._saw_error = False
        self._chat_id: str | None = None
        self._chat_model: str | None = None
        self._chat_created: int | None = None

    async def send(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "http.response.start":
            headers = list(message.get("headers") or [])
            self._enabled = _is_event_stream(headers)
            if self._enabled:
                message = {
                    **message,
                    "headers": _stream_headers(headers, self._mode),
                }
            await self._send(message)
            return

        if message_type != "http.response.body" or not self._enabled:
            await self._send(message)
            return

        # JSON string newlines are escaped, so normalizing SSE CRLF separators is safe.
        self._buffer += bytes(message.get("body") or b"")
        self._buffer = self._buffer.replace(b"\r\n", b"\n")
        outgoing = bytearray()

        while _FRAME_DELIMITER in self._buffer:
            frame, self._buffer = self._buffer.split(_FRAME_DELIMITER, 1)
            outgoing.extend(self._process_frame(frame))

        more_body = bool(message.get("more_body"))
        if not more_body:
            if self._buffer:
                outgoing.extend(self._process_frame(self._buffer))
                self._buffer = b""
            outgoing.extend(self._finish_stream())

        await self._send(
            {**message, "body": bytes(outgoing), "more_body": more_body}
        )

    def _process_frame(self, frame: bytes) -> bytes:
        normalized, terminal, done, payload = _normalize_frame(frame, self._mode)
        if payload is not None:
            self._observe_payload(payload)
        if terminal:
            self._terminal_seen = True

        output = bytearray()
        if done:
            if self._done_sent:
                return b""
            if self._mode == "openai_chat" and self._should_synthesize_chat_stop():
                output.extend(self._chat_stop_frame())
                self._terminal_seen = True
            output.extend(_DONE_FRAME)
            self._done_sent = True
            return bytes(output)

        if normalized:
            output.extend(normalized)
            output.extend(_FRAME_DELIMITER)
        return bytes(output)

    def _observe_payload(self, payload: dict[str, Any]) -> None:
        self._saw_payload = True
        if "error" in payload and payload.get("error") is not None:
            self._saw_error = True

        if self._mode != "openai_chat":
            return
        if isinstance(payload.get("id"), str):
            self._chat_id = payload["id"]
        if isinstance(payload.get("model"), str):
            self._chat_model = payload["model"]
        if isinstance(payload.get("created"), int):
            self._chat_created = payload["created"]

    def _should_synthesize_chat_stop(self) -> bool:
        return (
            not self._terminal_seen
            and self._saw_payload
            and not self._saw_error
        )

    def _chat_stop_frame(self) -> bytes:
        payload = {
            "id": self._chat_id or "chatcmpl_apiswitch_terminal",
            "object": "chat.completion.chunk",
            "created": self._chat_created or int(time.time()),
            "model": self._chat_model or "",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "stop",
                }
            ],
        }
        return _data_frame(payload)

    def _finish_stream(self) -> bytes:
        if self._done_sent:
            return b""

        output = bytearray()
        if self._mode == "openai_chat" and self._should_synthesize_chat_stop():
            output.extend(self._chat_stop_frame())
            self._terminal_seen = True

        # Append the conventional sentinel only after a parsed/synthesized terminal.
        if self._terminal_seen:
            output.extend(_DONE_FRAME)
            self._done_sent = True
        return bytes(output)


def _is_event_stream(headers: list[tuple[bytes, bytes]]) -> bool:
    return any(
        name.lower() == b"content-type"
        and b"text/event-stream" in value.lower()
        for name, value in headers
    )


def _stream_headers(
    headers: list[tuple[bytes, bytes]], mode: str
) -> list[tuple[bytes, bytes]]:
    compat = (
        b"chat-terminal-v1"
        if mode == "openai_chat"
        else b"responses-terminal-v2"
    )
    protocol = (
        b"openai_chat"
        if mode == "openai_chat"
        else b"openai_responses"
    )
    replacements = {
        b"cache-control": b"no-cache, no-transform",
        b"connection": b"keep-alive",
        b"x-accel-buffering": b"no",
        b"x-apiswitch-protocol": protocol,
        b"x-apiswitch-sse-compat": compat,
        b"x-apiswitch-version": __version__.encode("ascii"),
    }
    output: list[tuple[bytes, bytes]] = []
    seen: set[bytes] = set()
    for name, value in headers:
        lower = name.lower()
        if lower in replacements:
            if lower not in seen:
                output.append((lower, replacements[lower]))
                seen.add(lower)
        else:
            output.append((name, value))
    for name, value in replacements.items():
        if name not in seen:
            output.append((name, value))
    return output


def _normalize_frame(
    frame: bytes, mode: str
) -> tuple[bytes, bool, bool, dict[str, Any] | None]:
    """Return ``(frame, is_terminal, is_done, parsed_payload)``."""

    if not frame.strip():
        return b"", False, False, None

    lines = frame.splitlines()
    data_parts = [
        line[5:].lstrip()
        for line in lines
        if line.startswith(b"data:")
    ]
    if not data_parts:
        return frame, False, False, None

    raw_data = b"\n".join(data_parts)
    if raw_data.strip() == b"[DONE]":
        return b"", False, True, None

    try:
        payload = json.loads(raw_data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return frame, False, False, None
    if not isinstance(payload, dict):
        return frame, False, False, None

    if mode == "openai_chat":
        normalized, terminal = _normalize_chat_payload(payload)
    else:
        normalized, terminal = _normalize_responses_payload(payload)

    if normalized is payload:
        return frame, terminal, False, payload
    return _replace_data_lines(lines, normalized), terminal, False, normalized


def _normalize_chat_payload(
    payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        return payload, False

    terminal_choices: list[dict[str, Any]] = []
    terminal = False
    for fallback_index, choice in enumerate(choices):
        if not isinstance(choice, dict):
            continue
        finish_reason = choice.get("finish_reason")
        if finish_reason is None:
            continue
        if not isinstance(finish_reason, str):
            return payload, False
        terminal = True
        index = choice.get("index")
        terminal_choices.append(
            {
                "index": index if isinstance(index, int) else fallback_index,
                "delta": {},
                "finish_reason": finish_reason,
            }
        )

    if not terminal:
        return payload, False

    normalized = {
        key: value
        for key, value in payload.items()
        if key not in {"id", "created", "model", "choices", "usage"}
    }
    if isinstance(payload.get("id"), str):
        normalized["id"] = payload["id"]
    if isinstance(payload.get("created"), int):
        normalized["created"] = payload["created"]
    if isinstance(payload.get("model"), str):
        normalized["model"] = payload["model"]
    normalized["object"] = "chat.completion.chunk"
    normalized["choices"] = terminal_choices
    if isinstance(payload.get("usage"), dict):
        normalized["usage"] = _normalize_chat_usage(payload["usage"])
    return normalized, True


def _normalize_chat_usage(usage: dict[str, Any]) -> dict[str, Any]:
    prompt = _usage_number(usage.get("prompt_tokens", usage.get("input_tokens")))
    completion = _usage_number(
        usage.get("completion_tokens", usage.get("output_tokens"))
    )
    total = max(_usage_number(usage.get("total_tokens")), prompt + completion)
    result: dict[str, Any] = {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }
    prompt_details = usage.get("prompt_tokens_details")
    if isinstance(prompt_details, dict):
        result["prompt_tokens_details"] = {
            "cached_tokens": _usage_number(prompt_details.get("cached_tokens"))
        }
    completion_details = usage.get("completion_tokens_details")
    if isinstance(completion_details, dict):
        result["completion_tokens_details"] = {
            "reasoning_tokens": _usage_number(
                completion_details.get("reasoning_tokens")
            ),
            "accepted_prediction_tokens": _usage_number(
                completion_details.get("accepted_prediction_tokens")
            ),
            "rejected_prediction_tokens": _usage_number(
                completion_details.get("rejected_prediction_tokens")
            ),
        }
    return result


def _normalize_responses_payload(
    payload: dict[str, Any]
) -> tuple[dict[str, Any], bool]:
    if payload.get("type") != "response.completed":
        return payload, False

    response = payload.get("response")
    if not isinstance(response, dict):
        return payload, False

    minimal: dict[str, Any] = {}
    for key in (
        "id",
        "object",
        "created_at",
        "status",
        "error",
        "incomplete_details",
        "model",
    ):
        if key in response:
            minimal[key] = response[key]
    minimal["usage"] = to_openai_responses_usage(
        response.get("usage")
        if isinstance(response.get("usage"), dict)
        else None
    )
    minimal["service_tier"] = response.get("service_tier")
    normalized = {**payload, "response": minimal}
    return normalized, True


def _replace_data_lines(
    lines: list[bytes], payload: dict[str, Any]
) -> bytes:
    preserved = [
        line for line in lines if not line.startswith(b"data:")
    ]
    preserved.append(
        b"data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    return b"\n".join(preserved)


def _data_frame(payload: dict[str, Any]) -> bytes:
    return (
        b"data: "
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        + _FRAME_DELIMITER
    )


def _usage_number(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0
