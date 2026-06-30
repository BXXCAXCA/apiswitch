from fastapi import APIRouter

router = APIRouter(prefix="/api/admin/logs", tags=["Admin - Logs"])


@router.get("")
async def list_logs() -> dict:
    return {
        "items": [
            {
                "request_id": "req_mock_001",
                "started_at": "2026-06-30T00:00:00Z",
                "inbound_protocol": "openai_chat",
                "unified_model": "code-best",
                "final_provider": "mock-main",
                "final_upstream_model": "mock-chat",
                "success": True,
                "latency_ms": 42,
                "cache_hit": False,
            }
        ],
        "total": 1,
    }
