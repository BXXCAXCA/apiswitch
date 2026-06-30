from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from apiswitch.db.base import Base
from apiswitch.router.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    get_or_create_breaker,
    is_candidate_allowed,
    record_breaker_failure,
    record_breaker_success,
)
from apiswitch.router.scoring import CandidateScoreInput, calculate_score


def test_score_uses_default_weights():
    score = calculate_score(CandidateScoreInput(stability_score=100, speed_score=50))
    assert score == 85


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2)
    breaker.record_failure()
    assert breaker.state == CircuitState.CLOSED
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_persistent_circuit_breaker_open_half_open_closed():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        breaker = get_or_create_breaker(db, candidate_id=1)
        breaker.failure_threshold = 2
        breaker.cooldown_seconds = 1
        record_breaker_failure(db, candidate_id=1, consecutive_failures=1)
        assert breaker.state == CircuitState.CLOSED.value

        record_breaker_failure(db, candidate_id=1, consecutive_failures=2)
        assert breaker.state == CircuitState.OPEN.value
        assert is_candidate_allowed(db, candidate_id=1, now=datetime.utcnow()) is False

        breaker.opened_at = datetime.utcnow() - timedelta(seconds=2)
        assert is_candidate_allowed(db, candidate_id=1, now=datetime.utcnow()) is True
        assert breaker.state == CircuitState.HALF_OPEN.value

        record_breaker_success(db, candidate_id=1)
        assert breaker.state == CircuitState.CLOSED.value
        assert breaker.opened_at is None
        assert breaker.half_open_at is None


def test_half_open_failure_reopens_breaker():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        breaker = get_or_create_breaker(db, candidate_id=2)
        breaker.state = CircuitState.HALF_OPEN.value
        record_breaker_failure(db, candidate_id=2, consecutive_failures=1)
        assert breaker.state == CircuitState.OPEN.value
        assert breaker.opened_at is not None
