from collections.abc import Generator
from datetime import datetime

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.db.models import ApiToken, SystemSetting
from apiswitch.db.session import SessionLocal
from apiswitch.security.auth import require_admin_access as _require_admin_access
from apiswitch.security.tokens import hash_api_token


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin_access(
    request: Request,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> None:
    _require_admin_access(request=request, authorization=authorization, db=db)


def _extract_gateway_token(
    authorization: str | None,
    x_api_key: str | None = None,
    x_goog_api_key: str | None = None,
    query_key: str | None = None,
) -> str:
    bearer: str | None = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"type": "invalid_authorization_header", "message": "Expected Authorization: Bearer <token>"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        bearer = token
    candidates=[value.strip() for value in (bearer,x_api_key,x_goog_api_key,query_key) if value and value.strip()]
    if not candidates:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "missing_api_token", "message": "Missing client API token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if any(value!=candidates[0] for value in candidates[1:]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type":"conflicting_api_tokens","message":"Multiple client token headers contain different values"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return candidates[0]


def authenticate_gateway_token(
    db: Session,
    authorization: str | None,
    x_api_key: str | None = None,
    x_goog_api_key: str | None = None,
    query_key: str | None = None,
) -> ApiToken:
    """Validate one client token for both HTTP and WebSocket gateway entrypoints."""
    gateway_setting = db.get(SystemSetting, "gateway_enabled")
    if gateway_setting is not None and gateway_setting.value_json is not True:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "type": "gateway_disabled",
                "message": "网关已在系统设置中停用",
                "stage": "gateway_switch",
            },
        )
    raw_token = _extract_gateway_token(authorization,x_api_key,x_goog_api_key,query_key)
    api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw_token)).limit(1))
    now = datetime.utcnow()
    if api_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"type": "invalid_api_token", "message": "客户端 Token 无效。请在 APISwitch → API Token 中创建或重置 Token；供应商 API Key 不能用于网关鉴权"},
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
    raw_scopes = api_token.scopes_json or []
    scopes = raw_scopes.get("scopes", []) if isinstance(raw_scopes, dict) else raw_scopes
    if "gateway:invoke" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "insufficient_scope", "message": "API token requires gateway:invoke scope"},
        )
    api_token.last_used_at = now
    db.commit()
    db.refresh(api_token)
    return api_token


def require_gateway_token(
    request: Request,
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None,alias="x-api-key"),
    x_goog_api_key: str | None = Header(default=None,alias="x-goog-api-key"),
    db: Session = Depends(get_db),
) -> ApiToken:
    query_key=request.query_params.get("key") if request.url.path.startswith("/v1beta/") else None
    return authenticate_gateway_token(db,authorization,x_api_key,x_goog_api_key,query_key)
