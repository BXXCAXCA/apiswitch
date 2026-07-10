def test_embeddings_routes_through_unified_model(client, gateway_headers):
    response = client.post(
        "/v1/embeddings",
        headers={**gateway_headers, "X-APISwitch-Tier": "quality"},
        json={
            "model": "embedding-best",
            "input": ["hello", "world"],
            "dimensions": 6,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "list"
    assert body["model"] == "embedding-best"
    assert len(body["data"]) == 2
    assert len(body["data"][0]["embedding"]) == 6
    assert body["apiswitch"]["upstream_model"] == "mock-embedding"
    assert body["apiswitch"]["request_controls"]["tier"] == "quality"

    logs = client.get("/api/admin/logs").json()["items"]
    assert any(item["inbound_protocol"] == "openai_embeddings" for item in logs)

    usage = client.get("/api/admin/accounting/usage", params={"unified_model": "embedding-best"})
    assert usage.status_code == 200
    assert usage.json()[0]["input_tokens"] >= 1
    assert usage.json()[0]["output_tokens"] == 0


def test_embeddings_base64_format(client, gateway_headers):
    response = client.post(
        "/v1/embeddings",
        headers=gateway_headers,
        json={
            "model": "embedding-best",
            "input": "hello",
            "dimensions": 4,
            "encoding_format": "base64",
        },
    )
    assert response.status_code == 200
    assert isinstance(response.json()["data"][0]["embedding"], str)


def test_embeddings_requires_gateway_token(client):
    response = client.post(
        "/v1/embeddings",
        json={"model": "embedding-best", "input": "hello"},
    )
    assert response.status_code == 401
