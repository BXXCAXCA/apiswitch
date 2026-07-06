from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import AgentConfig
from apiswitch.schemas.agents import AgentConfigCheckResult, AgentConfigCreate, AgentConfigRead, AgentConfigUpdate

router = APIRouter(prefix="/api/admin/agents", tags=["Admin - Agents"])


def _get_agent(db: Session, agent_id: int) -> AgentConfig:
    agent = db.get(AgentConfig, agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent config not found")
    return agent


def _settings(agent: AgentConfig) -> dict:
    return agent.settings_json or {}


def _is_mock_path(path: str | None) -> bool:
    return bool(path and path.startswith("mock://"))


def _path_exists(path: str | None) -> bool:
    if not path:
        return False
    if _is_mock_path(path):
        return True
    try:
        return Path(path).expanduser().exists()
    except Exception:  # noqa: BLE001
        return False


def _to_read(agent: AgentConfig) -> AgentConfigRead:
    settings = _settings(agent)
    return AgentConfigRead(
        id=agent.id,
        agent_type=agent.agent_type,
        config_path=agent.config_path,
        last_backup_path=agent.last_backup_path,
        enabled=bool(settings.get("enabled", True)),
        notes=settings.get("notes"),
        settings={key: value for key, value in settings.items() if key not in {"enabled", "notes"}},
        config_exists=_path_exists(agent.config_path),
        backup_configured=bool(agent.last_backup_path),
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def _settings_from_payload(enabled: bool | None, notes: str | None, settings: dict | None) -> dict:
    data = dict(settings or {})
    if enabled is not None:
        data["enabled"] = enabled
    if notes is not None:
        data["notes"] = notes
    return data


@router.get("")
async def list_agents(db: Session = Depends(get_db)) -> list[AgentConfigRead]:
    agents = db.scalars(select(AgentConfig).order_by(AgentConfig.id.desc())).all()
    return [_to_read(agent) for agent in agents]


@router.post("")
async def create_agent(payload: AgentConfigCreate, db: Session = Depends(get_db)) -> AgentConfigRead:
    agent = AgentConfig(
        agent_type=payload.agent_type,
        config_path=payload.config_path,
        last_backup_path=payload.last_backup_path,
        settings_json=_settings_from_payload(payload.enabled, payload.notes, payload.settings),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _to_read(agent)


@router.patch("/{agent_id}")
async def update_agent(
    agent_id: int,
    payload: AgentConfigUpdate,
    db: Session = Depends(get_db),
) -> AgentConfigRead:
    agent = _get_agent(db, agent_id)
    data = payload.model_dump(exclude_unset=True)
    settings = _settings(agent)
    if "enabled" in data or "notes" in data or "settings" in data:
        settings.update(_settings_from_payload(data.pop("enabled", None), data.pop("notes", None), data.pop("settings", None)))
        agent.settings_json = settings
    for key, value in data.items():
        setattr(agent, key, value)
    db.commit()
    db.refresh(agent)
    return _to_read(agent)


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    agent = _get_agent(db, agent_id)
    db.delete(agent)
    db.commit()
    return {"deleted": True}


@router.post("/{agent_id}/check")
async def check_agent(agent_id: int, db: Session = Depends(get_db)) -> AgentConfigCheckResult:
    agent = _get_agent(db, agent_id)
    exists = _path_exists(agent.config_path)
    if exists:
        return AgentConfigCheckResult(ok=True, message="Agent config path is available", config_exists=True)
    return AgentConfigCheckResult(ok=False, message="Agent config path does not exist", config_exists=False)
