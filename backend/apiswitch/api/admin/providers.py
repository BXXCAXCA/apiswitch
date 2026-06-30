from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Provider, UnifiedModelCandidate
from apiswitch.schemas.providers import ProviderCreate, ProviderRead, ProviderUpdate

router = APIRouter(prefix="/api/admin/providers", tags=["Admin - Providers"])


def _get_provider(db: Session, provider_id: int) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider


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


@router.get("/{provider_id}")
async def get_provider(provider_id: int, db: Session = Depends(get_db)) -> ProviderRead:
    return _to_read(_get_provider(db, provider_id))


@router.patch("/{provider_id}")
async def update_provider(
    provider_id: int,
    payload: ProviderUpdate,
    db: Session = Depends(get_db),
) -> ProviderRead:
    provider = _get_provider(db, provider_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(provider, key, value)
    db.commit()
    db.refresh(provider)
    return _to_read(provider)


@router.delete("/{provider_id}")
async def delete_provider(provider_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    provider = _get_provider(db, provider_id)
    candidate = db.scalar(
        select(UnifiedModelCandidate).where(UnifiedModelCandidate.provider_id == provider_id).limit(1)
    )
    if candidate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider is still used by unified model candidates",
        )
    db.delete(provider)
    db.commit()
    return {"deleted": True}
