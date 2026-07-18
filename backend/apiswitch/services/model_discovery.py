from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderConnection, ProviderModel, ProviderNode
from apiswitch.providers.base import ProviderError
from apiswitch.providers.factory import build_provider_adapter
from apiswitch.schemas.model_discovery import DiscoveredModel


def normalize_discovered_model(raw: dict) -> DiscoveredModel:
    capabilities = raw.get("capabilities") or raw.get("permission") or []
    if not isinstance(capabilities, list):
        capabilities = []
    return DiscoveredModel(
        id=str(raw.get("id") or raw.get("name") or raw.get("model") or "unknown"),
        owned_by=raw.get("owned_by") or raw.get("owner"),
        capabilities=[str(item) for item in capabilities],
    )


async def test_provider_connection(
    provider: Provider,
    connection: ProviderConnection | None = None,
    node: ProviderNode | None = None,
) -> str:
    adapter = build_provider_adapter(provider, connection=connection, node=node)
    models = await adapter.list_models()
    return f"Connection ok, discovered {len(models)} model(s)."


async def discover_provider_models(
    provider: Provider,
    connection: ProviderConnection | None = None,
    node: ProviderNode | None = None,
) -> list[DiscoveredModel]:
    adapter = build_provider_adapter(provider, connection=connection, node=node)
    models = await adapter.list_models()
    return [normalize_discovered_model(item) for item in models]


async def sync_provider_models(
    db: Session,
    provider: Provider,
    connection: ProviderConnection | None = None,
    node: ProviderNode | None = None,
) -> list[DiscoveredModel]:
    discovered = await discover_provider_models(provider, connection=connection, node=node)
    for item in discovered:
        existing = next((model for model in provider.models if model.model_name == item.id), None)
        if existing is None:
            db.add(
                ProviderModel(
                    provider_id=provider.id,
                    model_name=item.id,
                    capabilities_json={"capabilities": item.capabilities, "owned_by": item.owned_by},
                    enabled=True,
                )
            )
        else:
            existing.capabilities_json = {"capabilities": item.capabilities, "owned_by": item.owned_by}
            existing.enabled = True
    db.commit()
    return discovered


async def safe_test_provider_connection(
    provider: Provider,
    connection: ProviderConnection | None = None,
    node: ProviderNode | None = None,
) -> tuple[bool, str]:
    try:
        message = await test_provider_connection(provider, connection=connection, node=node)
        return True, message
    except ProviderError as exc:
        return False, str(exc)
