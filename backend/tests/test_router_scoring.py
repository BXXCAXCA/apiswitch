from apiswitch.router.circuit_breaker import CircuitBreaker, CircuitState
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
