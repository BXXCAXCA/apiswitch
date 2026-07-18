from sqlalchemy import case, select
from sqlalchemy.orm import Session

from apiswitch.db.models import ModelPricing, UsageHistory
from apiswitch.services.budget_enforcement import accumulate_budget_spend


def _find_pricing(db: Session, provider_id: int, model_name: str) -> ModelPricing | None:
    pricing = db.scalar(
        select(ModelPricing)
        .where(
            ModelPricing.provider_id == provider_id,
            ModelPricing.model_name == model_name,
        )
        .order_by(
            case((ModelPricing.source == "manual", 1), else_=0).desc(),
            ModelPricing.effective_at.desc(),
            ModelPricing.id.desc(),
        )
        .limit(1)
    )
    if pricing is not None:
        return pricing
    return db.scalar(
        select(ModelPricing)
        .where(
            ModelPricing.provider_id.is_(None),
            ModelPricing.model_name == model_name,
        )
        .order_by(
            case((ModelPricing.source == "manual", 1), else_=0).desc(),
            ModelPricing.effective_at.desc(),
            ModelPricing.id.desc(),
        )
        .limit(1)
    )


def estimate_request_cost(
    db: Session,
    provider_id: int,
    model_name: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    pricing = _find_pricing(db, provider_id, model_name)
    if pricing is None:
        return None
    input_cost = None
    output_cost = None
    if input_tokens is not None and pricing.input_cost_per_million is not None:
        input_cost = input_tokens * pricing.input_cost_per_million / 1_000_000
    if output_tokens is not None and pricing.output_cost_per_million is not None:
        output_cost = output_tokens * pricing.output_cost_per_million / 1_000_000
    if input_cost is None and output_cost is None:
        return None
    return round((input_cost or 0.0) + (output_cost or 0.0), 10)


def record_usage_history(
    db: Session,
    *,
    request_id: str,
    api_token_id: int | None,
    provider_connection_id: int | None,
    provider_id: int,
    unified_model: str,
    upstream_model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> tuple[UsageHistory, float | None]:
    estimated_cost = estimate_request_cost(
        db,
        provider_id=provider_id,
        model_name=upstream_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    item = UsageHistory(
        request_id=request_id,
        api_token_id=api_token_id,
        provider_connection_id=provider_connection_id,
        unified_model=unified_model,
        upstream_model=upstream_model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
    )
    db.add(item)
    accumulate_budget_spend(
        db,
        estimated_cost=estimated_cost,
        api_token_id=api_token_id,
        provider_id=provider_id,
        unified_model=unified_model,
    )
    return item, estimated_cost
