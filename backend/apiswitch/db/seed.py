from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderModel, UnifiedModel, UnifiedModelCandidate
from apiswitch.services.settings import seed_default_settings


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

    existing_model = db.scalar(
        select(ProviderModel).where(
            ProviderModel.provider_id == provider.id,
            ProviderModel.model_name == "mock-chat",
        )
    )
    if existing_model is None:
        db.add(
            ProviderModel(
                provider_id=provider.id,
                model_name="mock-chat",
                capabilities_json={"capabilities": ["text", "tools", "files"]},
                enabled=True,
            )
        )

    unified_model = db.scalar(select(UnifiedModel).where(UnifiedModel.name == "code-best"))
    if unified_model is None:
        unified_model = UnifiedModel(
            name="code-best",
            description="Default mock coding route",
            enabled=True,
            capabilities_json={"capabilities": ["text", "tools", "files"]},
        )
        db.add(unified_model)
        db.flush()

    candidate = db.scalar(
        select(UnifiedModelCandidate).where(
            UnifiedModelCandidate.unified_model_id == unified_model.id,
            UnifiedModelCandidate.provider_id == provider.id,
            UnifiedModelCandidate.upstream_model == "mock-chat",
        )
    )
    if candidate is None:
        db.add(
            UnifiedModelCandidate(
                unified_model_id=unified_model.id,
                provider_id=provider.id,
                upstream_model="mock-chat",
                manual_priority=100,
                enabled=True,
                capabilities_json={"capabilities": ["text", "tools", "files"]},
            )
        )

    db.commit()
    seed_default_settings(db)
