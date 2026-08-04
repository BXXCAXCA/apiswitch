import json
from uuid import uuid4

from apiswitch.gateway.v2 import render_egress, render_sse
from apiswitch.protocols.canonical import CanonicalRequest, CanonicalResponse, response_events


def _streaming_gateway(client):
    provider = client.post(
        "/api/admin/provider-instances",
        json={"name": f"stream-{uuid4().hex}", "template_key": "openai", "base_url": "mock://stream"},
    ).json()
    upstream = client.post(
        f"/api/admin/provider-instances/{provider['id']}/upstream-models",
        json={"model_id": "mock-stream", "input_capabilities_json": ["text"], "output_capabilities_json": ["text"]},
    ).json()
    unified = client.post(
        "/api/admin/unified-models",
        json={"name": "stream-model", "enabled_protocols": ["openai_chat", "openai_responses", "anthropic_messages", "gemini_v1beta"]},
    ).json()
    assert client.post(f"/api/admin/unified-models/{unified['id']}/candidates", json={"upstream_model_id": upstream["id"]}).status_code == 201
    token = client.post("/api/admin/tokens", json={"name": "stream-token", "unified_model_ids": [unified["id"]]}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_each_chat_protocol_uses_its_native_sse_vocabulary(client):
    headers = _streaming_gateway(client)

    chat = client.post("/v1/chat/completions", headers=headers, json={"model": "stream-model", "messages": [{"role": "user", "content": "hello"}], "stream": True})
    assert chat.status_code == 200
    assert '"object":"chat.completion.chunk"' in chat.text
    assert '"content":"Mock upstream response"' in chat.text
    assert chat.text.endswith("data: [DONE]\n\n")
    assert "event: start" not in chat.text

    responses = client.post("/v1/responses", headers=headers, json={"model": "stream-model", "input": "hello", "stream": True})
    assert responses.status_code == 200
    assert "event: response.created" in responses.text
    assert "event: response.output_item.added" in responses.text
    assert "event: response.content_part.added" in responses.text
    assert "event: response.output_text.delta" in responses.text
    assert "event: response.output_text.done" in responses.text
    assert "event: response.content_part.done" in responses.text
    assert "event: response.output_item.done" in responses.text
    assert "event: response.completed" in responses.text

    anthropic = client.post("/v1/messages", headers=headers, json={"model": "stream-model", "max_tokens": 20, "messages": [{"role": "user", "content": "hello"}], "stream": True})
    assert anthropic.status_code == 200
    assert "event: message_start" in anthropic.text
    assert "event: content_block_delta" in anthropic.text
    assert '"type":"message_stop"' in anthropic.text

    gemini = client.post("/v1beta/models/stream-model:streamGenerateContent", headers=headers, json={"contents": [{"parts": [{"text": "hello"}]}]})
    assert gemini.status_code == 200
    assert gemini.headers["content-type"].startswith("text/event-stream")
    assert gemini.text.startswith("data: ")
    assert '"text":"Mock upstream response"' in gemini.text
    assert '"finishReason":"STOP"' in gemini.text

    logs = client.get("/api/admin/logs").json()
    assert logs and all(row["first_token_latency_ms"] is not None for row in logs)
    summary = client.get("/api/admin/dashboard/summary").json()
    assert summary["first_token_latency_ms"] > 0


def test_responses_stream_establishes_reasoning_text_and_tool_parts_before_deltas():
    request = CanonicalRequest("chat", "openai_responses", "stream-model", stream=True)
    upstream = CanonicalResponse(
        reasoning_content="think",
        text="answer",
        tool_calls=[{"id": "call_weather", "name": "weather", "arguments": {"city": "Shanghai"}}],
    )
    result = render_egress(request, upstream, "req_stream")
    chunks = render_sse(request, response_events(upstream, "req_stream", result))
    records = [json.loads(chunk.split("data: ", 1)[1]) for chunk in chunks]
    event_types = [record["type"] for record in records]

    assert event_types == [
        "response.created",
        "response.in_progress",
        "response.output_item.added",
        "response.reasoning_summary_part.added",
        "response.reasoning_summary_text.delta",
        "response.reasoning_summary_text.done",
        "response.reasoning_summary_part.done",
        "response.output_item.done",
        "response.output_item.added",
        "response.content_part.added",
        "response.output_text.delta",
        "response.output_text.done",
        "response.content_part.done",
        "response.output_item.done",
        "response.output_item.added",
        "response.function_call_arguments.delta",
        "response.function_call_arguments.done",
        "response.output_item.done",
        "response.completed",
    ]
    assert records[2]["item"]["id"] == records[3]["item_id"] == "rs_req_stream"
    assert records[8]["item"]["id"] == records[9]["item_id"] == "msg_req_stream"
    assert records[14]["item"]["id"] == records[15]["item_id"] == "call_weather"


def test_responses_completed_event_normalizes_chat_usage_for_strict_clients():
    request = CanonicalRequest("chat", "openai_responses", "stream-model", stream=True)
    upstream = CanonicalResponse(
        text="answer",
        usage={
            "prompt_tokens": 7,
            "prompt_tokens_details": {"cached_tokens": 2},
            "completion_tokens": 5,
            "completion_tokens_details": {"reasoning_tokens": 3},
            "total_tokens": 12,
        },
    )
    result = render_egress(request, upstream, "req_usage")
    assert isinstance(result, dict)
    assert result["usage"] == {
        "input_tokens": 7,
        "input_tokens_details": {"cached_tokens": 2},
        "output_tokens": 5,
        "output_tokens_details": {"reasoning_tokens": 3},
        "total_tokens": 12,
    }
    records = [
        json.loads(chunk.split("data: ", 1)[1])
        for chunk in render_sse(request, response_events(upstream, "req_usage", result))
    ]
    created = next(record for record in records if record["type"] == "response.created")
    in_progress = next(record for record in records if record["type"] == "response.in_progress")
    assert in_progress["response"]["created_at"] == created["response"]["created_at"]
    completed = next(record for record in records if record["type"] == "response.completed")
    assert completed["response"]["status"] == "completed"
    assert completed["response"]["usage"] == result["usage"]


def test_responses_completed_event_supplies_zero_usage_when_upstream_omits_it():
    request = CanonicalRequest("chat", "openai_responses", "stream-model", stream=True)
    result = render_egress(request, CanonicalResponse(text="answer"), "req_empty_usage")
    assert isinstance(result, dict)
    assert result["usage"]["input_tokens"] == result["usage"]["output_tokens"] == 0
    assert result["usage"]["total_tokens"] == 0


def test_responses_input_rejects_unconvertible_items(client):
    headers = _streaming_gateway(client)
    response = client.post("/v1/responses", headers=headers, json={"model": "stream-model", "input": [{"type": "computer_screenshot"}]})
    assert response.status_code == 400
    assert response.json()["error"]["stage"] == "protocol_conversion"
