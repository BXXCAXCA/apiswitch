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

from apiswitch.db.models import (
    AgentConfig,
    ApiToken,
    ApiTokenUnifiedModel,
    ProviderInstance,
    UnifiedModel,
    UnifiedModelCandidate,
    UpstreamModel,
)
from apiswitch.routing.model_catalog import model_catalog_metadata
from apiswitch.security.tokens import generate_api_token, hash_api_token, token_prefix

MODEL_FIELDS = ("main_model_id", "opus_model_id", "sonnet_model_id", "haiku_model_id")
AGENT_TOKEN_PLACEHOLDER = "ask_agent_key_created_when_written"
_AGENT_TOKEN_PATTERN = re.compile(r"ask_[A-Za-z0-9_-]{8,}")
_SCHEMA_URL = "https://json.schemastore.org/claude-code-settings.json"
AGENT_SPECS: dict[str, dict[str, str]] = {
    "claude-code": {"label": "Claude Code", "path": ".claude/settings.json", "protocol": "anthropic_messages", "language": "json"},
    "codex": {"label": "Codex", "path": ".codex/config.toml", "protocol": "openai_responses", "language": "toml"},
    "opencode": {"label": "OpenCode", "path": ".config/opencode/opencode.json", "protocol": "openai_chat", "language": "json"},
    "openclaw": {"label": "龙虾（OpenClaw）", "path": ".openclaw/openclaw.json", "protocol": "openai_chat", "language": "json"},
    "deepseek-harness": {"label": "DeepSeek Harness", "path": ".dsh/settings.yaml", "protocol": "openai_chat", "language": "yaml"},
    "hermes": {"label": "Hermes Agent", "path": ".hermes/config.yaml", "protocol": "openai_chat", "language": "yaml"},
    "gemini-cli": {"label": "Gemini CLI", "path": ".gemini/.env", "protocol": "gemini_v1beta", "language": "shell"},
    "langcli": {"label": "Langcli", "path": ".langcli/settings.json", "protocol": "openai_chat", "language": "json"},
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


def _selected_models(
    db: Session,
    main_model_id: int | None,
    model_ids: list[int] | None,
    required_protocol: str,
) -> tuple[UnifiedModel, list[UnifiedModel]]:
    main = _model(db, main_model_id, required_protocol)
    ids = list(dict.fromkeys([main.id, *(model_ids or [])]))
    models = [_model(db, model_id, required_protocol) for model_id in ids]
    return main, models


def _openclaw_model(db: Session, model: UnifiedModel) -> dict[str, Any]:
    upstreams = db.scalars(
        select(UpstreamModel)
        .join(UnifiedModelCandidate, UnifiedModelCandidate.upstream_model_id == UpstreamModel.id)
        .where(UnifiedModelCandidate.unified_model_id == model.id, UnifiedModelCandidate.enabled.is_(True))
    ).all()
    context = max((item.context_window or 0 for item in upstreams), default=0) or model.min_context_window or 32768
    max_tokens = max((item.max_output_tokens or 0 for item in upstreams), default=0) or min(8192, context)
    metadata = model_catalog_metadata(db, model)
    return {
        "id": model.name,
        "name": model.name,
        "reasoning": False,
        "input": [item for item in metadata["input_modalities"] if item in {"text", "image"}],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
        "contextWindow": context,
        "maxTokens": max_tokens,
    }


def _callable_agent_models(db: Session, required_protocol: str) -> list[UnifiedModel]:
    """Return enabled unified models with at least one callable upstream route."""
    rows = db.scalars(
        select(UnifiedModel)
        .join(UnifiedModelCandidate, UnifiedModelCandidate.unified_model_id == UnifiedModel.id)
        .join(UpstreamModel, UpstreamModel.id == UnifiedModelCandidate.upstream_model_id)
        .join(ProviderInstance, ProviderInstance.id == UpstreamModel.provider_instance_id)
        .where(
            UnifiedModel.enabled.is_(True),
            UnifiedModelCandidate.enabled.is_(True),
            UpstreamModel.enabled.is_(True),
            UpstreamModel.remote_status != "missing",
            ProviderInstance.enabled.is_(True),
        )
        .distinct()
        .order_by(UnifiedModel.name)
    ).all()
    return [row for row in rows if required_protocol in (row.enabled_protocols_json or [])]


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
    model_ids: list[int] | None = None,
    existing_text: str = "",
    api_token: str | None = None,
) -> str:
    spec = AGENT_SPECS.get(agent_type)
    if not spec:
        raise ValueError("不支持的 Agent 类型")
    model, selected_models = _selected_models(db, main_model_id, model_ids, spec["protocol"])
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
        provider.pop("env_key", None)
        if token:
            provider["experimental_bearer_token"] = token
        elif not provider.get("experimental_bearer_token"):
            provider["experimental_bearer_token"] = AGENT_TOKEN_PLACEHOLDER
        return tomlkit.dumps(document)

    if agent_type == "opencode":
        document = _load_json5(existing_text)
        document.setdefault("$schema", "https://opencode.ai/config.json")
        providers = _nested_dict(document, "provider")
        provider = providers.get("apiswitch") if isinstance(providers.get("apiswitch"), dict) else {}
        options = provider.get("options") if isinstance(provider.get("options"), dict) else {}
        options["baseURL"] = _gateway_url(base_url, openai=True)
        options["apiKey"] = token or options.get("apiKey") or AGENT_TOKEN_PLACEHOLDER
        models = {}
        for selected in selected_models:
            metadata = model_catalog_metadata(db, selected)
            models[selected.name] = {
                "name": selected.name,
                "attachment": "image" in metadata["input_modalities"],
                "tool_call": "tools" in metadata["capabilities"],
                "modalities": metadata["modalities"],
            }
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
        provider_models = [_openclaw_model(db, selected) for selected in selected_models]
        provider.update({
            "baseUrl": _gateway_url(base_url, openai=True),
            "apiKey": token or (provider.get("apiKey") if isinstance(provider.get("apiKey"), str) else None) or AGENT_TOKEN_PLACEHOLDER,
            "api": "openai-completions",
            "models": provider_models,
        })
        providers["apiswitch"] = provider
        defaults = _nested_dict(_nested_dict(document, "agents"), "defaults")
        primary = defaults.get("model") if isinstance(defaults.get("model"), dict) else {}
        primary["primary"] = f"apiswitch/{model.name}"
        defaults["model"] = primary
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

    if agent_type == "deepseek-harness":
        parsed = yaml.safe_load(existing_text) if existing_text.strip() else {}
        document = parsed if isinstance(parsed, dict) else {}
        llm = document.get("llm-pi-ai") if isinstance(document.get("llm-pi-ai"), dict) else {}
        providers = llm.get("providers") if isinstance(llm.get("providers"), dict) else {}
        provider = providers.get("apiswitch") if isinstance(providers.get("apiswitch"), dict) else {}
        prior_models = provider.get("models") if isinstance(provider.get("models"), list) else []
        existing_by_id = {
            item.get("id"): item
            for item in prior_models
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        provider_models=[]
        for catalog_model in selected_models:
            base_descriptor = _openclaw_model(db, catalog_model)
            existing_descriptor = existing_by_id.get(catalog_model.name, {})
            provider_models.append({
                **existing_descriptor,
                "id": catalog_model.name,
                "name": existing_descriptor.get("name") or catalog_model.name,
                # Harness intentionally ignores modality extensions returned by
                # OpenAI model discovery.  Each entry therefore needs an input
                # declaration before read_image will attach an image.
                "input": [item for item in base_descriptor["input"] if item in {"text", "image"}],
                "contextWindow": existing_descriptor.get("contextWindow") or base_descriptor["contextWindow"],
                "maxTokens": existing_descriptor.get("maxTokens") or base_descriptor["maxTokens"],
            })
        common_inputs = set(provider_models[0]["input"])
        for descriptor in provider_models[1:]:common_inputs.intersection_update(descriptor["input"])
        headers = provider.get("headers") if isinstance(provider.get("headers"), dict) else {}
        existing_auth = headers.get("Authorization") if isinstance(headers.get("Authorization"), str) else None
        headers["Authorization"] = f"Bearer {token}" if token else existing_auth or f"Bearer {AGENT_TOKEN_PLACEHOLDER}"
        provider.pop("apiKeyEnv", None)
        provider.update({
            "displayName": "APISwitch",
            "api": "openai-completions",
            "baseURL": _gateway_url(base_url, openai=True),
            # This fallback survives Harness's "fetch models" action, which
            # recreates catalog rows without their per-model modality fields.
            "defaultInput": [item for item in ("text", "image") if item in common_inputs],
            "headers": headers,
            "models": provider_models,
        })
        providers["apiswitch"] = provider
        llm["providers"] = providers
        document["llm-pi-ai"] = llm
        previous_default = document.get("agent-default-model") if isinstance(document.get("agent-default-model"), dict) else {}
        document["agent-default-model"] = {**previous_default, "provider": "apiswitch", "model": model.name}
        return yaml.safe_dump(document, allow_unicode=True, sort_keys=False)

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

    if agent_type == "langcli":
        document = _load_json5(existing_text)
        env_value = document.get("env")
        if env_value is not None and not isinstance(env_value, dict):
            raise ValueError("Langcli 现有 env 配置必须是对象")
        env = dict(env_value or {})
        env["APISWITCH_API_KEY"] = token or env.get("APISWITCH_API_KEY") or AGENT_TOKEN_PLACEHOLDER
        document["env"] = env

        providers_value = document.get("modelProviders")
        if providers_value is not None and not isinstance(providers_value, dict):
            raise ValueError("Langcli 现有 modelProviders 配置必须是对象")
        providers = dict(providers_value or {})
        openai_value = providers.get("openai")
        if openai_value is not None and not isinstance(openai_value, list):
            raise ValueError("Langcli modelProviders.openai 必须是数组")
        models = [
            item
            for item in (openai_value or [])
            if not isinstance(item, dict) or item.get("description") != "APISwitch unified model"
        ]
        for selected in selected_models:
            models.append({
                "id": selected.name,
                "name": selected.name,
                "description": "APISwitch unified model",
                "envKey": "APISWITCH_API_KEY",
                "baseUrl": _gateway_url(base_url, openai=True),
            })
        providers["openai"] = models
        document["modelProviders"] = providers
        document["model"] = f"custom:{model.name}"
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"

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
        r'("(?:apiKey|APISWITCH_API_KEY|ANTHROPIC_AUTH_TOKEN)"\s*:\s*)"(?:[^"\\]|\\.)*"',
        r'\1"<已隐藏>"',
        redacted,
    )


def preview_agent_config(
    db: Session,
    agent_type: str,
    main_model_id: int | None,
    base_url: str,
    config_path: str | None = None,
    model_ids: list[int] | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    target = validate_user_config_path(Path(config_path)) if config_path else default_agent_path(agent_type)
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = agent_content(
        db,
        agent_type,
        main_model_id,
        base_url,
        model_ids=model_ids,
        existing_text=existing,
        api_token=api_token,
    )
    return {
        "agent_type": agent_type,
        "label": AGENT_SPECS[agent_type]["label"],
        "config_path": str(target),
        "language": AGENT_SPECS[agent_type]["language"],
        "content": content,
        "token_hint": "可自动创建独立 API Key，也可选择已有 Key；明文直接写入此配置，不依赖系统环境变量。",
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


def validate_agent_content(agent_type: str, content: str) -> None:
    """Reject malformed user-edited content before replacing a working config."""
    if agent_type == "codex":
        tomlkit.parse(content)
    elif agent_type in {"opencode", "openclaw", "langcli", "claude-code"}:
        _load_json5(content)
    elif agent_type in {"deepseek-harness", "hermes"}:
        parsed = yaml.safe_load(content)
        if not isinstance(parsed, dict):
            raise ValueError("Agent 配置根节点必须是对象")
    elif agent_type == "gemini-cli" and not content.strip():
        raise ValueError("Gemini CLI 配置不能为空")


def write_agent_config(
    db: Session,
    row: AgentConfig,
    base_url: str,
    api_token: str | None = None,
    content_override: str | None = None,
) -> Path | None:
    if not row.config_path:
        raise ValueError("Agent 配置路径未设置")
    target = validate_user_config_path(Path(row.config_path))
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = content_override if content_override is not None else agent_content(
        db,
        row.agent_type,
        row.main_model_id,
        base_url,
        model_ids=row.model_ids_json or None,
        existing_text=existing,
        api_token=api_token,
    )
    validate_agent_content(row.agent_type, content)
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


def claude_content(
    db: Session,
    model_ids: dict[str, int | None],
    base_url: str,
    *,
    existing_text: str = "",
    api_token: str | None = None,
) -> dict[str, Any]:
    """Merge APISwitch routing values into a Claude Code settings document."""
    ids = [value for value in model_ids.values() if value]
    names: dict[int, str] = {}
    for model_id in ids:
        row = _model(db, model_id, "anthropic_messages")
        names[row.id] = row.name
    if any(value not in names for value in ids):
        raise ValueError("Agent 引用了不存在的统一模型")
    main = names.get(model_ids.get("main_model_id"))
    if not main:
        raise ValueError("Claude Code 主模型必须选择已启用的统一模型")

    document = _load_json5(existing_text)
    document.setdefault("$schema", _SCHEMA_URL)
    document["model"] = main
    env_value = document.get("env")
    if env_value is not None and not isinstance(env_value, dict):
        raise ValueError("Claude Code 现有 env 配置必须是对象")
    env = dict(env_value or {})
    env.update({
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_MODEL": main,
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY": "1",
    })
    optional = {
        "ANTHROPIC_DEFAULT_OPUS_MODEL": names.get(model_ids.get("opus_model_id")),
        "ANTHROPIC_DEFAULT_SONNET_MODEL": names.get(model_ids.get("sonnet_model_id")),
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": names.get(model_ids.get("haiku_model_id")),
    }
    for key, value in optional.items():
        if value:
            env[key] = value
        else:
            env.pop(key, None)
    token = api_token.strip() if isinstance(api_token, str) and api_token.strip() else None
    if token:
        env["ANTHROPIC_AUTH_TOKEN"] = token
    document["env"] = env
    return document


def write_claude_config(
    db: Session,
    row: AgentConfig,
    base_url: str,
    api_token: str | None = None,
    content_override: str | None = None,
) -> Path | None:
    if not row.config_path:
        raise ValueError("Claude Code 配置路径未设置")
    target = validate_user_config_path(Path(row.config_path))
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    content = _load_json5(content_override) if content_override is not None else claude_content(
        db,
        {field: getattr(row, field) for field in MODEL_FIELDS},
        base_url,
        existing_text=existing,
        api_token=api_token,
    )
    backup = atomic_write_config(target, content)
    row.last_written_base_url = base_url
    row.last_backup_path = str(backup) if backup else None
    db.add(row)
    return backup


def _refresh_model_ids(db: Session, row: AgentConfig) -> list[int]:
    """Upgrade legacy rows while preserving Harness's former all-model behavior."""
    configured = row.model_ids_json or []
    values = [row.main_model_id, *configured]
    values.extend(getattr(row, field) for field in MODEL_FIELDS[1:])
    if not configured and row.agent_type == "deepseek-harness":
        values.extend(model.id for model in _callable_agent_models(db, AGENT_SPECS[row.agent_type]["protocol"]))
    return list(dict.fromkeys(value for value in values if isinstance(value, int)))


def _config_contains_token(row: AgentConfig, token: ApiToken) -> bool:
    if not row.config_path:
        return False
    target = Path(row.config_path)
    if not target.is_file():
        return False
    try:
        content = target.read_text(encoding="utf-8")
    except OSError:
        return False
    return any(hash_api_token(value) == token.token_hash for value in _AGENT_TOKEN_PATTERN.findall(content))


def _ensure_refresh_token(db: Session, row: AgentConfig, model_ids: list[int]) -> str | None:
    """Create or recover the plaintext config key during automatic port refresh."""
    token = db.get(ApiToken, row.api_token_id) if row.api_token_id else None
    plain: str | None = None
    manual = (row.api_token_mode or "auto") == "manual"
    if manual and token is None:
        raise ValueError("手动选择的 Agent API Key 已不存在，请重新选择")
    if manual and token and not _config_contains_token(row, token):
        raise ValueError("Agent 配置中缺少手动选择的 API Key 明文，请重新输入并写入")
    if token is None:
        plain = generate_api_token()
        token = ApiToken(
            name=f"Agent · {AGENT_SPECS[row.agent_type]['label']}",
            token_prefix=token_prefix(plain),
            token_hash=hash_api_token(plain),
            scopes_json=["gateway:invoke"],
            enabled=True,
        )
        db.add(token)
        db.flush()
        row.api_token_id = token.id
    elif not manual and not _config_contains_token(row, token):
        # Only the hash is retained in the database. If the local plaintext was
        # removed, rotate to a recoverable key instead of writing a placeholder.
        plain = generate_api_token()
        token.token_prefix = token_prefix(plain)
        token.token_hash = hash_api_token(plain)
        token.last_used_at = None
        token.enabled = True

    if manual:
        allowed = set(db.scalars(
            select(ApiTokenUnifiedModel.unified_model_id).where(ApiTokenUnifiedModel.api_token_id == token.id)
        ).all())
        missing = [model_id for model_id in model_ids if model_id not in allowed]
        if missing:
            raise ValueError("手动选择的 API Key 未授权当前 Agent 的全部模型")
    else:
        db.query(ApiTokenUnifiedModel).filter(ApiTokenUnifiedModel.api_token_id == token.id).delete(
            synchronize_session=False
        )
        for model_id in model_ids:
            db.add(ApiTokenUnifiedModel(api_token_id=token.id, unified_model_id=model_id))
    return plain


def refresh_enabled_agent_configs(db: Session, base_url: str) -> int:
    rows = db.scalars(
        select(AgentConfig).where(
            AgentConfig.enabled.is_(True), AgentConfig.agent_type.in_(tuple(AGENT_SPECS))
        )
    ).all()
    changed = [row for row in rows if row.last_written_base_url != base_url]
    for row in changed:
        model_ids = _refresh_model_ids(db, row)
        row.model_ids_json = model_ids
        api_token = _ensure_refresh_token(db, row, model_ids)
        if row.agent_type == "claude-code":
            write_claude_config(db, row, base_url, api_token=api_token)
        elif row.agent_type in AGENT_SPECS:
            write_agent_config(db, row, base_url, api_token=api_token)
    db.commit()
    return len(changed)


def refresh_enabled_claude_configs(db: Session, base_url: str) -> int:
    """Backward-compatible alias retained for older callers and tests."""
    return refresh_enabled_agent_configs(db, base_url)
