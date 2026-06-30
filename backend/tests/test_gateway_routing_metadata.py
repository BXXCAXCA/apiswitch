def test_gateway_response_preserves_unified_model_and_tracks_upstream(client):
    response = client.post(
        "/v1/chat/completions",
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "code-best"
    assert body["apiswitch"]["provider"] == "mock-main"
    assert body["apiswitch"]["upstream_model"] == "mock-chat"
