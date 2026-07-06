def test_anthropic_messages_mock_route(client, gateway_headers):
    response = client.post(
        "/v1/messages",
        headers=gateway_headers,
        json={
            "model": "code-best",
            "max_tokens": 128,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "message"
    assert body["model"] == "code-best"
    assert body["content"][0]["text"] == "Mock response from APISwitch Messages."
    assert body["apiswitch"]["provider"] == "mock-main"
    assert body["apiswitch"]["upstream_model"] == "mock-chat"

    logs = client.get("/api/admin/logs").json()
    assert any(item["inbound_protocol"] == "anthropic_messages" for item in logs["items"])


def test_anthropic_provider_without_key_reports_connection_failure(client):
    provider = client.post(
        "/api/admin/providers",
        json={
            "name": "anthropic-no-key",
            "type": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "enabled": True,
            "timeout_seconds": 30,
        },
    ).json()

    tested = client.post(f"/api/admin/providers/{provider['id']}/test")
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    discovered = client.post(f"/api/admin/providers/{provider['id']}/discover-models")
    assert discovered.status_code == 200
    assert any(model["id"].startswith("claude") for model in discovered.json()["models"])
