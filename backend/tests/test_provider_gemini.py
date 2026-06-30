from apiswitch.providers.gemini import GeminiProviderAdapter, _gemini_response_to_openai_chat


def test_gemini_static_model_discovery_without_key():
    adapter = GeminiProviderAdapter(
        base_url="https://generativelanguage.googleapis.com/v1beta",
        api_key=None,
    )
    # list_models is async, but this test keeps network-free validation simple through the public method contract.
    import asyncio

    models = asyncio.run(adapter.list_models())
    assert any(model["id"].startswith("gemini") for model in models)


def test_gemini_response_converts_to_openai_chat_completion():
    payload = {
        "candidates": [
            {
                "content": {"parts": [{"text": "hello from gemini"}]},
                "finishReason": "STOP",
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 2,
            "candidatesTokenCount": 3,
            "totalTokenCount": 5,
        },
    }
    response = _gemini_response_to_openai_chat(payload, "gemini-1.5-flash")
    assert response["object"] == "chat.completion"
    assert response["model"] == "gemini-1.5-flash"
    assert response["choices"][0]["message"]["content"] == "hello from gemini"
    assert response["choices"][0]["finish_reason"] == "stop"
    assert response["usage"]["total_tokens"] == 5


def test_gemini_provider_model_discovery_api(client):
    provider = client.post(
        "/api/admin/providers",
        json={
            "name": "gemini-no-key",
            "type": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "enabled": True,
            "timeout_seconds": 30,
        },
    ).json()

    discovered = client.post(f"/api/admin/providers/{provider['id']}/discover-models")
    assert discovered.status_code == 200
    assert any(model["id"].startswith("gemini") for model in discovered.json()["models"])
