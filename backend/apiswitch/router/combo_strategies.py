"""Ordering policies for Combo and Auto-Combo candidate pools."""

from dataclasses import replace
from math import inf

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apiswitch.db.models import Setting, UnifiedModel, UsageHistory

SUPPORTED_COMBO_STRATEGIES = {
    "priority",
    "weighted",
    "round_robin",
    "least_used",
    "cost_optimized",
    "quota_headroom",
    "last_known_good",
}


def _routing(model: UnifiedModel) -> dict:
    value = (model.capabilities_json or {}).get("routing", {})
    return value if isinstance(value, dict) else {}


def _strategy_state(db: Session, model: UnifiedModel, strategy: str) -> int:
    key = f"combo:{model.id}:{strategy}"
    setting = db.get(Setting, key)
    current = int(((setting.value_json or {}).get("value", 0))) if setting else 0
    next_value = current + 1
    if setting is None:
        db.add(Setting(key=key, value_json={"value": next_value}))
    else:
        setting.value_json = {"value": next_value}
    return current


def _usage_count(db: Session, candidate: object) -> int:
    connection_id = getattr(candidate, "provider_connection_id")
    if connection_id is not None:
        return int(db.scalar(select(func.count(UsageHistory.id)).where(UsageHistory.provider_connection_id == connection_id)) or 0)
    return int(
        db.scalar(
            select(func.count(UsageHistory.id)).where(
                UsageHistory.upstream_model == getattr(candidate, "upstream_model"),
            )
        )
        or 0
    )


def _with_strategy(candidates: list[object], strategy: str) -> list[object]:
    return [
        replace(candidate, score_breakdown={**candidate.score_breakdown, "combo_strategy": strategy})
        for candidate in candidates
    ]


def order_combo_candidates(db: Session, model: UnifiedModel, candidates: list[object]) -> list[object]:
    """Return candidates in the configured dispatch order.

    The returned list still includes fallback candidates; the gateway retries in
    that order when the first selected target fails.
    """
    config = _routing(model)
    mode = config.get("routing_mode", "static")
    strategy = config.get("combo_strategy", "priority")
    if mode not in {"combo", "auto"} or strategy not in SUPPORTED_COMBO_STRATEGIES:
        return candidates

    if strategy == "priority":
        ordered = sorted(candidates, key=lambda item: (-item.score, -item.candidate_id))
    elif strategy == "cost_optimized":
        ordered = sorted(candidates, key=lambda item: (item.estimated_request_cost if item.estimated_request_cost is not None else inf, -item.score))
    elif strategy == "quota_headroom":
        ordered = sorted(candidates, key=lambda item: (-float(item.score_breakdown["factors"]["quota"]), -item.score))
    elif strategy == "least_used":
        ordered = sorted(candidates, key=lambda item: (_usage_count(db, item), -item.score))
    elif strategy == "last_known_good":
        ordered = sorted(
            candidates,
            key=lambda item: (
                not bool(item.score_breakdown.get("session_affinity")),
                -float(item.score_breakdown["factors"]["health"]),
                -item.score,
            ),
        )
    else:
        base = sorted(candidates, key=lambda item: -item.score)
        cursor = _strategy_state(db, model, strategy)
        if strategy == "round_robin":
            start = cursor % len(base)
        else:  # weighted: use manual-priority-derived slots without unbounded expansion.
            weights = [max(1, min(100, int(item.score_breakdown["factors"]["manual_priority"]))) for item in base]
            total = sum(weights)
            slot = cursor % total
            start = next(index for index, weight in enumerate(weights) if (slot := slot - weight) < 0)
        ordered = base[start:] + base[:start]
    return _with_strategy(ordered, strategy)
