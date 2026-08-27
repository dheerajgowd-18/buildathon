"""FastAPI application factory for MerchantOS AI."""

from fastapi import FastAPI

from merchantos_api.routers.health import router as health_router
from merchantos_api.routers.webhooks import router as webhooks_router
from merchantos_core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure MerchantOS FastAPI application instance."""
    app_instance = FastAPI(
        title="MerchantOS AI API",
        version="0.1.0",
        description="Review-gated commerce intelligence and adapter engine",
    )

    app_instance.state.settings = settings

    app_instance.include_router(health_router)
    app_instance.include_router(webhooks_router)

    return app_instance


app = create_app()
