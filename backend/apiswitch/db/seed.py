from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderModel, UnifiedModel, UnifiedModelCandidate
from apiswitch.services.settings import seed_default_settings


def _seed_provider_model(
    db: Session,
    provider_id: int,
    model_name: str,
    capabilities: list[str],
) -> None:
    existing = db.scalar(
        select(ProviderModel).where(
            ProviderModel.provider_id == provider_id,
            ProviderModel.model_name == model_name,
        )
    )
    if existing is None:
        db.add(
            ProviderModel(
                provider_id=provider_id,
                model_name=model_name,
                capabilities_json={"capabilities": capabilities},
                enabled=True,
            )
        )
    else:
        known = set((existing.capabilities_json or {}).get("capabilities", []))
        expected = set(capabilities)
        if not expected.issubset(known):
            existing.capabilities_json = {"capabilities": sorted(known | expected)}


def _seed_unified_route(
    db: Session,
    provider_id: int,
    name: str,
    description: str,
    upstream_model: str,
    capabilities: list[str],
) -> None:
    unified_model = db.scalar(select(UnifiedModel).where(UnifiedModel.name == name))
    if unified_model is None:
        unified_model = UnifiedModel(
            name=name,
            description=description,
            enabled=True,
            capabilities_json={"capabilities": capabilities},
        )
        db.add(unified_model)
        db.flush()

    candidate = db.scalar(
        select(UnifiedModelCandidate).where(
            UnifiedModelCandidate.unified_model_id == unified_model.id,
            UnifiedModelCandidate.provider_id == provider_id,
            UnifiedModelCandidate.upstream_model == upstream_model,
        )
    )
    if candidate is None:
        db.add(
            UnifiedModelCandidate(
                unified_model_id=unified_model.id,
                provider_id=provider_id,
                upstream_model=upstream_model,
                manual_priority=100,
                enabled=True,
                capabilities_json={"capabilities": capabilities},
            )
        )
    else:
        existing = set((candidate.capabilities_json or {}).get("capabilities", []))
        expected = set(capabilities)
        if not expected.issubset(existing):
            candidate.capabilities_json = {"capabilities": sorted(existing | expected)}


def seed_default_data(db: Session) -> None:
    provider = db.scalar(select(Provider).where(Provider.name == "mock-main"))
    if provider is None:
        provider = Provider(
            name="mock-main",
            type="mock",
            base_url="mock://local",
            api_key_encrypted=None,
            enabled=True,
            timeout_seconds=120,
            proxy_type=None,
            proxy_url=None,
        )
        db.add(provider)
        db.flush()

    _seed_provider_model(db, provider.id, "mock-chat", ["text", "tools", "files", "images", "audio", "moderations", "rerank", "search", "video", "music"])
    _seed_provider_model(db, provider.id, "mock-embedding", ["embeddings"])
    _seed_unified_route(
        db,
        provider.id,
        name="code-best",
        description="Default mock coding route",
        upstream_model="mock-chat",
        capabilities=["text", "tools", "files", "images", "audio", "moderations", "rerank", "search", "video", "music"],
    )
    _seed_unified_route(
        db,
        provider.id,
        name="embedding-best",
        description="Default mock embedding route",
        upstream_model="mock-embedding",
        capabilities=["embeddings"],
    )

    db.commit()
    seed_default_settings(db)
