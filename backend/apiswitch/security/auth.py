from __future__ import annotations

import hmac
import ipaddress
from datetime import datetime

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from apiswitch.config import settings
from apiswitch.db.models import ApiToken
from apiswitch.security.tokens import hash_api_token


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None


def require_admin_access(
    request: Request,
    authorization: str | None,
    db: Session | None,
) -> None:
    """Protect admin routes with loopback-only access or a scoped bearer token.

    Local-first installations work without another bootstrap credential.  A
    remote client is always rejected unless explicit admin authentication is
    enabled.  When enabled, callers use either the operator bootstrap token or
    a database API token carrying ``admin:access``.
    """
    if not settings.admin_auth_enabled:
        if _is_loopback(request.client.host if request.client else None):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"type": "admin_local_only", "message": "Admin API is restricted to loopback clients"},
        )

    raw_token = _extract_bearer_token(authorization)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing admin Bearer token")
    if settings.admin_token and hmac.compare_digest(raw_token, settings.admin_token):
        return
    # The injected Session dependency is replaced in api.deps to avoid a
    # circular import while keeping this policy module usable by the app.
    if db is not None:
        api_token = db.scalar(select(ApiToken).where(ApiToken.token_hash == hash_api_token(raw_token)).limit(1))
        scopes = (api_token.scopes_json or {}).get("scopes", []) if api_token else []
        if (
            api_token
            and api_token.enabled
            and (api_token.expires_at is None or api_token.expires_at > datetime.utcnow())
            and "admin:access" in scopes
        ):
            api_token.last_used_at = datetime.utcnow()
            db.commit()
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin token requires admin:access scope")


def require_gateway_token(request: Request) -> None:
    """Compatibility hook for callers still importing the old dependency."""
    if not settings.auth_enabled:
        return
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
