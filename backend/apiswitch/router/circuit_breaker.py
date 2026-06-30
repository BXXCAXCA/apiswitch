from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import CircuitBreakerModel


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


DEFAULT_FAILURE_THRESHOLD = 5
DEFAULT_COOLDOWN_SECONDS = 60


def get_or_create_breaker(db: Session, candidate_id: int) -> CircuitBreakerModel:
    breaker = db.scalar(select(CircuitBreakerModel).where(CircuitBreakerModel.candidate_id == candidate_id))
    if breaker is None:
        breaker = CircuitBreakerModel(
            candidate_id=candidate_id,
            state=CircuitState.CLOSED.value,
            failure_threshold=DEFAULT_FAILURE_THRESHOLD,
            cooldown_seconds=DEFAULT_COOLDOWN_SECONDS,
        )
        db.add(breaker)
        db.flush()
    return breaker


def is_candidate_allowed(db: Session, candidate_id: int, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    breaker = get_or_create_breaker(db, candidate_id)
    if breaker.state == CircuitState.CLOSED.value:
        return True
    if breaker.state == CircuitState.HALF_OPEN.value:
        return True
    if breaker.state == CircuitState.OPEN.value:
        if breaker.opened_at is None:
            return False
        cooldown_until = breaker.opened_at + timedelta(seconds=breaker.cooldown_seconds)
        if now >= cooldown_until:
            breaker.state = CircuitState.HALF_OPEN.value
            breaker.half_open_at = now
            breaker.updated_at = now
            db.flush()
            return True
        return False
    return True


def record_breaker_success(db: Session, candidate_id: int) -> None:
    now = datetime.utcnow()
    breaker = get_or_create_breaker(db, candidate_id)
    breaker.state = CircuitState.CLOSED.value
    breaker.opened_at = None
    breaker.half_open_at = None
    breaker.updated_at = now


def record_breaker_failure(db: Session, candidate_id: int, consecutive_failures: int) -> None:
    now = datetime.utcnow()
    breaker = get_or_create_breaker(db, candidate_id)
    if breaker.state == CircuitState.HALF_OPEN.value:
        breaker.state = CircuitState.OPEN.value
        breaker.opened_at = now
        breaker.half_open_at = None
        breaker.updated_at = now
        return
    if consecutive_failures >= breaker.failure_threshold:
        breaker.state = CircuitState.OPEN.value
        breaker.opened_at = now
        breaker.half_open_at = None
        breaker.updated_at = now
    else:
        breaker.state = CircuitState.CLOSED.value
        breaker.updated_at = now


class CircuitBreaker:
    def __init__(self, failure_threshold: int = DEFAULT_FAILURE_THRESHOLD) -> None:
        self.failure_threshold = failure_threshold
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
