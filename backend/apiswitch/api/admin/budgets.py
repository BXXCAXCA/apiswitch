from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import Budget
from apiswitch.schemas.budgets import BudgetCreate, BudgetRead, BudgetUpdate

router = APIRouter(prefix="/api/admin/budgets", tags=["Admin - Budgets"])


def _get_budget(db: Session, budget_id: int) -> Budget:
    budget = db.get(Budget, budget_id)
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Budget not found")
    return budget


def _usage_percent(budget: Budget) -> float | None:
    if budget.monthly_limit is None or budget.monthly_limit <= 0:
        return None
    return round((budget.spent_amount / budget.monthly_limit) * 100, 2)


def _to_read(budget: Budget) -> BudgetRead:
    usage_percent = _usage_percent(budget)
    return BudgetRead(
        id=budget.id,
        name=budget.name,
        scope=budget.scope,
        scope_id=budget.scope_id,
        monthly_limit=budget.monthly_limit,
        currency=budget.currency,
        enabled=budget.enabled,
        spent_amount=budget.spent_amount,
        alert_threshold_percent=budget.alert_threshold_percent,
        usage_percent=usage_percent,
        alert_triggered=usage_percent is not None and usage_percent >= budget.alert_threshold_percent,
        enforcement_action=budget.enforcement_action,
        created_at=budget.created_at,
        updated_at=budget.updated_at,
    )


@router.get("")
async def list_budgets(db: Session = Depends(get_db)) -> list[BudgetRead]:
    budgets = db.scalars(select(Budget).order_by(Budget.id.desc())).all()
    return [_to_read(budget) for budget in budgets]


@router.post("")
async def create_budget(payload: BudgetCreate, db: Session = Depends(get_db)) -> BudgetRead:
    budget = Budget(
        name=payload.name,
        scope=payload.scope,
        scope_id=payload.scope_id,
        monthly_limit=payload.monthly_limit,
        currency=payload.currency,
        enabled=payload.enabled,
        spent_amount=payload.spent_amount,
        alert_threshold_percent=payload.alert_threshold_percent,
        enforcement_action=payload.enforcement_action,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return _to_read(budget)


@router.patch("/{budget_id}")
async def update_budget(
    budget_id: int,
    payload: BudgetUpdate,
    db: Session = Depends(get_db),
) -> BudgetRead:
    budget = _get_budget(db, budget_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(budget, key, value)
    db.commit()
    db.refresh(budget)
    return _to_read(budget)


@router.delete("/{budget_id}")
async def delete_budget(budget_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    budget = _get_budget(db, budget_id)
    db.delete(budget)
    db.commit()
    return {"deleted": True}
