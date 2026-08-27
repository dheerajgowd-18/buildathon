"""Health check endpoint."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from merchantos_api.deps import get_settings
from merchantos_core.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Safe health response model revealing no secrets or sensitive environment data."""

    model_config = ConfigDict(extra="forbid")

    service: str = "merchantos-ai"
    status: str = "ok"
    razorpay_mode: Literal["mock", "live"]


@router.get("/healthz", response_model=HealthResponse)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return health status and current Razorpay operational mode."""
    mode: Literal["mock", "live"] = "mock" if settings.razorpay_use_mock else "live"
    return HealthResponse(
        service="merchantos-ai",
        status="ok",
        razorpay_mode=mode,
    )
