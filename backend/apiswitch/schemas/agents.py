from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentConfigCreate(BaseModel):
    agent_type: str
    config_path: str | None = None
    last_backup_path: str | None = None
    enabled: bool = True
    notes: str | None = None
    settings: dict[str, Any] = {}


class AgentConfigUpdate(BaseModel):
    agent_type: str | None = None
    config_path: str | None = None
    last_backup_path: str | None = None
    enabled: bool | None = None
    notes: str | None = None
    settings: dict[str, Any] | None = None


class AgentConfigRead(BaseModel):
    id: int
    agent_type: str
    config_path: str | None
    last_backup_path: str | None
    enabled: bool
    notes: str | None
    settings: dict[str, Any]
    config_exists: bool
    backup_configured: bool
    created_at: datetime
    updated_at: datetime


class AgentConfigCheckResult(BaseModel):
    ok: bool
    message: str
    config_exists: bool
