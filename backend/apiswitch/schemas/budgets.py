from datetime import datetime

from typing import Literal

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
    enforcement_action: Literal["warn_only", "reject", "fallback_to_free", "fallback_to_cheapest"] = "warn_only"


class BudgetUpdate(BaseModel):
    name: str | None = None
    scope: str | None = None
    scope_id: str | None = None
    monthly_limit: float | None = Field(default=None, ge=0)
    currency: str | None = None
    enabled: bool | None = None
    spent_amount: float | None = Field(default=None, ge=0)
    alert_threshold_percent: int | None = Field(default=None, ge=1, le=100)
    enforcement_action: Literal["warn_only", "reject", "fallback_to_free", "fallback_to_cheapest"] | None = None


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
    enforcement_action: str
    created_at: datetime
    updated_at: datetime
