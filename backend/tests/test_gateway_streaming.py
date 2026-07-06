def test_chat_completions_streaming_mock(client, gateway_headers):
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers=gateway_headers,
        json={
            "model": "code-best",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())

    assert "data:" in body
    assert "chat.completion.chunk" in body
    assert '"model": "code-best"' in body
    assert '"upstream_model": "mock-chat"' in body
    assert "data: [DONE]" in body

    logs = client.get("/api/admin/logs").json()
    assert any(item["inbound_protocol"] == "openai_chat_stream" for item in logs["items"])


def test_streaming_unknown_unified_model_returns_error(client, gateway_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={
            "model": "missing-stream-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": True,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "unified_model_not_found"
