"""Shared fixtures for pytest test suite."""

import pytest
from pydantic import SecretStr

from merchantos_core.config import Settings
from merchantos_core.contracts import CheckoutLineItem, CheckoutSnapshot


@pytest.fixture
def mock_settings() -> Settings:
    """Settings configured in mock mode."""
    return Settings(
        razorpay_use_mock=True,
        razorpay_base_url="https://api.razorpay.com",
        razorpay_request_timeout_seconds=10.0,
    )


@pytest.fixture
def live_valid_settings() -> Settings:
    """Settings configured in live test mode with valid credentials."""
    return Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_key12345"),
        razorpay_key_secret=SecretStr("secret_key_abcdef"),
        razorpay_webhook_secret=SecretStr("whsec_secret_xyz123"),
        razorpay_base_url="https://api.razorpay.com",
        razorpay_request_timeout_seconds=5.0,
    )


@pytest.fixture
def sample_line_items() -> list[CheckoutLineItem]:
    """Sample line items for checkout tests."""
    return [
        CheckoutLineItem(
            sku_id="SKU-001",
            name="Organic Cotton T-Shirt",
            quantity=2,
            unit_amount_minor=150000,
            line_total_minor=300000,
        ),
        CheckoutLineItem(
            sku_id="SKU-002",
            name="Canvas Tote Bag",
            quantity=1,
            unit_amount_minor=50000,
            line_total_minor=50000,
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_line_items: list[CheckoutLineItem]) -> CheckoutSnapshot:
    """Sample valid checkout snapshot."""
    return CheckoutSnapshot(
        session_id="sess_abc123",
        merchant_id="merch_xyz999",
        currency="INR",
        amount_minor=350000,
        line_items=sample_line_items,
    )
