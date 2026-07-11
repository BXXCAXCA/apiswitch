from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Provider, ProviderConnection, ProviderNode, UnifiedModel, UnifiedModelCandidate
from apiswitch.schemas.unified_models import (
    UnifiedModelCandidateCreate,
    UnifiedModelCandidateRead,
    UnifiedModelCandidateUpdate,
    UnifiedModelCreate,
    UnifiedModelRead,
    UnifiedModelUpdate,
)

router = APIRouter(prefix="/api/admin/unified-models", tags=["Admin - Unified Models"])


def _capabilities(value: dict | None) -> list[str]:
    if not value:
        return []
    capabilities = value.get("capabilities", [])
    return capabilities if isinstance(capabilities, list) else []


def _routing(value: dict | None) -> dict:
    config = (value or {}).get("routing", {})
    return config if isinstance(config, dict) else {}


def _model_config(payload: UnifiedModelCreate | UnifiedModelUpdate, existing: dict | None = None) -> dict:
    """Keep capabilities and routing configuration together in the stable JSON column."""
    result = dict(existing or {})
    data = payload.model_dump(exclude_unset=True)
    if "capabilities" in data:
        result["capabilities"] = data["capabilities"]
    routing = dict(_routing(result))
    for key in ("routing_mode", "combo_strategy", "category", "preferred_tier", "max_request_cost", "min_context_window", "session_affinity_enabled"):
        if key in data:
            routing[key] = data[key]
    if isinstance(payload, UnifiedModelCreate):
        routing.setdefault("routing_mode", payload.routing_mode)
        routing.setdefault("combo_strategy", payload.combo_strategy)
        routing.setdefault("category", payload.category)
        routing.setdefault("preferred_tier", payload.preferred_tier)
        routing.setdefault("max_request_cost", payload.max_request_cost)
        routing.setdefault("min_context_window", payload.min_context_window)
        routing.setdefault("session_affinity_enabled", payload.session_affinity_enabled)
    result["routing"] = routing
    return result


def _get_unified_model(db: Session, model_id: int) -> UnifiedModel:
    model = db.get(UnifiedModel, model_id)
    if model is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unified model not found")
    return model


def _get_provider(db: Session, provider_id: int) -> Provider:
    provider = db.get(Provider, provider_id)
    if provider is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")
    return provider


def _get_candidate(db: Session, candidate_id: int) -> UnifiedModelCandidate:
    candidate = db.get(UnifiedModelCandidate, candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return candidate


def _validate_route_target(
    db: Session,
    provider_id: int,
    connection_id: int | None,
    node_id: int | None,
) -> None:
    connection = db.get(ProviderConnection, connection_id) if connection_id is not None else None
    node = db.get(ProviderNode, node_id) if node_id is not None else None
    if connection_id is not None and connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider connection not found")
    if node_id is not None and node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider node not found")
    if connection is not None and connection.provider_id != provider_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Connection belongs to another provider")
    if node is not None:
        if node.provider_id != provider_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Node belongs to another provider")
        if node.connection_id is not None and connection_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A node-bound candidate must select the node's connection",
            )
        if connection_id is not None and node.connection_id != connection_id:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Node is not attached to the selected connection")


def _find_duplicate_candidate(
    db: Session,
    model_id: int,
    provider_id: int,
    upstream_model: str,
    connection_id: int | None,
    node_id: int | None,
    exclude_candidate_id: int | None = None,
) -> UnifiedModelCandidate | None:
    statement = select(UnifiedModelCandidate).where(
        UnifiedModelCandidate.unified_model_id == model_id,
        UnifiedModelCandidate.provider_id == provider_id,
        UnifiedModelCandidate.upstream_model == upstream_model,
        UnifiedModelCandidate.provider_connection_id == connection_id,
        UnifiedModelCandidate.provider_node_id == node_id,
    )
    if exclude_candidate_id is not None:
        statement = statement.where(UnifiedModelCandidate.id != exclude_candidate_id)
    return db.scalar(statement.limit(1))


def _reject_duplicate_candidate(
    db: Session,
    model_id: int,
    provider_id: int,
    upstream_model: str,
    connection_id: int | None,
    node_id: int | None,
    exclude_candidate_id: int | None = None,
) -> None:
    duplicate = _find_duplicate_candidate(db, model_id, provider_id, upstream_model, connection_id, node_id, exclude_candidate_id)
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate already exists for this unified model, provider, and upstream model",
        )


def _candidate_to_read(candidate: UnifiedModelCandidate, provider: Provider) -> UnifiedModelCandidateRead:
    return UnifiedModelCandidateRead(
        id=candidate.id,
        unified_model_id=candidate.unified_model_id,
        provider_id=provider.id,
        provider_name=provider.name,
        provider_type=provider.type,
        provider_connection_id=candidate.provider_connection_id,
        provider_node_id=candidate.provider_node_id,
        upstream_model=candidate.upstream_model,
        manual_priority=candidate.manual_priority,
        enabled=candidate.enabled,
        capabilities=_capabilities(candidate.capabilities_json),
    )


def _to_read(db: Session, model: UnifiedModel) -> UnifiedModelRead:
    rows = db.execute(
        select(UnifiedModelCandidate, Provider)
        .join(Provider, Provider.id == UnifiedModelCandidate.provider_id)
        .where(UnifiedModelCandidate.unified_model_id == model.id)
        .order_by(UnifiedModelCandidate.manual_priority.desc())
    ).all()
    routing = _routing(model.capabilities_json)
    return UnifiedModelRead(
        id=model.id,
        name=model.name,
        description=model.description,
        enabled=model.enabled,
        capabilities=_capabilities(model.capabilities_json),
        routing_mode=routing.get("routing_mode", "static"),
        combo_strategy=routing.get("combo_strategy", "priority"),
        category=routing.get("category"),
        preferred_tier=routing.get("preferred_tier", "balanced"),
        max_request_cost=routing.get("max_request_cost"),
        min_context_window=routing.get("min_context_window"),
        session_affinity_enabled=routing.get("session_affinity_enabled", True),
        candidates=[
            _candidate_to_read(candidate, provider).model_dump()
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
        capabilities_json=_model_config(payload),
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return _to_read(db, model)


@router.get("/{model_id}")
async def get_unified_model(model_id: int, db: Session = Depends(get_db)) -> UnifiedModelRead:
    return _to_read(db, _get_unified_model(db, model_id))


@router.patch("/{model_id}")
async def update_unified_model(
    model_id: int,
    payload: UnifiedModelUpdate,
    db: Session = Depends(get_db),
) -> UnifiedModelRead:
    model = _get_unified_model(db, model_id)
    data = payload.model_dump(exclude_unset=True)
    routing_keys = {"routing_mode", "combo_strategy", "category", "preferred_tier", "max_request_cost", "min_context_window", "session_affinity_enabled"}
    if "capabilities" in data or routing_keys & data.keys():
        model.capabilities_json = _model_config(payload, model.capabilities_json)
        data.pop("capabilities", None)
        for key in routing_keys:
            data.pop(key, None)
    for key, value in data.items():
        setattr(model, key, value)
    db.commit()
    db.refresh(model)
    return _to_read(db, model)


@router.delete("/{model_id}")
async def delete_unified_model(model_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    model = _get_unified_model(db, model_id)
    candidates = db.scalars(
        select(UnifiedModelCandidate).where(UnifiedModelCandidate.unified_model_id == model_id)
    ).all()
    for candidate in candidates:
        db.delete(candidate)
    db.delete(model)
    db.commit()
    return {"deleted": True}


@router.get("/{model_id}/candidates")
async def list_candidates(
    model_id: int,
    db: Session = Depends(get_db),
) -> list[UnifiedModelCandidateRead]:
    _get_unified_model(db, model_id)
    rows = db.execute(
        select(UnifiedModelCandidate, Provider)
        .join(Provider, Provider.id == UnifiedModelCandidate.provider_id)
        .where(UnifiedModelCandidate.unified_model_id == model_id)
        .order_by(UnifiedModelCandidate.manual_priority.desc())
    ).all()
    return [_candidate_to_read(candidate, provider) for candidate, provider in rows]


@router.post("/{model_id}/candidates")
async def create_candidate(
    model_id: int,
    payload: UnifiedModelCandidateCreate,
    db: Session = Depends(get_db),
) -> UnifiedModelCandidateRead:
    _get_unified_model(db, model_id)
    provider = _get_provider(db, payload.provider_id)
    _validate_route_target(db, payload.provider_id, payload.provider_connection_id, payload.provider_node_id)
    _reject_duplicate_candidate(db, model_id, payload.provider_id, payload.upstream_model, payload.provider_connection_id, payload.provider_node_id)
    candidate = UnifiedModelCandidate(
        unified_model_id=model_id,
        provider_id=payload.provider_id,
        provider_connection_id=payload.provider_connection_id,
        provider_node_id=payload.provider_node_id,
        upstream_model=payload.upstream_model,
        manual_priority=payload.manual_priority,
        enabled=payload.enabled,
        capabilities_json={"capabilities": payload.capabilities},
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return _candidate_to_read(candidate, provider)


@router.patch("/{model_id}/candidates/{candidate_id}")
async def update_candidate(
    model_id: int,
    candidate_id: int,
    payload: UnifiedModelCandidateUpdate,
    db: Session = Depends(get_db),
) -> UnifiedModelCandidateRead:
    _get_unified_model(db, model_id)
    candidate = _get_candidate(db, candidate_id)
    if candidate.unified_model_id != model_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    data = payload.model_dump(exclude_unset=True)
    next_provider_id = data.get("provider_id", candidate.provider_id)
    next_upstream_model = data.get("upstream_model", candidate.upstream_model)
    next_connection_id = data.get("provider_connection_id", candidate.provider_connection_id)
    next_node_id = data.get("provider_node_id", candidate.provider_node_id)
    if "provider_id" in data:
        _get_provider(db, data["provider_id"])
    _validate_route_target(db, next_provider_id, next_connection_id, next_node_id)
    _reject_duplicate_candidate(db, model_id, next_provider_id, next_upstream_model, next_connection_id, next_node_id, exclude_candidate_id=candidate_id)
    if "capabilities" in data:
        candidate.capabilities_json = {"capabilities": data.pop("capabilities")}
    for key, value in data.items():
        setattr(candidate, key, value)
    db.commit()
    db.refresh(candidate)
    provider = _get_provider(db, candidate.provider_id)
    return _candidate_to_read(candidate, provider)


@router.delete("/{model_id}/candidates/{candidate_id}")
async def delete_candidate(
    model_id: int,
    candidate_id: int,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    _get_unified_model(db, model_id)
    candidate = _get_candidate(db, candidate_id)
    if candidate.unified_model_id != model_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"deleted": True}
