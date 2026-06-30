from fastapi import HTTPException, Request, status

from apiswitch.config import settings


def require_gateway_token(request: Request) -> None:
    """Stage-1 auth hook.

    Local development can keep auth disabled. Later stages will validate admin
    API tokens and enforce auth when listening on non-local addresses.
    """
    if not settings.auth_enabled:
        return
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token")
