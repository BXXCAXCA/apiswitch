def test_gemini_v1beta_generate_content_routes_unified_model(client, gateway_headers):
    response = client.post(
        "/v1beta/models/code-best:generateContent",
        headers={**gateway_headers, "X-APISwitch-Tier": "quality"},
        json={
            "systemInstruction": {"parts": [{"text": "You are helpful."}]},
            "contents": [
                {"role": "user", "parts": [{"text": "hello"}]},
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 128,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["modelVersion"] == "code-best"
    assert body["candidates"][0]["content"]["role"] == "model"
    assert body["candidates"][0]["content"]["parts"][0]["text"] == "Mock response from APISwitch."
    assert body["usageMetadata"]["totalTokenCount"] == 2
    assert body["apiswitch"]["upstream_model"] == "mock-chat"
    assert body["apiswitch"]["request_controls"]["tier"] == "quality"

    logs = client.get("/api/admin/logs").json()["items"]
    assert any(item["inbound_protocol"] == "gemini_v1beta" for item in logs)


def test_gemini_v1beta_requires_token(client):
    response = client.post(
        "/v1beta/models/code-best:generateContent",
        json={"contents": [{"role": "user", "parts": [{"text": "hello"}]}]},
    )
    assert response.status_code == 401
