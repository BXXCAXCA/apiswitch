from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import ProviderHealth


def _get_or_create_health(db: Session, candidate_id: int) -> ProviderHealth:
    health = db.scalar(select(ProviderHealth).where(ProviderHealth.candidate_id == candidate_id))
    if health is None:
        health = ProviderHealth(candidate_id=candidate_id)
        db.add(health)
        db.flush()
    return health


def record_candidate_success(db: Session, candidate_id: int, latency_ms: float) -> None:
    health = _get_or_create_health(db, candidate_id)
    health.success_count += 1
    health.consecutive_failures = 0
    health.last_success_at = datetime.utcnow()
    if health.avg_latency_ms is None:
        health.avg_latency_ms = latency_ms
    else:
        health.avg_latency_ms = (health.avg_latency_ms * 0.8) + (latency_ms * 0.2)
    health.p50_latency_ms = health.avg_latency_ms
    health.p95_latency_ms = max(health.p95_latency_ms or 0, latency_ms)
    health.updated_at = datetime.utcnow()


def record_candidate_failure(db: Session, candidate_id: int, reason: str) -> None:
    health = _get_or_create_health(db, candidate_id)
    health.failure_count += 1
    health.consecutive_failures += 1
    health.last_failure_at = datetime.utcnow()
    health.last_failure_reason = reason
    health.updated_at = datetime.utcnow()
