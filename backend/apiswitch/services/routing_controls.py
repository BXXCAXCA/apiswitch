import json
from typing import Any

ALLOWED_ROUTING_TIERS = {"balanced", "fast", "cheap", "free", "quality", "reliable"}


def estimate_token_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            text = str(value)
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def validate_request_budget(value: float | None) -> float | None:
    if value is None:
        return None
    if value <= 0:
        raise ValueError("X-APISwitch-Budget must be greater than zero")
    return value


def validate_routing_tier(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = value.strip().lower()
    if normalized not in ALLOWED_ROUTING_TIERS:
        allowed = ", ".join(sorted(ALLOWED_ROUTING_TIERS))
        raise ValueError(f"X-APISwitch-Tier must be one of: {allowed}")
    return normalized
