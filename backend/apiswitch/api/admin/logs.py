from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import RequestLog

router = APIRouter(prefix="/api/admin/logs", tags=["Admin - Logs"])


@router.get("")
async def list_logs(db: Session = Depends(get_db), limit: int = 50) -> dict:
    logs = db.scalars(
        select(RequestLog).order_by(RequestLog.started_at.desc()).limit(min(limit, 200))
    ).all()
    return {
        "items": [
            {
                "request_id": log.request_id,
                "started_at": log.started_at.isoformat() + "Z",
                "finished_at": log.finished_at.isoformat() + "Z" if log.finished_at else None,
                "inbound_protocol": log.inbound_protocol,
                "unified_model": log.unified_model,
                "final_provider": log.final_provider,
                "provider_connection_id": log.provider_connection_id,
                "provider_node_id": log.provider_node_id,
                "final_upstream_model": log.final_upstream_model,
                "success": log.success,
                "error_type": log.error_type,
                "error_message": log.error_message,
                "retry_chain": log.retry_chain_json,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "estimated_cost": log.estimated_cost,
                "latency_ms": log.latency_ms,
                "first_token_latency_ms": log.first_token_latency_ms,
                "cache_hit": log.cache_hit,
            }
            for log in logs
        ],
        "total": len(logs),
    }
