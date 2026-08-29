from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from merchantos_api.routers.dashboard import router as dashboard_router
from merchantos_api.routers.demo import router as demo_router
from merchantos_api.routers.health import router as health_router
from merchantos_api.routers.validation import router as validation_router
from merchantos_api.routers.webhooks import router as webhooks_router
from merchantos_api.theater import router as theater_router
from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    settings: Settings | None = None,
    trade_ledger: TradeLedger | None = None,
) -> FastAPI:
    """Create and configure MerchantOS FastAPI application instance."""
    app_instance = FastAPI(
        title="MerchantOS AI API",
        version="0.1.0",
        description="Review-gated commerce intelligence and adapter engine",
    )

    app_instance.state.settings = settings
    app_instance.state.trade_ledger = trade_ledger

    if STATIC_DIR.exists():
        app_instance.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app_instance.include_router(dashboard_router)
    app_instance.include_router(demo_router)
    app_instance.include_router(theater_router)
    app_instance.include_router(validation_router)
    app_instance.include_router(health_router)
    app_instance.include_router(webhooks_router)

    return app_instance


app = create_app()

