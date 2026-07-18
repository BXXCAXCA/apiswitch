"""Budget matching, period rollover, enforcement and usage accumulation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Budget
from apiswitch.gateway.errors import BudgetExceededError, NoAvailableCandidateError


_CHINA_TZ = timezone(timedelta(hours=8), name="UTC+8")


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _calendar_bounds(period_type: str, now: datetime) -> tuple[datetime, datetime]:
    local = _as_utc(now).astimezone(_CHINA_TZ)
    if period_type == "calendar_day":
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif period_type == "calendar_week":
        start = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
    else:
        start = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    return start.astimezone(UTC).replace(tzinfo=None), end.astimezone(UTC).replace(tzinfo=None)


def refresh_budget_period(budget: Budget, *, now: datetime | None = None) -> datetime:
    """Reset a budget when its configured window rolls over and return the window end."""
    current = now or _utc_now()
    previous = budget.period_started_at
    if budget.period_type == "rolling_5_hours":
        start = previous or current
        if start > current or current >= start + timedelta(hours=5):
            start = current
        end = start + timedelta(hours=5)
    else:
        start, end = _calendar_bounds(budget.period_type or "calendar_month", current)

    if previous is not None and previous != start:
        budget.spent_amount = 0
        budget.request_count = 0
    budget.period_started_at = start
    return end


def budget_limit_value(budget: Budget) -> float | int | None:
    return budget.request_limit if budget.billing_mode == "request_count" else budget.monthly_limit


def budget_usage_value(budget: Budget) -> float | int:
    return int(budget.request_count or 0) if budget.billing_mode == "request_count" else float(budget.spent_amount or 0)


def budget_is_exceeded(budget: Budget, *, projected_cost: float | None = None) -> bool:
    refresh_budget_period(budget)
    limit = budget_limit_value(budget)
    if limit is None:
        return False
    usage = budget_usage_value(budget)
    projected = 1 if budget.billing_mode == "request_count" else float(projected_cost or 0)
    return usage >= limit or usage + projected > limit


def _matches(
    budget: Budget,
    *,
    api_token_id: int | None,
    provider_id: int | None,
    upstream_model_id: int | None,
    unified_model: str,
    unified_model_id: int | None,
) -> bool:
    if budget.scope == "global":
        return True
    if budget.scope in {"api_token", "token"}:
        return api_token_id is not None and budget.scope_id == str(api_token_id)
    if budget.scope in {"provider", "provider_instance"}:
        return provider_id is not None and budget.scope_id == str(provider_id)
    if budget.scope == "upstream_model":
        return upstream_model_id is not None and budget.scope_id == str(upstream_model_id)
    if budget.scope == "unified_model":
        return budget.scope_id in {unified_model, str(unified_model_id) if unified_model_id is not None else ""}
    return False


def matching_budgets(
    db: Session,
    *,
    api_token_id: int | None,
    provider_id: int | None,
    unified_model: str,
    upstream_model_id: int | None = None,
    unified_model_id: int | None = None,
) -> list[Budget]:
    rows = [
        budget
        for budget in db.scalars(select(Budget).where(Budget.enabled.is_(True))).all()
        if _matches(
            budget,
            api_token_id=api_token_id,
            provider_id=provider_id,
            upstream_model_id=upstream_model_id,
            unified_model=unified_model,
            unified_model_id=unified_model_id,
        )
    ]
    for budget in rows:
        refresh_budget_period(budget)
    return rows


def _candidate_value(candidate: object, direct: str, nested: str) -> int | None:
    value = getattr(candidate, direct, None)
    if value is not None:
        return int(value)
    nested_value = getattr(candidate, nested, None)
    return int(nested_value.id) if nested_value is not None else None


def enforce_candidate_budgets(
    db: Session,
    candidates: list[object],
    *,
    api_token_id: int | None,
    unified_model: str,
) -> list[object]:
    allowed: list[object] = []
    cheapest_fallback = False
    for candidate in candidates:
        cost = getattr(candidate, "estimated_request_cost", None)
        budgets = matching_budgets(
            db,
            api_token_id=api_token_id,
            provider_id=_candidate_value(candidate, "provider_id", "provider"),
            upstream_model_id=_candidate_value(candidate, "upstream_model_id", "upstream"),
            unified_model=unified_model,
        )
        exceeded = [budget for budget in budgets if budget_is_exceeded(budget, projected_cost=cost)]
        actions = {budget.enforcement_action for budget in exceeded}
        if "reject" in actions:
            raise BudgetExceededError(f"Budget exceeded: {', '.join(budget.name for budget in exceeded)}")
        if "fallback_to_free" in actions and (cost is None or cost > 0):
            continue
        if "fallback_to_cheapest" in actions:
            cheapest_fallback = True
        allowed.append(candidate)
    if not allowed:
        raise NoAvailableCandidateError("No candidate remains after budget enforcement")
    if cheapest_fallback:
        return sorted(
            allowed,
            key=lambda candidate: candidate.estimated_request_cost
            if candidate.estimated_request_cost is not None
            else float("inf"),
        )
    return allowed


def accumulate_budget_spend(
    db: Session,
    *,
    estimated_cost: float | None,
    api_token_id: int | None,
    provider_id: int,
    unified_model: str,
    upstream_model_id: int | None = None,
    unified_model_id: int | None = None,
) -> None:
    for budget in matching_budgets(
        db,
        api_token_id=api_token_id,
        provider_id=provider_id,
        upstream_model_id=upstream_model_id,
        unified_model=unified_model,
        unified_model_id=unified_model_id,
    ):
        if budget.billing_mode == "request_count":
            budget.request_count = int(budget.request_count or 0) + 1
        elif estimated_cost is not None:
            budget.spent_amount = round(float(budget.spent_amount or 0) + estimated_cost, 10)
