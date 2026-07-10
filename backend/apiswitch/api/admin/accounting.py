from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import ModelPricing, Provider, ProviderConnection, QuotaSnapshot, UsageHistory
from apiswitch.schemas.accounting import (
    ModelPricingCreate,
    ModelPricingRead,
    ModelPricingUpdate,
    QuotaSnapshotCreate,
    QuotaSnapshotRead,
    UsageHistoryRead,
    UsageSummary,
)

router = APIRouter(prefix="/api/admin/accounting", tags=["Admin - Accounting"])


def _get_pricing(db: Session, pricing_id: int) -> ModelPricing:
    item = db.get(ModelPricing, pricing_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model pricing not found")
    return item


def _validate_provider(db: Session, provider_id: int | None) -> None:
    if provider_id is not None and db.get(Provider, provider_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider not found")


def _pricing_read(item: ModelPricing) -> ModelPricingRead:
    return ModelPricingRead(
        id=item.id,
        provider_id=item.provider_id,
        model_name=item.model_name,
        input_cost_per_million=item.input_cost_per_million,
        output_cost_per_million=item.output_cost_per_million,
        cached_input_cost_per_million=item.cached_input_cost_per_million,
        currency=item.currency,
        effective_at=item.effective_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _quota_read(item: QuotaSnapshot) -> QuotaSnapshotRead:
    return QuotaSnapshotRead(
        id=item.id,
        provider_connection_id=item.provider_connection_id,
        captured_at=item.captured_at,
        remaining_requests=item.remaining_requests,
        remaining_tokens=item.remaining_tokens,
        remaining_credit=item.remaining_credit,
        reset_at=item.reset_at,
        raw=item.raw_json or {},
    )


def _usage_read(item: UsageHistory) -> UsageHistoryRead:
    return UsageHistoryRead(
        id=item.id,
        request_id=item.request_id,
        api_token_id=item.api_token_id,
        provider_connection_id=item.provider_connection_id,
        unified_model=item.unified_model,
        upstream_model=item.upstream_model,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        estimated_cost=item.estimated_cost,
        created_at=item.created_at,
    )


@router.get("/pricing")
async def list_model_pricing(
    provider_id: int | None = Query(default=None),
    model_name: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[ModelPricingRead]:
    statement = select(ModelPricing)
    if provider_id is not None:
        statement = statement.where(ModelPricing.provider_id == provider_id)
    if model_name:
        statement = statement.where(ModelPricing.model_name == model_name)
    items = db.scalars(statement.order_by(ModelPricing.model_name, ModelPricing.effective_at.desc())).all()
    return [_pricing_read(item) for item in items]


@router.post("/pricing")
async def create_model_pricing(
    payload: ModelPricingCreate,
    db: Session = Depends(get_db),
) -> ModelPricingRead:
    _validate_provider(db, payload.provider_id)
    item = ModelPricing(
        provider_id=payload.provider_id,
        model_name=payload.model_name,
        input_cost_per_million=payload.input_cost_per_million,
        output_cost_per_million=payload.output_cost_per_million,
        cached_input_cost_per_million=payload.cached_input_cost_per_million,
        currency=payload.currency,
        effective_at=payload.effective_at or datetime.utcnow(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _pricing_read(item)


@router.patch("/pricing/{pricing_id}")
async def update_model_pricing(
    pricing_id: int,
    payload: ModelPricingUpdate,
    db: Session = Depends(get_db),
) -> ModelPricingRead:
    item = _get_pricing(db, pricing_id)
    data = payload.model_dump(exclude_unset=True)
    if "provider_id" in data:
        _validate_provider(db, data["provider_id"])
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _pricing_read(item)


@router.delete("/pricing/{pricing_id}")
async def delete_model_pricing(pricing_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    item = _get_pricing(db, pricing_id)
    db.delete(item)
    db.commit()
    return {"deleted": True}


@router.get("/quota-snapshots")
async def list_quota_snapshots(
    provider_connection_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[QuotaSnapshotRead]:
    statement = select(QuotaSnapshot)
    if provider_connection_id is not None:
        statement = statement.where(QuotaSnapshot.provider_connection_id == provider_connection_id)
    items = db.scalars(statement.order_by(QuotaSnapshot.captured_at.desc()).limit(limit)).all()
    return [_quota_read(item) for item in items]


@router.post("/quota-snapshots")
async def create_quota_snapshot(
    payload: QuotaSnapshotCreate,
    db: Session = Depends(get_db),
) -> QuotaSnapshotRead:
    if db.get(ProviderConnection, payload.provider_connection_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Provider connection not found")
    item = QuotaSnapshot(
        provider_connection_id=payload.provider_connection_id,
        remaining_requests=payload.remaining_requests,
        remaining_tokens=payload.remaining_tokens,
        remaining_credit=payload.remaining_credit,
        reset_at=payload.reset_at,
        raw_json=payload.raw,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _quota_read(item)


@router.get("/usage")
async def list_usage_history(
    unified_model: str | None = Query(default=None),
    api_token_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[UsageHistoryRead]:
    statement = select(UsageHistory)
    if unified_model:
        statement = statement.where(UsageHistory.unified_model == unified_model)
    if api_token_id is not None:
        statement = statement.where(UsageHistory.api_token_id == api_token_id)
    items = db.scalars(statement.order_by(UsageHistory.created_at.desc()).limit(limit)).all()
    return [_usage_read(item) for item in items]


@router.get("/usage/summary")
async def get_usage_summary(
    unified_model: str | None = Query(default=None),
    api_token_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> UsageSummary:
    conditions = []
    if unified_model:
        conditions.append(UsageHistory.unified_model == unified_model)
    if api_token_id is not None:
        conditions.append(UsageHistory.api_token_id == api_token_id)

    statement = select(
        func.count(UsageHistory.id),
        func.coalesce(func.sum(UsageHistory.input_tokens), 0),
        func.coalesce(func.sum(UsageHistory.output_tokens), 0),
        func.coalesce(func.sum(UsageHistory.estimated_cost), 0.0),
        func.count(UsageHistory.estimated_cost),
    )
    if conditions:
        statement = statement.where(*conditions)
    request_count, input_tokens, output_tokens, estimated_cost, priced_request_count = db.execute(statement).one()
    return UsageSummary(
        request_count=int(request_count or 0),
        input_tokens=int(input_tokens or 0),
        output_tokens=int(output_tokens or 0),
        estimated_cost=float(estimated_cost or 0.0),
        priced_request_count=int(priced_request_count or 0),
    )
