"""Dependency injection helpers for MerchantOS API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from merchantos_core.config import Settings
from merchantos_razorpay.adapter import RazorpayAdapterBase, build_razorpay_adapter


@lru_cache
def get_global_settings() -> Settings:
    """Load default global settings singleton."""
    return Settings()


def get_settings(request: Request) -> Settings:
    """Retrieve settings from app state if configured, otherwise from global singleton."""
    if hasattr(request.app.state, "settings") and request.app.state.settings is not None:
        return request.app.state.settings
    return get_global_settings()


def get_razorpay_adapter(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RazorpayAdapterBase:
    """Instantiate Razorpay adapter configured for current settings."""
    return build_razorpay_adapter(settings=settings)
