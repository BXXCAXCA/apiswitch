from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import CircuitBreakerModel, RequestLog

router = APIRouter(prefix="/api/admin/dashboard", tags=["Admin - Dashboard"])


@router.get("/summary")
async def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    requests_total = db.scalar(select(func.count(RequestLog.id))) or 0
    success_total = db.scalar(select(func.count(RequestLog.id)).where(RequestLog.success.is_(True))) or 0
    failure_total = max(requests_total - success_total, 0)
    average_latency_ms = db.scalar(select(func.avg(RequestLog.latency_ms))) or 0
    first_token_latency_ms = db.scalar(select(func.avg(RequestLog.first_token_latency_ms))) or 0
    open_circuit_breakers = (
        db.scalar(select(func.count(CircuitBreakerModel.id)).where(CircuitBreakerModel.state == "open")) or 0
    )
    recent_errors = db.scalars(
        select(RequestLog.error_message)
        .where(RequestLog.success.is_(False), RequestLog.error_message.is_not(None))
        .order_by(RequestLog.started_at.desc())
        .limit(5)
    ).all()

    success_rate = (success_total / requests_total) if requests_total else 1.0
    failure_rate = (failure_total / requests_total) if requests_total else 0.0

    return {
        "requests_total": requests_total,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "average_latency_ms": round(float(average_latency_ms), 2),
        "first_token_latency_ms": round(float(first_token_latency_ms), 2),
        "open_circuit_breakers": open_circuit_breakers,
        "monthly_budget_used": 0,
        "monthly_budget_limit": 0,
        "recent_errors": recent_errors,
    }
