from uuid import uuid4


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
    assert "event: response.output_text.delta" in responses.text
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


def test_responses_input_rejects_unconvertible_items(client):
    headers = _streaming_gateway(client)
    response = client.post("/v1/responses", headers=headers, json={"model": "stream-model", "input": [{"type": "computer_screenshot"}]})
    assert response.status_code == 400
    assert response.json()["error"]["stage"] == "protocol_conversion"
