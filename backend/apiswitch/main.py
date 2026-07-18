import uvicorn

from apiswitch.config import settings


def _is_loopback_host(host: str) -> bool:
    return host.lower() in {"127.0.0.1", "::1", "localhost"}


def main() -> None:
    if not _is_loopback_host(settings.listen_host) and not settings.admin_auth_enabled:
        raise RuntimeError(
            "Remote listening requires APISWITCH_ADMIN_AUTH_ENABLED=true"
        )
    uvicorn.run(
        "apiswitch.app:app",
        host=settings.listen_host,
        port=settings.port,
        reload=settings.reload,
    )
