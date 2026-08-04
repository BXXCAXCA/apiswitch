from __future__ import annotations

import json
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

_RESPONSES_PATHS = {"/v1/responses", "/v1/v1/responses"}
_FRAME_DELIMITER = b"\n\n"
_DONE_FRAME = b"data: [DONE]\n\n"


class SSECompatibilityMiddleware:
    """Harden Responses SSE termination for strict desktop clients.

    Several AI SDK releases keep the finish reason at ``other`` until a valid
    ``response.completed`` frame is parsed. APISwitch already streams content in
    earlier frames, so repeating instructions, tools, and output in the terminal
    frame is unnecessary and makes that decisive frame fragile. This middleware
    leaves incremental events untouched, emits a compact terminal frame, and
    appends the conventional ``[DONE]`` sentinel.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Receive,
        send: Send,
    ) -> None:
        if (
            scope.get("type") != "http"
            or str(scope.get("path") or "") not in _RESPONSES_PATHS
        ):
            await self.app(scope, receive, send)
            return

        stream = _ResponsesStream(send)
        await self.app(scope, receive, stream.send)


class _ResponsesStream:
    def __init__(self, send: Send) -> None:
        self._send = send
        self._enabled = False
        self._buffer = b""
        self._done_sent = False

    async def send(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "http.response.start":
            headers = list(message.get("headers") or [])
            self._enabled = _is_event_stream(headers)
            if self._enabled:
                message = {**message, "headers": _stream_headers(headers)}
            await self._send(message)
            return

        if message_type != "http.response.body" or not self._enabled:
            await self._send(message)
            return

        self._buffer += bytes(message.get("body") or b"")
        outgoing = bytearray()

        while _FRAME_DELIMITER in self._buffer:
            frame, self._buffer = self._buffer.split(_FRAME_DELIMITER, 1)
            normalized, completed, done = _normalize_frame(frame)
            if done and self._done_sent:
                normalized = b""
            elif done:
                self._done_sent = True

            if normalized:
                outgoing.extend(normalized)
                outgoing.extend(_FRAME_DELIMITER)

            if completed and not self._done_sent:
                outgoing.extend(_DONE_FRAME)
                self._done_sent = True

        more_body = bool(message.get("more_body"))
        if not more_body and self._buffer:
            normalized, completed, done = _normalize_frame(self._buffer)
            if done and self._done_sent:
                normalized = b""
            elif done:
                self._done_sent = True

            if normalized:
                outgoing.extend(normalized)
                if not normalized.endswith(_FRAME_DELIMITER):
                    outgoing.extend(_FRAME_DELIMITER)

            if completed and not self._done_sent:
                outgoing.extend(_DONE_FRAME)
                self._done_sent = True
            self._buffer = b""

        await self._send(
            {**message, "body": bytes(outgoing), "more_body": more_body}
        )


def _is_event_stream(headers: list[tuple[bytes, bytes]]) -> bool:
    return any(
        name.lower() == b"content-type"
        and b"text/event-stream" in value.lower()
        for name, value in headers
    )


def _stream_headers(
    headers: list[tuple[bytes, bytes]],
) -> list[tuple[bytes, bytes]]:
    replacements = {
        b"cache-control": b"no-cache, no-transform",
        b"connection": b"keep-alive",
        b"x-accel-buffering": b"no",
        b"x-apiswitch-sse-compat": b"responses-terminal-v1",
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


def _normalize_frame(frame: bytes) -> tuple[bytes, bool, bool]:
    """Return ``(frame, is_completed, is_done)``."""

    if not frame.strip():
        return b"", False, False

    lines = frame.splitlines()
    data_parts = [
        line[5:].lstrip()
        for line in lines
        if line.startswith(b"data:")
    ]
    if not data_parts:
        return frame, False, False

    raw_data = b"\n".join(data_parts)
    if raw_data.strip() == b"[DONE]":
        return b"\n".join(lines), False, True

    try:
        payload = json.loads(raw_data)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return frame, False, False

    if (
        not isinstance(payload, dict)
        or payload.get("type") != "response.completed"
    ):
        return frame, False, False

    response = payload.get("response")
    if not isinstance(response, dict):
        return frame, False, False

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
    payload["response"] = minimal

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
    return b"\n".join(preserved), True, False
