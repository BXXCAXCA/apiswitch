from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import SessionAffinity, UnifiedModel

DEFAULT_AFFINITY_TTL_HOURS = 24


def _storage_key(unified_model_name: str, session_key: str) -> str:
    return f"{unified_model_name}:{session_key.strip()}"


def get_affinity_candidate_id(
    db: Session,
    unified_model: UnifiedModel,
    session_key: str | None,
    now: datetime | None = None,
) -> int | None:
    if not session_key or not session_key.strip():
        return None
    current = now or datetime.utcnow()
    item = db.scalar(
        select(SessionAffinity).where(
            SessionAffinity.session_key == _storage_key(unified_model.name, session_key),
            SessionAffinity.unified_model_id == unified_model.id,
        )
    )
    if item is None:
        return None
    if item.expires_at is not None and item.expires_at <= current:
        db.delete(item)
        db.flush()
        return None
    item.last_used_at = current
    return item.candidate_id


def record_session_affinity(
    db: Session,
    unified_model_name: str,
    session_key: str | None,
    candidate_id: int,
    provider_connection_id: int | None = None,
    ttl_hours: int = DEFAULT_AFFINITY_TTL_HOURS,
) -> None:
    if not session_key or not session_key.strip():
        return
    unified_model = db.scalar(select(UnifiedModel).where(UnifiedModel.name == unified_model_name))
    if unified_model is None:
        return
    key = _storage_key(unified_model_name, session_key)
    item = db.scalar(select(SessionAffinity).where(SessionAffinity.session_key == key))
    now = datetime.utcnow()
    if item is None:
        item = SessionAffinity(
            session_key=key,
            unified_model_id=unified_model.id,
            candidate_id=candidate_id,
            provider_connection_id=provider_connection_id,
            last_used_at=now,
            expires_at=now + timedelta(hours=ttl_hours),
        )
        db.add(item)
    else:
        item.unified_model_id = unified_model.id
        item.candidate_id = candidate_id
        item.provider_connection_id = provider_connection_id
        item.last_used_at = now
        item.expires_at = now + timedelta(hours=ttl_hours)
