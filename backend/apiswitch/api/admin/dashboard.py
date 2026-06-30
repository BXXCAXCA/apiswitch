from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/dashboard", tags=["Admin - Dashboard"])


@router.get("/summary")
async def dashboard_summary() -> dict:
    return {
        "requests_total": 128,
        "success_rate": 0.982,
        "failure_rate": 0.018,
        "average_latency_ms": 842,
        "first_token_latency_ms": 391,
        "open_circuit_breakers": 0,
        "monthly_budget_used": 12.5,
        "monthly_budget_limit": 50,
        "recent_errors": [],
    }
