"""Best-effort normalization of common provider rate-limit response headers."""

from datetime import datetime, timedelta


def quota_from_headers(headers: dict[str, str] | None) -> dict[str, object] | None:
    if not headers:
        return None
    values = {key.lower(): value for key, value in headers.items()}

    def number(*names: str) -> float | None:
        for name in names:
            raw = values.get(name)
            if raw is None:
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return None

    remaining_requests = number("x-ratelimit-remaining-requests", "ratelimit-remaining", "x-rate-limit-remaining")
    remaining_tokens = number("x-ratelimit-remaining-tokens")
    remaining_credit = number("x-ratelimit-remaining-credit", "x-ratelimit-remaining-credits")
    if remaining_requests is None and remaining_tokens is None and remaining_credit is None:
        return None
    reset_at = None
    reset_seconds = number("x-ratelimit-reset-requests", "retry-after")
    if reset_seconds is not None and reset_seconds >= 0:
        reset_at = datetime.utcnow() + timedelta(seconds=reset_seconds)
    return {
        "remaining_requests": int(remaining_requests) if remaining_requests is not None else None,
        "remaining_tokens": int(remaining_tokens) if remaining_tokens is not None else None,
        "remaining_credit": remaining_credit,
        "reset_at": reset_at,
        "raw": values,
    }
