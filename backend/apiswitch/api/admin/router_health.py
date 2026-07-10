from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import CircuitBreakerModel, Provider, ProviderHealth, UnifiedModel, UnifiedModelCandidate
from apiswitch.router.circuit_breaker import CircuitState, is_candidate_allowed
from apiswitch.router.selector import list_ranked_candidates

router = APIRouter(prefix="/api/admin/router-health", tags=["Admin - Router Health"])


@router.get("")
async def list_router_health(db: Session = Depends(get_db)) -> dict:
    rows = db.execute(
        select(UnifiedModel, UnifiedModelCandidate, Provider, ProviderHealth, CircuitBreakerModel)
        .join(UnifiedModelCandidate, UnifiedModelCandidate.unified_model_id == UnifiedModel.id)
        .join(Provider, Provider.id == UnifiedModelCandidate.provider_id)
        .outerjoin(ProviderHealth, ProviderHealth.candidate_id == UnifiedModelCandidate.id)
        .outerjoin(CircuitBreakerModel, CircuitBreakerModel.candidate_id == UnifiedModelCandidate.id)
        .order_by(UnifiedModel.name, UnifiedModelCandidate.manual_priority.desc())
    ).all()

    ranked_by_model: dict[str, list] = {}
    for unified_model, _candidate, _provider, _health, _breaker in rows:
        if unified_model.enabled and unified_model.name not in ranked_by_model:
            try:
                ranked_by_model[unified_model.name] = list_ranked_candidates(db, unified_model.name)
            except Exception:  # noqa: BLE001
                ranked_by_model[unified_model.name] = []

    items = []
    for unified_model, candidate, provider, health, breaker in rows:
        ranked = ranked_by_model.get(unified_model.name, [])
        ranked_item = next((item for item in ranked if item.candidate_id == candidate.id), None)
        allowed = is_candidate_allowed(db, candidate.id) if candidate.enabled and provider.enabled and unified_model.enabled else False
        state = breaker.state if breaker else CircuitState.CLOSED.value
        items.append(
            {
                "unified_model": unified_model.name,
                "candidate_id": candidate.id,
                "provider": provider.name,
                "provider_type": provider.type,
                "upstream_model": candidate.upstream_model,
                "enabled": candidate.enabled and provider.enabled and unified_model.enabled,
                "available": allowed,
                "score": round(ranked_item.score if ranked_item else 0, 2),
                "score_breakdown": ranked_item.score_breakdown if ranked_item else None,
                "success_count": health.success_count if health else 0,
                "failure_count": health.failure_count if health else 0,
                "consecutive_failures": health.consecutive_failures if health else 0,
                "avg_latency_ms": round(health.avg_latency_ms, 2) if health and health.avg_latency_ms else None,
                "last_failure_reason": health.last_failure_reason if health else None,
                "circuit_state": state,
                "opened_at": breaker.opened_at.isoformat() + "Z" if breaker and breaker.opened_at else None,
                "half_open_at": breaker.half_open_at.isoformat() + "Z" if breaker and breaker.half_open_at else None,
                "failure_threshold": breaker.failure_threshold if breaker else None,
                "cooldown_seconds": breaker.cooldown_seconds if breaker else None,
            }
        )

    db.commit()
    return {"items": items, "total": len(items)}
