import uvicorn

from apiswitch.config import settings


def main() -> None:
    uvicorn.run(
        "apiswitch.app:app",
        host=settings.listen_host,
        port=settings.port,
        reload=settings.reload,
    )
