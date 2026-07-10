def test_provider_catalog_lists_implemented_and_planned_providers(client):
    response = client.get("/api/admin/provider-catalog")
    assert response.status_code == 200
    items = response.json()
    by_type = {item["type"]: item for item in items}

    assert by_type["openai"]["status"] == "implemented"
    assert by_type["gemini"]["auth_methods"] == ["api_key", "oauth"]
    assert by_type["openrouter"]["status"] == "planned"
    assert by_type["siliconflow"]["free_tier"] is True
    assert "embeddings" in by_type["cohere"]["protocols"]
    assert "rerank" in by_type["cohere"]["protocols"]


def test_provider_catalog_item_not_found(client):
    response = client.get("/api/admin/provider-catalog/missing-provider")
    assert response.status_code == 404
