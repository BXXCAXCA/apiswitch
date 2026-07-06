from collections.abc import Generator
from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import ApiToken
from apiswitch.db.session import SessionLocal
from apiswitch.security.tokens import hash_api_token


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "missing_api_token", "message": "Missing Authorization bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_authorization_header", "message": "Expected Authorization: Bearer <token>"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def require_gateway_token(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> ApiToken:
    raw_token = _extract_bearer_token(authorization)
    api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw_token)).limit(1))
    now = datetime.utcnow()
    if api_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_api_token", "message": "API token is invalid"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not api_token.enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "api_token_disabled", "message": "API token is disabled"},
        )
    if api_token.expires_at and api_token.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "api_token_expired", "message": "API token is expired"},
        )
    scopes = (api_token.scopes_json or {}).get("scopes", [])
    if "gateway:invoke" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "insufficient_scope", "message": "API token requires gateway:invoke scope"},
        )
    api_token.last_used_at = now
    db.commit()
    db.refresh(api_token)
    return api_token
