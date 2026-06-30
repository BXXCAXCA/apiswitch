from fastapi import APIRouter

from apiswitch.schemas.unified_models import UnifiedModelCreate, UnifiedModelRead

router = APIRouter(prefix="/api/admin/unified-models", tags=["Admin - Unified Models"])

MOCK_UNIFIED_MODELS: list[UnifiedModelRead] = [
    UnifiedModelRead(
        id=1,
        name="code-best",
        description="Mock coding model route",
        enabled=True,
        capabilities=["text", "tools", "files"],
        candidates=[{"provider": "mock-main", "upstream_model": "mock-chat", "priority": 100}],
    )
]


@router.get("")
async def list_unified_models() -> list[UnifiedModelRead]:
    return MOCK_UNIFIED_MODELS


@router.post("")
async def create_unified_model(payload: UnifiedModelCreate) -> UnifiedModelRead:
    model = UnifiedModelRead(id=len(MOCK_UNIFIED_MODELS) + 1, candidates=[], **payload.model_dump())
    MOCK_UNIFIED_MODELS.append(model)
    return model
