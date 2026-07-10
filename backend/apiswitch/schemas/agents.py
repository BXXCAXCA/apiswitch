from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentConfigCreate(BaseModel):
    agent_type: str
    config_path: str | None = None
    last_backup_path: str | None = None
    enabled: bool = True
    notes: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)


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


class ClaudeCodeProfileWriteRequest(BaseModel):
    profile_name: str = "apiswitch"
    base_url: str = "http://127.0.0.1:8080"
    model: str = "code-best"
    effort_level: str | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    auto_compact_window: int | None = Field(default=None, ge=1)
    dry_run: bool = False


class ClaudeCodeProfileWriteResult(BaseModel):
    ok: bool
    profile_name: str
    config_dir: str
    settings_path: str
    backup_path: str | None
    written: bool
    settings: dict[str, Any]
    powershell_command: str
    posix_command: str
    message: str
