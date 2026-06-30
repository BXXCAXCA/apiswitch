from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import CircuitBreakerModel, Provider, ProviderHealth, UnifiedModel, UnifiedModelCandidate
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

    items = []
    for unified_model, candidate, provider, health, breaker in rows:
        ranked = list_ranked_candidates(db, unified_model.name) if unified_model.enabled else []
        score = next((item.score for item in ranked if item.candidate_id == candidate.id), None)
        items.append(
            {
                "unified_model": unified_model.name,
                "candidate_id": candidate.id,
                "provider": provider.name,
                "provider_type": provider.type,
                "upstream_model": candidate.upstream_model,
                "enabled": candidate.enabled and provider.enabled and unified_model.enabled,
                "score": round(score or 0, 2),
                "success_count": health.success_count if health else 0,
                "failure_count": health.failure_count if health else 0,
                "consecutive_failures": health.consecutive_failures if health else 0,
                "avg_latency_ms": round(health.avg_latency_ms, 2) if health and health.avg_latency_ms else None,
                "last_failure_reason": health.last_failure_reason if health else None,
                "circuit_state": breaker.state if breaker else "closed",
            }
        )

    return {"items": items, "total": len(items)}
