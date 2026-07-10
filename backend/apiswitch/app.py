from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apiswitch import __version__
from apiswitch.api.admin import (
    accounting,
    agents,
    api_tokens,
    budgets,
    dashboard,
    logs,
    provider_catalog,
    provider_connections,
    providers,
    router_health,
    settings as admin_settings,
    unified_models,
    webdav,
)
from apiswitch.api.gateway import chat_completions, embeddings, gemini_v1beta, messages, models, responses
from apiswitch.db.bootstrap import init_database


def create_app() -> FastAPI:
    init_database()

    app = FastAPI(
        title="APISwitch",
        version=__version__,
        description="Local-first AI API gateway, model router, and control panel.",
        openapi_tags=[
            {"name": "System", "description": "Runtime and health endpoints."},
            {"name": "Gateway - OpenAI Chat", "description": "OpenAI Chat Completions compatible API."},
            {"name": "Gateway - OpenAI Responses", "description": "OpenAI Responses compatible API."},
            {"name": "Gateway - Anthropic Messages", "description": "Anthropic Messages compatible API."},
            {"name": "Gateway - Embeddings", "description": "OpenAI-compatible Embeddings API."},
            {"name": "Gateway - Gemini v1beta", "description": "Gemini generateContent compatibility API."},
            {"name": "Gateway - Models", "description": "Gateway-visible model listing."},
            {"name": "Admin - Dashboard", "description": "Dashboard metrics for the Web UI."},
            {"name": "Admin - Providers", "description": "Provider management and catalog."},
            {
                "name": "Admin - Provider Connections",
                "description": "Multi-account credentials and provider node management.",
            },
            {"name": "Admin - Accounting", "description": "Pricing, quota snapshots, and usage history."},
            {"name": "Admin - Unified Models", "description": "Unified model management."},
            {"name": "Admin - Router Health", "description": "Candidate scoring and health state."},
            {"name": "Admin - Logs", "description": "Request logs and statistics."},
            {"name": "Admin - API Tokens", "description": "Gateway API token management."},
            {"name": "Admin - Budgets", "description": "Budget limits and spend tracking."},
            {"name": "Admin - WebDAV", "description": "WebDAV sync profile management."},
            {"name": "Admin - Agents", "description": "Local Agent config management."},
            {"name": "Admin - Settings", "description": "System settings."},
        ],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["System"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "apiswitch", "version": __version__}

    app.include_router(chat_completions.router)
    app.include_router(responses.router)
    app.include_router(messages.router)
    app.include_router(embeddings.router)
    app.include_router(gemini_v1beta.router)
    app.include_router(models.router)
    app.include_router(dashboard.router)
    app.include_router(provider_catalog.router)
    app.include_router(providers.router)
    app.include_router(provider_connections.router)
    app.include_router(accounting.router)
    app.include_router(unified_models.router)
    app.include_router(router_health.router)
    app.include_router(logs.router)
    app.include_router(api_tokens.router)
    app.include_router(budgets.router)
    app.include_router(webdav.router)
    app.include_router(agents.router)
    app.include_router(admin_settings.router)
    return app


app = create_app()
