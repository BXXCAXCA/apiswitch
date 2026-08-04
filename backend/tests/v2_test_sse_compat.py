from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from apiswitch.stream_compat import SSECompatibilityMiddleware

Send = Callable[[dict[str, Any]], Awaitable[None]]


def _run(app, path: str = "/v1/responses") -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    asyncio.run(
        SSECompatibilityMiddleware(app)(
            {"type": "http", "method": "POST", "path": path},
            receive,
            send,
        )
    )
    return messages


def _body(messages: list[dict[str, Any]]) -> bytes:
    return b"".join(
        message.get("body") or b""
        for message in messages
        if message.get("type") == "http.response.body"
    )


def test_responses_terminal_frame_is_compact_and_done_is_appended() -> None:
    terminal = {
        "type": "response.completed",
        "sequence_number": 12,
        "response": {
            "id": "resp_req_finish",
            "object": "response",
            "created_at": 1_786_000_000,
            "status": "completed",
            "error": None,
            "incomplete_details": None,
            "model": "client-model",
            "instructions": "system prompt " * 20_000,
            "tools": [{"type": "function", "name": "large-tool"}] * 500,
            "output": [{"type": "message", "content": "already streamed"}],
            "usage": {
                "prompt_tokens": "7",
                "completion_tokens": 3,
                "total_tokens": 10,
            },
        },
    }
    terminal_frame = (
        "event: response.completed\n"
        f"data: {json.dumps(terminal)}\n\n"
    ).encode()
    first_frame = (
        b"event: response.output_text.delta\n"
        b'data: {"type":"response.output_text.delta",'
        b'"item_id":"msg_req_finish","output_index":0,'
        b'"content_index":0,"delta":"ok"}\n\n'
    )

    async def app(_scope, _receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream; charset=utf-8"),
                    (b"cache-control", b"private"),
                ],
            }
        )
        combined = first_frame + terminal_frame
        cut = len(first_frame) + 257
        await send(
            {
                "type": "http.response.body",
                "body": combined[:cut],
                "more_body": True,
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": combined[cut:],
                "more_body": False,
            }
        )

    messages = _run(app)
    headers = dict(messages[0]["headers"])
    body = _body(messages)

    assert headers[b"cache-control"] == b"no-cache, no-transform"
    assert headers[b"x-accel-buffering"] == b"no"
    assert headers[b"x-apiswitch-sse-compat"] == b"responses-terminal-v1"
    assert headers[b"x-apiswitch-version"]
    assert b"response.output_text.delta" in body
    assert b"system prompt" not in body
    assert b"large-tool" not in body
    assert body.count(b"data: [DONE]\n\n") == 1

    terminal_data = next(
        line.removeprefix(b"data: ")
        for line in body.splitlines()
        if line.startswith(b"data: ")
        and b'"type":"response.completed"' in line
    )
    parsed = json.loads(terminal_data)
    response = parsed["response"]
    assert response == {
        "id": "resp_req_finish",
        "object": "response",
        "created_at": 1_786_000_000,
        "status": "completed",
        "error": None,
        "incomplete_details": None,
        "model": "client-model",
        "usage": {
            "input_tokens": 7,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 3,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 10,
        },
        "service_tier": None,
    }


def test_existing_done_sentinel_is_not_duplicated() -> None:
    terminal = {
        "type": "response.completed",
        "response": {
            "incomplete_details": None,
            "usage": {
                "input_tokens": 1,
                "input_tokens_details": {"cached_tokens": 0},
                "output_tokens": 1,
                "output_tokens_details": {"reasoning_tokens": 0},
            },
        },
    }

    async def app(_scope, _receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        body = (
            f"data: {json.dumps(terminal)}\n\n"
            "data: [DONE]\n\n"
        ).encode()
        await send(
            {
                "type": "http.response.body",
                "body": body,
                "more_body": False,
            }
        )

    assert _body(_run(app)).count(b"data: [DONE]\n\n") == 1


def test_non_responses_stream_is_untouched() -> None:
    original = b"data: original\n\n"

    async def app(_scope, _receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": original,
                "more_body": False,
            }
        )

    messages = _run(app, "/v1/chat/completions")
    assert _body(messages) == original
    assert b"x-apiswitch-sse-compat" not in dict(messages[0]["headers"])
