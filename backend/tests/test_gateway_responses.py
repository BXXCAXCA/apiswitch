def test_responses_routes_through_gateway(client):
    response = client.post(
        "/v1/responses",
        json={"model": "code-best", "input": "hello"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "response"
    assert body["model"] == "code-best"
    assert body["status"] == "completed"
    assert body["output"][0]["type"] == "message"
    assert body["output"][0]["content"][0]["type"] == "output_text"
    assert body["output"][0]["content"][0]["text"] == "Mock response from APISwitch."
    assert body["apiswitch"]["upstream_model"] == "mock-chat"
    assert body["apiswitch"]["inbound_protocol"] == "openai_responses"

    logs = client.get("/api/admin/logs").json()
    assert any(item["inbound_protocol"] == "openai_responses" for item in logs["items"])


def test_responses_input_message_list(client):
    response = client.post(
        "/v1/responses",
        json={
            "model": "code-best",
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "hello from responses"}],
                }
            ],
        },
    )
    assert response.status_code == 200
    assert response.json()["model"] == "code-best"


def test_responses_unknown_model_returns_error(client):
    response = client.post(
        "/v1/responses",
        json={"model": "missing-response-model", "input": "hello"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["type"] == "unified_model_not_found"


def test_responses_streaming_not_implemented(client):
    response = client.post(
        "/v1/responses",
        json={"model": "code-best", "input": "hello", "stream": True},
    )
    assert response.status_code == 502
    assert response.json()["detail"]["type"] == "responses_streaming_not_implemented"
