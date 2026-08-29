"""Dependency injection helpers for MerchantOS API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger
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


from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@lru_cache
def get_global_trade_ledger() -> TradeLedger:
    """Load default global TradeLedger singleton."""
    settings = get_global_settings()
    persist_path = (DATA_DIR / "ledger_history.jsonl") if settings.ledger_persist_enabled else None
    return TradeLedger(persist_path=persist_path)


def get_trade_ledger(request: Request) -> TradeLedger:
    """Retrieve trade ledger from app state if configured, otherwise from global singleton."""
    if hasattr(request.app.state, "trade_ledger") and request.app.state.trade_ledger is not None:
        return request.app.state.trade_ledger
    settings = get_settings(request)
    if settings.ledger_persist_enabled:
        persist_path = DATA_DIR / "ledger_history.jsonl"
        return TradeLedger(persist_path=persist_path)
    return get_global_trade_ledger()


def get_razorpay_adapter(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RazorpayAdapterBase:
    """Instantiate Razorpay adapter configured for current settings."""
    return build_razorpay_adapter(settings=settings)

