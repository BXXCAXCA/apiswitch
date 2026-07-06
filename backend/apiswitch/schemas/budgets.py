from datetime import datetime

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    name: str
    scope: str = "global"
    scope_id: str | None = None
    monthly_limit: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    enabled: bool = True
    spent_amount: float = Field(default=0, ge=0)
    alert_threshold_percent: int = Field(default=80, ge=1, le=100)


class BudgetUpdate(BaseModel):
    name: str | None = None
    scope: str | None = None
    scope_id: str | None = None
    monthly_limit: float | None = Field(default=None, ge=0)
    currency: str | None = None
    enabled: bool | None = None
    spent_amount: float | None = Field(default=None, ge=0)
    alert_threshold_percent: int | None = Field(default=None, ge=1, le=100)


class BudgetRead(BaseModel):
    id: int
    name: str
    scope: str
    scope_id: str | None
    monthly_limit: float | None
    currency: str
    enabled: bool
    spent_amount: float
    alert_threshold_percent: int
    usage_percent: float | None
    alert_triggered: bool
    created_at: datetime
    updated_at: datetime
