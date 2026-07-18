import json
from collections.abc import AsyncIterator


async def rewrite_openai_sse_model(
    chunks: AsyncIterator[bytes],
    unified_model: str,
    metadata: dict | None = None,
) -> AsyncIterator[bytes]:
    """Rewrite OpenAI-compatible SSE JSON events to preserve the unified model name.

    Upstream providers emit their own model name in streaming chunks. APISwitch
    keeps the client-facing model as the requested unified model and attaches
    routing metadata under `apiswitch` for JSON data events.
    """
    buffer = ""
    async for chunk in chunks:
        buffer += chunk.decode("utf-8", errors="ignore")
        while "\n\n" in buffer:
            event, buffer = buffer.split("\n\n", 1)
            rewritten = _rewrite_single_event(event, unified_model, metadata or {})
            yield f"{rewritten}\n\n".encode("utf-8")
    if buffer.strip():
        yield f"{_rewrite_single_event(buffer, unified_model, metadata or {})}\n\n".encode("utf-8")


def _rewrite_single_event(event: str, unified_model: str, metadata: dict) -> str:
    lines = event.splitlines()
    output_lines: list[str] = []
    for line in lines:
        if not line.startswith("data:"):
            output_lines.append(line)
            continue
        data = line[len("data:") :].strip()
        if data == "[DONE]":
            output_lines.append(line)
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            output_lines.append(line)
            continue
        if isinstance(payload, dict):
            payload["model"] = unified_model
            if metadata:
                payload.setdefault("apiswitch", {}).update(metadata)
        output_lines.append(f"data: {json.dumps(payload, ensure_ascii=False)}")
    return "\n".join(output_lines)


def inspect_openai_sse_event(chunk: bytes) -> tuple[str, dict[str, int]]:
    """Return text deltas and optional token usage from one normalized SSE event."""
    text_parts: list[str] = []
    usage: dict[str, int] = {}
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
        if isinstance(choices, list) and choices:
            delta = choices[0].get("delta", {}) if isinstance(choices[0], dict) else {}
            content = delta.get("content") if isinstance(delta, dict) else None
            if isinstance(content, str):
                text_parts.append(content)
        raw_usage = payload.get("usage", {})
        if isinstance(raw_usage, dict):
            for field in ("prompt_tokens", "completion_tokens"):
                value = raw_usage.get(field)
                if isinstance(value, int):
                    usage[field] = value
    return "".join(text_parts), usage
