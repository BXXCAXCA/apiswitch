def test_chat_completions_mock(client, gateway_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Mock response from APISwitch."
    assert body["apiswitch"]["provider"] == "mock-main"
    assert body["apiswitch"]["candidate_id"] >= 1
    assert body["apiswitch"]["retry_chain"][0]["success"] is True

    logs = client.get("/api/admin/logs").json()
    assert logs["total"] >= 1
    assert any(item["unified_model"] == "code-best" for item in logs["items"])


def test_unknown_unified_model_returns_error(client, gateway_headers):
    response = client.post(
        "/v1/chat/completions",
        headers=gateway_headers,
        json={"model": "missing-model", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "unified_model_not_found"


def test_models_mock(client, gateway_headers):
    response = client.get("/v1/models", headers=gateway_headers)
    assert response.status_code == 200
    assert response.json()["object"] == "list"
