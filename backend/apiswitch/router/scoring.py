from dataclasses import dataclass

DEFAULT_SCORE_WEIGHTS = {
    "health": 0.25,
    "quota": 0.15,
    "cost": 0.15,
    "latency": 0.15,
    "task_fit": 0.10,
    "context_fit": 0.08,
    "stability": 0.07,
    "manual_priority": 0.05,
}

TIER_SCORE_WEIGHTS = {
    "balanced": DEFAULT_SCORE_WEIGHTS,
    "fast": {
        "health": 0.25,
        "quota": 0.10,
        "cost": 0.05,
        "latency": 0.30,
        "task_fit": 0.10,
        "context_fit": 0.05,
        "stability": 0.10,
        "manual_priority": 0.05,
    },
    "cheap": {
        "health": 0.15,
        "quota": 0.20,
        "cost": 0.35,
        "latency": 0.08,
        "task_fit": 0.07,
        "context_fit": 0.05,
        "stability": 0.05,
        "manual_priority": 0.05,
    },
    "free": {
        "health": 0.15,
        "quota": 0.25,
        "cost": 0.30,
        "latency": 0.08,
        "task_fit": 0.07,
        "context_fit": 0.05,
        "stability": 0.05,
        "manual_priority": 0.05,
    },
    "quality": {
        "health": 0.20,
        "quota": 0.08,
        "cost": 0.05,
        "latency": 0.07,
        "task_fit": 0.25,
        "context_fit": 0.15,
        "stability": 0.15,
        "manual_priority": 0.05,
    },
    "reliable": {
        "health": 0.35,
        "quota": 0.15,
        "cost": 0.05,
        "latency": 0.10,
        "task_fit": 0.08,
        "context_fit": 0.07,
        "stability": 0.15,
        "manual_priority": 0.05,
    },
}


@dataclass(frozen=True)
class CandidateScoreInput:
    stability_score: float
    speed_score: float
    manual_priority_adjustment: float = 0.0
    failure_penalty: float = 0.0
    budget_penalty: float = 0.0
    health_score: float | None = None
    quota_score: float | None = None
    cost_score: float | None = None
    latency_score: float | None = None
    task_fit_score: float | None = None
    context_fit_score: float | None = None
    manual_priority_score: float | None = None


@dataclass(frozen=True)
class CandidateScoreResult:
    score: float
    factors: dict[str, float]
    weighted_factors: dict[str, float]
    penalties: dict[str, float]
    mode: str


def get_tier_score_weights(tier: str | None) -> tuple[str, dict[str, float]]:
    normalized = (tier or "balanced").strip().lower()
    if normalized not in TIER_SCORE_WEIGHTS:
        normalized = "balanced"
    return normalized, dict(TIER_SCORE_WEIGHTS[normalized])


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, float(value)))


def _uses_extended_scoring(item: CandidateScoreInput) -> bool:
    return any(
        value is not None
        for value in (
            item.health_score,
            item.quota_score,
            item.cost_score,
            item.latency_score,
            item.task_fit_score,
            item.context_fit_score,
            item.manual_priority_score,
        )
    )


def calculate_score_details(
    item: CandidateScoreInput,
    weights: dict[str, float] | None = None,
    stability_weight: float = 0.7,
    speed_weight: float = 0.3,
) -> CandidateScoreResult:
    if not _uses_extended_scoring(item):
        factors = {
            "stability": _clamp(item.stability_score),
            "speed": _clamp(item.speed_score),
        }
        weighted_factors = {
            "stability": factors["stability"] * stability_weight,
            "speed": factors["speed"] * speed_weight,
            "manual_priority": item.manual_priority_adjustment,
        }
        penalties = {
            "failure": max(0.0, item.failure_penalty),
            "budget": max(0.0, item.budget_penalty),
        }
        score = sum(weighted_factors.values()) - sum(penalties.values())
        return CandidateScoreResult(
            score=_clamp(score),
            factors=factors,
            weighted_factors=weighted_factors,
            penalties=penalties,
            mode="legacy",
        )

    resolved_weights = dict(DEFAULT_SCORE_WEIGHTS)
    if weights:
        resolved_weights.update(weights)
    weight_total = sum(resolved_weights.values())
    if abs(weight_total - 1.0) > 0.000001:
        raise ValueError(f"Score weights must sum to 1.0, got {weight_total}")

    factors = {
        "health": _clamp(item.health_score if item.health_score is not None else item.stability_score),
        "quota": _clamp(item.quota_score if item.quota_score is not None else 50.0),
        "cost": _clamp(item.cost_score if item.cost_score is not None else 50.0),
        "latency": _clamp(item.latency_score if item.latency_score is not None else item.speed_score),
        "task_fit": _clamp(item.task_fit_score if item.task_fit_score is not None else 50.0),
        "context_fit": _clamp(item.context_fit_score if item.context_fit_score is not None else 50.0),
        "stability": _clamp(item.stability_score),
        "manual_priority": _clamp(
            item.manual_priority_score
            if item.manual_priority_score is not None
            else item.manual_priority_adjustment * 100.0
        ),
    }
    weighted_factors = {name: factors[name] * resolved_weights[name] for name in DEFAULT_SCORE_WEIGHTS}
    penalties = {
        "failure": max(0.0, item.failure_penalty),
        "budget": max(0.0, item.budget_penalty),
    }
    score = sum(weighted_factors.values()) - sum(penalties.values())
    return CandidateScoreResult(
        score=_clamp(score),
        factors=factors,
        weighted_factors=weighted_factors,
        penalties=penalties,
        mode="extended",
    )


def calculate_score(
    item: CandidateScoreInput,
    stability_weight: float = 0.7,
    speed_weight: float = 0.3,
) -> float:
    return calculate_score_details(
        item,
        stability_weight=stability_weight,
        speed_weight=speed_weight,
    ).score
