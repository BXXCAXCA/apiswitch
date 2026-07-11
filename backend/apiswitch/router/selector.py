import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import (
    ModelPricing,
    Provider,
    ProviderConnection,
    ProviderHealth,
    ProviderNode,
    QuotaSnapshot,
    UnifiedModel,
    UnifiedModelCandidate,
)
from apiswitch.gateway.errors import NoAvailableCandidateError, UnifiedModelNotFoundError
from apiswitch.providers.catalog import get_provider_catalog_item
from apiswitch.router.circuit_breaker import is_candidate_allowed
from apiswitch.router.auto_combo import materialize_auto_candidates
from apiswitch.router.scoring import CandidateScoreInput, calculate_score_details, get_tier_score_weights
from apiswitch.services.session_affinity import get_affinity_candidate_id


@dataclass(frozen=True)
class SelectedCandidate:
    candidate_id: int
    provider_id: int
    provider_name: str
    provider_type: str
    provider_connection_id: int | None
    provider_node_id: int | None
    upstream_model: str
    score: float
    score_breakdown: dict[str, object]
    estimated_request_cost: float | None = None


@dataclass
class _CandidateMetrics:
    candidate: UnifiedModelCandidate
    provider: Provider
    connection: ProviderConnection | None
    node: ProviderNode | None
    health: ProviderHealth | None
    stability: float
    speed: float
    health_score: float
    quota_score: float
    blended_price: float | None
    estimated_request_cost: float | None
    task_fit_score: float
    context_fit_score: float
    failure_penalty: float


def _latest_pricing(db: Session, provider_id: int, model_name: str) -> ModelPricing | None:
    item = db.scalar(
        select(ModelPricing)
        .where(ModelPricing.provider_id == provider_id, ModelPricing.model_name == model_name)
        .order_by(ModelPricing.effective_at.desc(), ModelPricing.id.desc())
        .limit(1)
    )
    if item is not None:
        return item
    return db.scalar(
        select(ModelPricing)
        .where(ModelPricing.provider_id.is_(None), ModelPricing.model_name == model_name)
        .order_by(ModelPricing.effective_at.desc(), ModelPricing.id.desc())
        .limit(1)
    )


def _blended_price(pricing: ModelPricing | None) -> float | None:
    if pricing is None:
        return None
    input_price = pricing.input_cost_per_million
    output_price = pricing.output_cost_per_million
    if input_price is None and output_price is None:
        return None
    if input_price is None:
        return float(output_price or 0.0)
    if output_price is None:
        return float(input_price)
    return float(input_price) * 0.6 + float(output_price) * 0.4


def _estimate_cost(
    pricing: ModelPricing | None,
    estimated_input_tokens: int | None,
    estimated_output_tokens: int | None,
) -> float | None:
    if pricing is None:
        return None
    input_cost = None
    output_cost = None
    if estimated_input_tokens is not None and pricing.input_cost_per_million is not None:
        input_cost = estimated_input_tokens * pricing.input_cost_per_million / 1_000_000
    if estimated_output_tokens is not None and pricing.output_cost_per_million is not None:
        output_cost = estimated_output_tokens * pricing.output_cost_per_million / 1_000_000
    if input_cost is None and output_cost is None:
        return None
    return round((input_cost or 0.0) + (output_cost or 0.0), 10)


def _latest_quota_score(db: Session, provider_id: int, connection_id: int | None = None) -> float:
    snapshot = db.scalar(
        select(QuotaSnapshot)
        .join(ProviderConnection, ProviderConnection.id == QuotaSnapshot.provider_connection_id)
        .where(ProviderConnection.provider_id == provider_id, ProviderConnection.enabled.is_(True))
        .order_by(QuotaSnapshot.captured_at.desc(), QuotaSnapshot.id.desc())
        .limit(1)
    )
    if connection_id is not None:
        snapshot = db.scalar(
            select(QuotaSnapshot)
            .where(QuotaSnapshot.provider_connection_id == connection_id)
            .order_by(QuotaSnapshot.captured_at.desc(), QuotaSnapshot.id.desc())
            .limit(1)
        )
    if snapshot is None:
        return 50.0

    values = [snapshot.remaining_requests, snapshot.remaining_tokens, snapshot.remaining_credit]
    known = [value for value in values if value is not None]
    if known and all(float(value) <= 0 for value in known):
        return 0.0

    scores: list[float] = []
    if snapshot.remaining_requests is not None and snapshot.remaining_requests > 0:
        scores.append(min(100.0, 50.0 + math.log10(1 + snapshot.remaining_requests) * 10.0))
    if snapshot.remaining_tokens is not None and snapshot.remaining_tokens > 0:
        scores.append(min(100.0, 50.0 + math.log10(1 + snapshot.remaining_tokens / 1000) * 10.0))
    if snapshot.remaining_credit is not None and snapshot.remaining_credit > 0:
        scores.append(min(100.0, 50.0 + math.log10(1 + snapshot.remaining_credit) * 15.0))
    return max(scores) if scores else 50.0


def _task_fit(unified_model: UnifiedModel, candidate: UnifiedModelCandidate) -> float:
    required = set((unified_model.capabilities_json or {}).get("capabilities", []))
    available = set((candidate.capabilities_json or {}).get("capabilities", []))
    if not required:
        return 50.0
    if not available:
        return 25.0
    return min(100.0, len(required & available) / len(required) * 100.0)


def _context_fit(unified_model: UnifiedModel, candidate: UnifiedModelCandidate) -> float:
    required = (unified_model.capabilities_json or {}).get("min_context_window")
    available = (candidate.capabilities_json or {}).get("context_window")
    if required is None or available is None:
        return 50.0
    if float(available) >= float(required):
        return 100.0
    if float(required) <= 0:
        return 50.0
    return max(0.0, min(100.0, float(available) / float(required) * 100.0))


def _cost_score(value: float | None, known_values: list[float]) -> float:
    if value is None:
        return 50.0
    if value <= 0:
        return 100.0
    if len(known_values) <= 1:
        return 75.0
    minimum = min(known_values)
    maximum = max(known_values)
    if abs(maximum - minimum) < 0.000000001:
        return 75.0
    return max(0.0, min(100.0, 100.0 - ((value - minimum) / (maximum - minimum) * 100.0)))


def list_ranked_candidates(
    db: Session,
    unified_model_name: str,
    *,
    session_key: str | None = None,
    tier: str | None = None,
    max_cost: float | None = None,
    estimated_input_tokens: int | None = None,
    estimated_output_tokens: int | None = None,
) -> list[SelectedCandidate]:
    unified_model = db.scalar(
        select(UnifiedModel).where(
            UnifiedModel.name == unified_model_name,
            UnifiedModel.enabled.is_(True),
        )
    )
    if unified_model is None:
        raise UnifiedModelNotFoundError(f"Unified model not found: {unified_model_name}")

    materialize_auto_candidates(db, unified_model)

    normalized_tier, score_weights = get_tier_score_weights(tier)
    affinity_candidate_id = get_affinity_candidate_id(db, unified_model, session_key)

    rows = db.execute(
        select(UnifiedModelCandidate, Provider, ProviderHealth)
        .join(Provider, Provider.id == UnifiedModelCandidate.provider_id)
        .outerjoin(ProviderHealth, ProviderHealth.candidate_id == UnifiedModelCandidate.id)
        .where(
            UnifiedModelCandidate.unified_model_id == unified_model.id,
            UnifiedModelCandidate.enabled.is_(True),
            Provider.enabled.is_(True),
        )
    ).all()

    if not rows:
        raise NoAvailableCandidateError(f"No enabled candidates for unified model: {unified_model_name}")

    metrics: list[_CandidateMetrics] = []
    blocked_count = 0
    budget_filtered_count = 0
    tier_filtered_count = 0
    for candidate, provider, health in rows:
        if not is_candidate_allowed(db, candidate.id):
            blocked_count += 1
            continue

        connection = (
            db.get(ProviderConnection, candidate.provider_connection_id)
            if candidate.provider_connection_id is not None
            else None
        )
        node = db.get(ProviderNode, candidate.provider_node_id) if candidate.provider_node_id is not None else None
        if connection is not None:
            if connection.provider_id != provider.id or not connection.enabled:
                continue
            if connection.expires_at is not None and connection.expires_at <= datetime.utcnow():
                continue
        if node is not None:
            if node.provider_id != provider.id or not node.enabled:
                continue
            if node.connection_id is not None and (connection is None or node.connection_id != connection.id):
                continue

        pricing = _latest_pricing(db, provider.id, candidate.upstream_model)
        blended_price = _blended_price(pricing)
        estimated_cost = _estimate_cost(pricing, estimated_input_tokens, estimated_output_tokens)
        if max_cost is not None and (estimated_cost is None or estimated_cost > max_cost):
            budget_filtered_count += 1
            continue

        if normalized_tier == "free":
            catalog_item = get_provider_catalog_item(provider.type)
            has_free_tier = bool(catalog_item and catalog_item.get("free_tier"))
            if not has_free_tier and (blended_price is None or blended_price > 0):
                tier_filtered_count += 1
                continue

        success_count = health.success_count if health else 0
        failure_count = health.failure_count if health else 0
        total_count = success_count + failure_count
        stability = 100.0 if total_count == 0 else (success_count / total_count) * 100.0
        avg_latency = health.avg_latency_ms if health and health.avg_latency_ms else 1000.0
        speed = max(0.0, min(100.0, 100.0 - (avg_latency / 50.0)))
        consecutive_failures = health.consecutive_failures if health else 0
        metrics.append(
            _CandidateMetrics(
                candidate=candidate,
                provider=provider,
                connection=connection,
                node=node,
                health=health,
                stability=stability,
                speed=speed,
                health_score=max(0.0, stability - consecutive_failures * 10.0),
                quota_score=_latest_quota_score(db, provider.id, connection.id if connection else None),
                blended_price=blended_price,
                estimated_request_cost=estimated_cost,
                task_fit_score=_task_fit(unified_model, candidate),
                context_fit_score=_context_fit(unified_model, candidate),
                failure_penalty=float(consecutive_failures * 5),
            )
        )

    known_prices = [item.blended_price for item in metrics if item.blended_price is not None]
    scored: list[tuple[bool, SelectedCandidate]] = []
    for item in metrics:
        result = calculate_score_details(
            CandidateScoreInput(
                stability_score=item.stability,
                speed_score=item.speed,
                health_score=item.health_score,
                quota_score=item.quota_score,
                cost_score=_cost_score(item.blended_price, known_prices),
                latency_score=item.speed,
                task_fit_score=item.task_fit_score,
                context_fit_score=item.context_fit_score,
                manual_priority_score=float(item.candidate.manual_priority),
                failure_penalty=item.failure_penalty,
                budget_penalty=0.0,
            ),
            weights=score_weights,
        )
        affinity_match = affinity_candidate_id == item.candidate.id
        selected = SelectedCandidate(
            candidate_id=item.candidate.id,
            provider_id=item.provider.id,
            provider_name=item.provider.name,
            provider_type=item.provider.type,
            provider_connection_id=item.connection.id if item.connection else None,
            provider_node_id=item.node.id if item.node else None,
            upstream_model=item.candidate.upstream_model,
            score=result.score,
            estimated_request_cost=item.estimated_request_cost,
            score_breakdown={
                "mode": result.mode,
                "tier": normalized_tier,
                "session_affinity": affinity_match,
                "provider_connection_id": item.connection.id if item.connection else None,
                "provider_node_id": item.node.id if item.node else None,
                "estimated_request_cost": item.estimated_request_cost,
                "factors": result.factors,
                "weighted_factors": result.weighted_factors,
                "penalties": result.penalties,
            },
        )
        scored.append((affinity_match, selected))

    if not scored:
        details = [f"{blocked_count} blocked by circuit breaker"]
        if budget_filtered_count:
            details.append(f"{budget_filtered_count} filtered by request budget")
        if tier_filtered_count:
            details.append(f"{tier_filtered_count} filtered by tier")
        raise NoAvailableCandidateError(
            f"No available candidates for unified model: {unified_model_name}; " + ", ".join(details)
        )
    return [item for _, item in sorted(scored, key=lambda pair: (pair[0], pair[1].score), reverse=True)]


def select_best_candidate(db: Session, unified_model_name: str) -> SelectedCandidate:
    return list_ranked_candidates(db, unified_model_name)[0]
