from __future__ import annotations

import json
import os
import re
import shutil
from collections.abc import MutableMapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import json5
import tomlkit
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import AgentConfig, UnifiedModel, UnifiedModelCandidate, UpstreamModel

MODEL_FIELDS = ("main_model_id", "opus_model_id", "sonnet_model_id", "haiku_model_id")
_SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"
AGENT_SPECS: dict[str, dict[str, str]] = {
    "codex": {"label": "Codex", "path": ".codex/config.toml", "protocol": "openai_responses", "language": "toml"},
    "opencode": {"label": "OpenCode", "path": ".config/opencode/opencode.json", "protocol": "openai_chat", "language": "json"},
    "openclaw": {"label": "龙虾（OpenClaw）", "path": ".openclaw/openclaw.json", "protocol": "openai_chat", "language": "json"},
    "hermes": {"label": "Hermes Agent", "path": ".hermes/config.yaml", "protocol": "openai_chat", "language": "yaml"},
    "gemini-cli": {"label": "Gemini CLI", "path": ".gemini/.env", "protocol": "gemini_v1beta", "language": "shell"},
}


def validate_user_config_path(path: Path) -> Path:
    target = path.expanduser().resolve()
    home = Path(os.getenv("USERPROFILE") or Path.home()).resolve()
    if target != home and home not in target.parents:
        raise ValueError("Agent 配置路径必须位于当前用户目录内")
    return target


def default_agent_path(agent_type: str) -> Path:
    spec = AGENT_SPECS.get(agent_type)
    if not spec:
        raise ValueError("不支持的 Agent 类型")
    return validate_user_config_path(Path(os.getenv("USERPROFILE") or Path.home()) / spec["path"])


def _gateway_url(base_url: str, *, openai: bool = False) -> str:
    root = base_url.rstrip("/")
    return f"{root}/v1" if openai else root


def _model(db: Session, model_id: int | None, required_protocol: str) -> UnifiedModel:
    row = db.get(UnifiedModel, model_id) if model_id else None
    if not row or not row.enabled:
        raise ValueError("Agent 主模型必须选择已启用的统一模型")
    if required_protocol not in (row.enabled_protocols_json or []):
        raise ValueError(f"统一模型未启用 Agent 所需协议：{required_protocol}")
    return row


def _openclaw_model(db: Session, model: UnifiedModel) -> dict[str, Any]:
    upstreams = db.scalars(
        select(UpstreamModel)
        .join(UnifiedModelCandidate, UnifiedModelCandidate.upstream_model_id == UpstreamModel.id)
        .where(UnifiedModelCandidate.unified_model_id == model.id, UnifiedModelCandidate.enabled.is_(True))
    ).all()
    context = max((item.context_window or 0 for item in upstreams), default=0) or model.min_context_window or 32768
    max_tokens = max((item.max_output_tokens or 0 for item in upstreams), default=0) or min(8192, context)
    inputs = {capability for item in upstreams for capability in (item.input_capabilities_json or [])}
    return {
        "id": model.name,
        "name": model.name,
        "reasoning": False,
        "input": [item for item in ("text", "image") if item == "text" or "vision" in inputs],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": context,
        "maxTokens": max_tokens,
    }


def _load_json5(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    parsed = json5.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("现有 Agent 配置根节点必须是对象")
    return parsed


def _nested_dict(root: dict[str, Any], key: str) -> dict[str, Any]:
    value = root.get(key)
    if not isinstance(value, dict):
        value = {}
        root[key] = value
    return value


def _merge_env(text: str, updates: dict[str, str | None]) -> str:
    lines = text.splitlines()
    positions: dict[str, int] = {}
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].removeprefix("export ").strip()
        positions[key] = index
    for key, value in updates.items():
        if value is None:
            continue
        rendered = f"{key}={value}"
        if key in positions:
            lines[positions[key]] = rendered
        else:
            lines.append(rendered)
    return "\n".join(lines).rstrip() + "\n"


def agent_content(
    db: Session,
    agent_type: str,
    main_model_id: int | None,
    base_url: str,
    *,
    existing_text: str = "",
    api_token: str | None = None,
) -> str:
    spec = AGENT_SPECS.get(agent_type)
    if not spec:
        raise ValueError("不支持的 Agent 类型")
    model = _model(db, main_model_id, spec["protocol"])
    token = api_token.strip() if isinstance(api_token, str) and api_token.strip() else None

    if agent_type == "codex":
        document = tomlkit.parse(existing_text) if existing_text.strip() else tomlkit.document()
        document["model"] = model.name
        document["model_provider"] = "apiswitch"
        providers = document.get("model_providers")
        if not isinstance(providers, MutableMapping):
            providers = tomlkit.table()
            document["model_providers"] = providers
        provider = providers.get("apiswitch")
        if not isinstance(provider, MutableMapping):
            provider = tomlkit.table()
            providers["apiswitch"] = provider
        provider.update({"name": "APISwitch", "base_url": _gateway_url(base_url, openai=True), "wire_api": "responses", "requires_openai_auth": False})
        if token:
            provider.pop("env_key", None)
            provider["experimental_bearer_token"] = token
        elif not provider.get("experimental_bearer_token"):
            provider["env_key"] = "APISWITCH_API_KEY"
        return tomlkit.dumps(document)

    if agent_type == "opencode":
        document = _load_json5(existing_text)
        document.setdefault("$schema", "https://opencode.ai/config.json")
        providers = _nested_dict(document, "provider")
        provider = providers.get("apiswitch") if isinstance(providers.get("apiswitch"), dict) else {}
        options = provider.get("options") if isinstance(provider.get("options"), dict) else {}
        options["baseURL"] = _gateway_url(base_url, openai=True)
        options["apiKey"] = token or options.get("apiKey") or "{env:APISWITCH_API_KEY}"
        models = provider.get("models") if isinstance(provider.get("models"), dict) else {}
        models[model.name] = {"name": model.name}
        provider.update({"npm": "@ai-sdk/openai-compatible", "name": "APISwitch", "options": options, "models": models})
        providers["apiswitch"] = provider
        document["model"] = f"apiswitch/{model.name}"
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if agent_type == "openclaw":
        document = _load_json5(existing_text)
        models_root = _nested_dict(document, "models")
        models_root["mode"] = "merge"
        providers = _nested_dict(models_root, "providers")
        provider = providers.get("apiswitch") if isinstance(providers.get("apiswitch"), dict) else {}
        prior_models = provider.get("models") if isinstance(provider.get("models"), list) else []
        descriptor = _openclaw_model(db, model)
        provider_models = [item for item in prior_models if isinstance(item, dict) and item.get("id") != model.name]
        provider_models.append(descriptor)
        provider.update({
            "baseUrl": _gateway_url(base_url, openai=True),
            "apiKey": token or provider.get("apiKey") or {"source": "env", "provider": "default", "id": "APISWITCH_API_KEY"},
            "api": "openai-completions",
            "models": provider_models,
        })
        providers["apiswitch"] = provider
        defaults = _nested_dict(_nested_dict(document, "agents"), "defaults")
        primary = defaults.get("model") if isinstance(defaults.get("model"), dict) else {}
        primary["primary"] = f"apiswitch/{model.name}"
        defaults["model"] = primary
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if agent_type == "hermes":
        parsed = yaml.safe_load(existing_text) if existing_text.strip() else {}
        document = parsed if isinstance(parsed, dict) else {}
        previous = document.get("model") if isinstance(document.get("model"), dict) else {}
        document["model"] = {
            **previous,
            "provider": "custom",
            "default": model.name,
            "base_url": _gateway_url(base_url, openai=True),
            "api_mode": "chat_completions",
            "api_key": token or previous.get("api_key") or "",
        }
        return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)

    return _merge_env(existing_text, {
        "GEMINI_API_KEY": token,
        "GOOGLE_GEMINI_BASE_URL": _gateway_url(base_url),
        "GEMINI_MODEL": model.name,
    })


def _redact(content: str, api_token: str | None) -> str:
    redacted = content.replace(api_token, "<已隐藏>") if api_token else content
    redacted = re.sub(
        r'(?im)^(\s*(?:GEMINI_API_KEY|experimental_bearer_token|api_key)\s*[=:]\s*)[^\r\n]*$',
        r"\1<已隐藏>",
        redacted,
    )
    return re.sub(
        r'("apiKey"\s*:\s*)"(?:[^"\\]|\\.)*"',
        r'\1"<已隐藏>"',
        redacted,
    )


def preview_agent_config(
    db: Session,
    agent_type: str,
    main_model_id: int | None,
    base_url: str,
    config_path: str | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    target = validate_user_config_path(Path(config_path)) if config_path else default_agent_path(agent_type)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = agent_content(db, agent_type, main_model_id, base_url, existing_text=existing, api_token=api_token)
    return {
        "agent_type": agent_type,
        "label": AGENT_SPECS[agent_type]["label"],
        "config_path": str(target),
        "language": AGENT_SPECS[agent_type]["language"],
        "content": _redact(content, api_token),
        "token_hint": "客户端 Token 仅写入目标配置且不会进入 APISwitch 数据库；留空时使用现有值或 APISWITCH_API_KEY 环境变量。",
    }


def atomic_write_text(target: Path, content: str) -> Path | None:
    target = validate_user_config_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if target.exists():
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = target.with_name(f"{target.name}.{stamp}.bak")
        shutil.copy2(target, backup)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return backup


def atomic_write_config(target: Path, content: dict[str, Any]) -> Path | None:
    return atomic_write_text(target, json.dumps(content, ensure_ascii=False, indent=2) + "\n")


def write_agent_config(db: Session, row: AgentConfig, base_url: str, api_token: str | None = None) -> Path | None:
    if not row.config_path:
        raise ValueError("Agent 配置路径未设置")
    target = validate_user_config_path(Path(row.config_path))
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = agent_content(db, row.agent_type, row.main_model_id, base_url, existing_text=existing, api_token=api_token)
    backup = atomic_write_text(target, content)
    row.last_written_base_url = base_url
    row.last_backup_path = str(backup) if backup else None
    db.add(row)
    return backup


def restore_agent_config(config_path: str, backup_path: str) -> None:
    target = validate_user_config_path(Path(config_path))
    backup = validate_user_config_path(Path(backup_path))
    if backup.parent != target.parent or not backup.name.startswith(target.name + ".") or not backup.name.endswith(".bak"):
        raise ValueError("备份必须是目标配置的同目录 APISwitch 备份")
    if not backup.is_file():
        raise ValueError("备份文件不存在")
    temporary = target.with_name(f".{target.name}.{os.getpid()}.restore")
    try:
        temporary.write_bytes(backup.read_bytes())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def claude_content(db: Session, model_ids: dict[str, int | None], base_url: str) -> dict[str, Any]:
    ids = [value for value in model_ids.values() if value]
    names = {row.id: row.name for row in db.scalars(select(UnifiedModel).where(UnifiedModel.id.in_(ids), UnifiedModel.enabled.is_(True))).all()} if ids else {}
    if any(value not in names for value in ids):
        raise ValueError("Agent 引用了不存在的统一模型")
    main = names.get(model_ids.get("main_model_id"))
    if not main:
        raise ValueError("Claude Code 主模型必须选择已启用的统一模型")
    env = {"ANTHROPIC_BASE_URL": base_url, "ANTHROPIC_MODEL": main, "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1"}
    optional = {"ANTHROPIC_DEFAULT_OPUS_MODEL": names.get(model_ids.get("opus_model_id")), "ANTHROPIC_DEFAULT_SONNET_MODEL": names.get(model_ids.get("sonnet_model_id")), "ANTHROPIC_DEFAULT_HAIKU_MODEL": names.get(model_ids.get("haiku_model_id"))}
    env.update({key: value for key, value in optional.items() if value})
    return {"$schema": _SCHEMA_URL, "model": main, "env": env}


def write_claude_config(db: Session, row: AgentConfig, base_url: str) -> Path | None:
    if not row.config_path:
        raise ValueError("Claude Code 配置路径未设置")
    content = claude_content(db, {field: getattr(row, field) for field in MODEL_FIELDS}, base_url)
    backup = atomic_write_config(Path(row.config_path), content)
    row.last_written_base_url = base_url
    row.last_backup_path = str(backup) if backup else None
    db.add(row)
    return backup


def refresh_enabled_agent_configs(db: Session, base_url: str) -> int:
    supported = (*AGENT_SPECS.keys(), "claude-code")
    rows = db.scalars(
        select(AgentConfig).where(
            AgentConfig.enabled.is_(True), AgentConfig.agent_type.in_(supported)
        )
    ).all()
    changed = [row for row in rows if row.last_written_base_url != base_url]
    for row in changed:
        if row.agent_type == "claude-code":
            write_claude_config(db, row, base_url)
        elif row.agent_type in AGENT_SPECS:
            write_agent_config(db, row, base_url)
    db.commit()
    return len(changed)


def refresh_enabled_claude_configs(db: Session, base_url: str) -> int:
    """Backward-compatible alias retained for older callers and tests."""
    return refresh_enabled_agent_configs(db, base_url)
