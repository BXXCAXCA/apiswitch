from apiswitch.db.models import Provider
from apiswitch.providers.compatible import CompatibleProviderAdapter
from apiswitch.providers.factory import build_provider_adapter


def test_provider_catalog_lists_implemented_and_planned_providers(client):
    response = client.get("/api/admin/provider-catalog")
    assert response.status_code == 200
    items = response.json()
    by_type = {item["type"]: item for item in items}

    assert by_type["openai"]["status"] == "implemented"
    assert by_type["gemini"]["auth_methods"] == ["api_key", "oauth"]
    assert by_type["openrouter"]["status"] == "implemented"
    assert by_type["openrouter"]["adapter_mode"] == "openai_compatible"
    assert by_type["deepseek"]["status"] == "implemented"
    assert by_type["siliconflow"]["free_tier"] is True
    assert by_type["azure-openai"]["status"] == "planned"
    assert "embeddings" in by_type["cohere"]["protocols"]
    assert "rerank" in by_type["cohere"]["protocols"]


def test_catalog_compatible_provider_uses_compatible_adapter():
    provider = Provider(
        name="deepseek-main",
        type="deepseek",
        base_url="https://api.deepseek.com/v1",
        api_key_encrypted=None,
        enabled=True,
        timeout_seconds=30,
    )
    adapter = build_provider_adapter(provider)
    assert isinstance(adapter, CompatibleProviderAdapter)


def test_provider_catalog_item_not_found(client):
    response = client.get("/api/admin/provider-catalog/missing-provider")
    assert response.status_code == 404
