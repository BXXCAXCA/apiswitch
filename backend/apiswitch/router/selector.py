from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Provider, ProviderHealth, UnifiedModel, UnifiedModelCandidate
from apiswitch.gateway.errors import NoAvailableCandidateError, UnifiedModelNotFoundError
from apiswitch.router.scoring import CandidateScoreInput, calculate_score


@dataclass(frozen=True)
class SelectedCandidate:
    candidate_id: int
    provider_id: int
    provider_name: str
    provider_type: str
    upstream_model: str
    score: float


def list_ranked_candidates(db: Session, unified_model_name: str) -> list[SelectedCandidate]:
    unified_model = db.scalar(
        select(UnifiedModel).where(
            UnifiedModel.name == unified_model_name,
            UnifiedModel.enabled.is_(True),
        )
    )
    if unified_model is None:
        raise UnifiedModelNotFoundError(f"Unified model not found: {unified_model_name}")

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

    scored: list[SelectedCandidate] = []
    for candidate, provider, health in rows:
        success_count = health.success_count if health else 0
        failure_count = health.failure_count if health else 0
        total_count = success_count + failure_count
        stability = 100.0 if total_count == 0 else (success_count / total_count) * 100.0
        avg_latency = health.avg_latency_ms if health and health.avg_latency_ms else 1000.0
        speed = max(0.0, min(100.0, 100.0 - (avg_latency / 50.0)))
        failure_penalty = float(health.consecutive_failures * 10) if health else 0.0
        score = calculate_score(
            CandidateScoreInput(
                stability_score=stability,
                speed_score=speed,
                manual_priority_adjustment=float(candidate.manual_priority) / 100.0,
                failure_penalty=failure_penalty,
            )
        )
        scored.append(
            SelectedCandidate(
                candidate_id=candidate.id,
                provider_id=provider.id,
                provider_name=provider.name,
                provider_type=provider.type,
                upstream_model=candidate.upstream_model,
                score=score,
            )
        )

    return sorted(scored, key=lambda item: item.score, reverse=True)


def select_best_candidate(db: Session, unified_model_name: str) -> SelectedCandidate:
    return list_ranked_candidates(db, unified_model_name)[0]
