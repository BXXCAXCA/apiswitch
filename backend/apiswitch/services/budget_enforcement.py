"""Budget matching, enforcement and automatic spend accumulation."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import Budget
from apiswitch.gateway.errors import BudgetExceededError, NoAvailableCandidateError


def _matches(budget: Budget, *, api_token_id: int | None, provider_id: int, unified_model: str) -> bool:
    if budget.scope == "global":
        return True
    if budget.scope == "api_token":
        return budget.scope_id == str(api_token_id) if api_token_id is not None else False
    if budget.scope == "provider":
        return budget.scope_id == str(provider_id)
    if budget.scope == "unified_model":
        return budget.scope_id == unified_model
    return False


def matching_budgets(db: Session, *, api_token_id: int | None, provider_id: int, unified_model: str) -> list[Budget]:
    return [
        budget for budget in db.scalars(select(Budget).where(Budget.enabled.is_(True))).all()
        if _matches(budget, api_token_id=api_token_id, provider_id=provider_id, unified_model=unified_model)
    ]


def enforce_candidate_budgets(db: Session, candidates: list[object], *, api_token_id: int | None, unified_model: str) -> list[object]:
    allowed: list[object] = []
    cheapest_fallback = False
    for candidate in candidates:
        cost = getattr(candidate, "estimated_request_cost")
        budgets = matching_budgets(
            db, api_token_id=api_token_id, provider_id=getattr(candidate, "provider_id"), unified_model=unified_model
        )
        exceeded = [budget for budget in budgets if budget.monthly_limit is not None and budget.spent_amount + (cost or 0) > budget.monthly_limit]
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
        return sorted(allowed, key=lambda candidate: candidate.estimated_request_cost if candidate.estimated_request_cost is not None else float("inf"))
    return allowed


def accumulate_budget_spend(
    db: Session,
    *,
    estimated_cost: float | None,
    api_token_id: int | None,
    provider_id: int,
    unified_model: str,
) -> None:
    if estimated_cost is None:
        return
    for budget in matching_budgets(db, api_token_id=api_token_id, provider_id=provider_id, unified_model=unified_model):
        budget.spent_amount = round(budget.spent_amount + estimated_cost, 10)
