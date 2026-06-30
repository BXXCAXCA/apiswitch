from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateScoreInput:
    stability_score: float
    speed_score: float
    manual_priority_adjustment: float = 0.0
    failure_penalty: float = 0.0
    budget_penalty: float = 0.0


def calculate_score(
    item: CandidateScoreInput,
    stability_weight: float = 0.7,
    speed_weight: float = 0.3,
) -> float:
    return (
        item.stability_score * stability_weight
        + item.speed_score * speed_weight
        + item.manual_priority_adjustment
        - item.failure_penalty
        - item.budget_penalty
    )
