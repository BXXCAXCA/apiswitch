import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from apiswitch.schemas.agents import (
    ClaudeCodeProfileRestoreRequest,
    ClaudeCodeProfileRestoreResult,
    ClaudeCodeProfileWriteRequest,
    ClaudeCodeProfileWriteResult,
)

_PROFILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
_SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"


class ClaudeCodeProfileError(ValueError):
    pass


def _profiles_root() -> Path:
    configured = os.getenv("APISWITCH_CLAUDE_CONFIG_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / ".claude" / "profiles").resolve()


def _normalize_profile_name(profile_name: str) -> str:
    value = profile_name.strip()
    if not value or not _PROFILE_PATTERN.fullmatch(value):
        raise ClaudeCodeProfileError(
            "Profile name may contain only letters, numbers, dots, underscores, and hyphens"
        )
    if value in {".", ".."}:
        raise ClaudeCodeProfileError("Invalid profile name")
    return value


def _normalize_base_url(base_url: str) -> str:
    value = base_url.strip().rstrip("/")
    if value.endswith("/v1"):
        value = value[:-3].rstrip("/")
    if not value.startswith(("http://", "https://")):
        raise ClaudeCodeProfileError("Base URL must start with http:// or https://")
    return value


def build_claude_code_settings(payload: ClaudeCodeProfileWriteRequest) -> dict[str, Any]:
    base_url = _normalize_base_url(payload.base_url)
    model = payload.model.strip()
    if not model:
        raise ClaudeCodeProfileError("Model is required")

    env: dict[str, str] = {
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_MODEL": model,
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    }
    if payload.max_output_tokens is not None:
        env["CLAUDE_CODE_MAX_OUTPUT_TOKENS"] = str(payload.max_output_tokens)
    if payload.auto_compact_window is not None:
        env["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(payload.auto_compact_window)

    settings: dict[str, Any] = {
        "$schema": _SCHEMA_URL,
        "model": model,
        "env": env,
    }
    if payload.effort_level:
        settings["effortLevel"] = payload.effort_level
    return settings


def write_claude_code_profile(payload: ClaudeCodeProfileWriteRequest) -> ClaudeCodeProfileWriteResult:
    profile_name = _normalize_profile_name(payload.profile_name)
    root = _profiles_root()
    config_dir = (root / profile_name).resolve()
    if config_dir.parent != root:
        raise ClaudeCodeProfileError("Profile path escapes the Claude Code profiles directory")

    settings_path = config_dir / "settings.json"
    settings = build_claude_code_settings(payload)
    backup_path: Path | None = None

    if not payload.dry_run:
        config_dir.mkdir(parents=True, exist_ok=True)
        if settings_path.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_path = config_dir / f"settings.json.bak-{timestamp}"
            backup_path.write_bytes(settings_path.read_bytes())

        temporary_path = config_dir / ".settings.json.tmp"
        temporary_path.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(settings_path)

    config_dir_text = str(config_dir)
    powershell_command = (
        f'$env:CLAUDE_CONFIG_DIR="{config_dir_text}"; '
        '$env:ANTHROPIC_AUTH_TOKEN="<APISWITCH_TOKEN>"; claude'
    )
    posix_command = (
        f'CLAUDE_CONFIG_DIR="{config_dir_text}" '
        'ANTHROPIC_AUTH_TOKEN="<APISWITCH_TOKEN>" claude'
    )

    return ClaudeCodeProfileWriteResult(
        ok=True,
        profile_name=profile_name,
        config_dir=config_dir_text,
        settings_path=str(settings_path),
        backup_path=str(backup_path) if backup_path else None,
        written=not payload.dry_run,
        settings=settings,
        powershell_command=powershell_command,
        posix_command=posix_command,
        message="Claude Code profile preview generated" if payload.dry_run else "Claude Code profile written",
    )


def restore_claude_code_profile(
    payload: ClaudeCodeProfileRestoreRequest,
) -> ClaudeCodeProfileRestoreResult:
    profile_name = _normalize_profile_name(payload.profile_name)
    root = _profiles_root()
    config_dir = (root / profile_name).resolve()
    if config_dir.parent != root:
        raise ClaudeCodeProfileError("Profile path escapes the Claude Code profiles directory")
    settings_path = config_dir / "settings.json"
    if payload.backup_path:
        backup_path = Path(payload.backup_path).expanduser().resolve()
        if backup_path.parent != config_dir or not backup_path.name.startswith("settings.json.bak-"):
            raise ClaudeCodeProfileError("Backup path must be a backup in the selected profile directory")
    else:
        backups = sorted(config_dir.glob("settings.json.bak-*"), reverse=True)
        if not backups:
            raise ClaudeCodeProfileError("No Claude Code backup is available for this profile")
        backup_path = backups[0]
    if not backup_path.is_file():
        raise ClaudeCodeProfileError("Claude Code backup does not exist")

    current_backup: Path | None = None
    if settings_path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        current_backup = config_dir / f"settings.json.bak-{timestamp}-before-restore"
        current_backup.write_bytes(settings_path.read_bytes())
    temporary_path = config_dir / ".settings.json.restore.tmp"
    temporary_path.write_bytes(backup_path.read_bytes())
    temporary_path.replace(settings_path)
    return ClaudeCodeProfileRestoreResult(
        ok=True,
        profile_name=profile_name,
        settings_path=str(settings_path),
        restored_from=str(backup_path),
        backup_path=str(current_backup) if current_backup else None,
        message="Claude Code profile restored",
    )
