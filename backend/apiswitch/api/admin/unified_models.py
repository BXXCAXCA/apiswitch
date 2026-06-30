from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Provider, UnifiedModel, UnifiedModelCandidate
from apiswitch.schemas.unified_models import UnifiedModelCreate, UnifiedModelRead

router = APIRouter(prefix="/api/admin/unified-models", tags=["Admin - Unified Models"])


def _capabilities(value: dict | None) -> list[str]:
    if not value:
        return []
    capabilities = value.get("capabilities", [])
    return capabilities if isinstance(capabilities, list) else []


def _to_read(db: Session, model: UnifiedModel) -> UnifiedModelRead:
    rows = db.execute(
        select(UnifiedModelCandidate, Provider)
        .join(Provider, Provider.id == UnifiedModelCandidate.provider_id)
        .where(UnifiedModelCandidate.unified_model_id == model.id)
        .order_by(UnifiedModelCandidate.manual_priority.desc())
    ).all()
    return UnifiedModelRead(
        id=model.id,
        name=model.name,
        description=model.description,
        enabled=model.enabled,
        capabilities=_capabilities(model.capabilities_json),
        candidates=[
            {
                "id": candidate.id,
                "provider": provider.name,
                "provider_type": provider.type,
                "upstream_model": candidate.upstream_model,
                "priority": candidate.manual_priority,
                "enabled": candidate.enabled,
            }
            for candidate, provider in rows
        ],
    )


@router.get("")
async def list_unified_models(db: Session = Depends(get_db)) -> list[UnifiedModelRead]:
    models = db.scalars(select(UnifiedModel).order_by(UnifiedModel.id)).all()
    return [_to_read(db, model) for model in models]


@router.post("")
async def create_unified_model(
    payload: UnifiedModelCreate,
    db: Session = Depends(get_db),
) -> UnifiedModelRead:
    model = UnifiedModel(
        name=payload.name,
        description=payload.description,
        enabled=payload.enabled,
        capabilities_json={"capabilities": payload.capabilities},
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _to_read(db, model)
