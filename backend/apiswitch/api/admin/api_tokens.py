from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.api.deps import get_db
from apiswitch.db.models import ApiToken
from apiswitch.schemas.api_tokens import ApiTokenCreate, ApiTokenCreated, ApiTokenRead, ApiTokenUpdate
from apiswitch.security.tokens import generate_api_token, hash_api_token, token_prefix

router = APIRouter(prefix="/api/admin/tokens", tags=["Admin - API Tokens"])


def _scopes(value: dict | None) -> list[str]:
    if not value:
        return []
    scopes = value.get("scopes", [])
    return scopes if isinstance(scopes, list) else []


def _get_token(db: Session, token_id: int) -> ApiToken:
    api_token = db.get(ApiToken, token_id)
    if api_token is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    return api_token


def _to_read(api_token: ApiToken) -> ApiTokenRead:
    return ApiTokenRead(
        id=api_token.id,
        name=api_token.name,
        token_prefix=api_token.token_prefix,
        enabled=api_token.enabled,
        scopes=_scopes(api_token.scopes_json),
        expires_at=api_token.expires_at,
        last_used_at=api_token.last_used_at,
        created_at=api_token.created_at,
        updated_at=api_token.updated_at,
    )


@router.get("")
async def list_api_tokens(db: Session = Depends(get_db)) -> list[ApiTokenRead]:
    tokens = db.scalars(select(ApiToken).order_by(ApiToken.id.desc())).all()
    return [_to_read(api_token) for api_token in tokens]


@router.post("")
async def create_api_token(payload: ApiTokenCreate, db: Session = Depends(get_db)) -> ApiTokenCreated:
    raw_token = generate_api_token()
    api_token = ApiToken(
        name=payload.name,
        token_prefix=token_prefix(raw_token),
        token_hash=hash_api_token(raw_token),
        enabled=True,
        scopes_json={"scopes": payload.scopes},
        expires_at=payload.expires_at,
    )
    db.add(api_token)
    db.commit()
    db.refresh(api_token)
    return ApiTokenCreated(**_to_read(api_token).model_dump(), token=raw_token)


@router.patch("/{token_id}")
async def update_api_token(
    token_id: int,
    payload: ApiTokenUpdate,
    db: Session = Depends(get_db),
) -> ApiTokenRead:
    api_token = _get_token(db, token_id)
    data = payload.model_dump(exclude_unset=True)
    if "scopes" in data:
        api_token.scopes_json = {"scopes": data.pop("scopes")}
    for key, value in data.items():
        setattr(api_token, key, value)
    db.commit()
    db.refresh(api_token)
    return _to_read(api_token)


@router.delete("/{token_id}")
async def delete_api_token(token_id: int, db: Session = Depends(get_db)) -> dict[str, bool]:
    api_token = _get_token(db, token_id)
    db.delete(api_token)
    db.commit()
    return {"deleted": True}
