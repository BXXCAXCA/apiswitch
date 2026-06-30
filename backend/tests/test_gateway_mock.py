def test_chat_completions_mock(client):
    response = client.post(
        "/v1/chat/completions",
        json={"model": "code-best", "messages": [{"role": "user", "content": "hello"}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"]["content"] == "Mock response from APISwitch."


def test_models_mock(client):
    response = client.get("/v1/models")
    assert response.status_code == 200
    assert response.json()["object"] == "list"
