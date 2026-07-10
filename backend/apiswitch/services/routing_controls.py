import json
from typing import Any


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
