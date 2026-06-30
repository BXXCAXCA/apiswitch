from fastapi import APIRouter

from apiswitch.schemas.providers import ProviderCreate, ProviderRead

router = APIRouter(prefix="/api/admin/providers", tags=["Admin - Providers"])

MOCK_PROVIDERS: list[ProviderRead] = [
    ProviderRead(
        id=1,
        name="mock-main",
        type="mock",
        base_url="mock://local",
        enabled=True,
        timeout_seconds=120,
        proxy_type=None,
        proxy_url=None,
    )
]


@router.get("")
async def list_providers() -> list[ProviderRead]:
    return MOCK_PROVIDERS


@router.post("")
async def create_provider(payload: ProviderCreate) -> ProviderRead:
    provider = ProviderRead(id=len(MOCK_PROVIDERS) + 1, **payload.model_dump())
    MOCK_PROVIDERS.append(provider)
    return provider
