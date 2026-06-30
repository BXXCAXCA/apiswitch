from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Provider
from apiswitch.schemas.providers import ProviderCreate, ProviderRead

router = APIRouter(prefix="/api/admin/providers", tags=["Admin - Providers"])


def _to_read(provider: Provider) -> ProviderRead:
    return ProviderRead(
        id=provider.id,
        name=provider.name,
        type=provider.type,
        base_url=provider.base_url,
        enabled=provider.enabled,
        timeout_seconds=provider.timeout_seconds,
        proxy_type=provider.proxy_type,
        proxy_url=provider.proxy_url,
    )


@router.get("")
async def list_providers(db: Session = Depends(get_db)) -> list[ProviderRead]:
    providers = db.scalars(select(Provider).order_by(Provider.id)).all()
    return [_to_read(provider) for provider in providers]


@router.post("")
async def create_provider(payload: ProviderCreate, db: Session = Depends(get_db)) -> ProviderRead:
    provider = Provider(
        name=payload.name,
        type=payload.type,
        base_url=payload.base_url,
        enabled=payload.enabled,
        timeout_seconds=payload.timeout_seconds,
        proxy_type=payload.proxy_type,
        proxy_url=payload.proxy_url,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    return _to_read(provider)
