"""Unit tests for MockRazorpayAdapter."""

from merchantos_core.config import Settings
from merchantos_core.contracts import (
    RazorpayOrderNotes,
    RazorpayOrderRequest,
)
from merchantos_razorpay.adapter import MockRazorpayAdapter, build_razorpay_adapter
from merchantos_razorpay.webhook import (
    parse_webhook_event,
    verify_webhook_signature,
)


def test_mock_adapter_construction() -> None:
    """Mock adapter reports is_mock as True and can be built via factory."""
    settings = Settings(razorpay_use_mock=True)
    adapter = build_razorpay_adapter(settings)
    assert isinstance(adapter, MockRazorpayAdapter)
    assert adapter.is_mock is True


def test_mock_adapter_deterministic_order_creation() -> None:
    """Mock adapter must return deterministic orders preserving amount, currency, and receipt."""
    adapter = MockRazorpayAdapter()
    req = RazorpayOrderRequest(
        amount_minor=125000,
        currency="INR",
        receipt="rcpt_test_001",
        notes=RazorpayOrderNotes(
            session_id="sess_123",
            merchant_id="merch_456",
            checkout_snapshot_hash="hash_abc",
        ),
    )

    order1 = adapter.create_order(req)
    order2 = adapter.create_order(req)

    assert order1.id == order2.id
    assert order1.id.startswith("order_mock_")
    assert order1.amount_minor == 125000
    assert order1.currency == "INR"
    assert order1.receipt == "rcpt_test_001"
    assert order1.status == "created"


def test_mock_adapter_captured_webhook_generation() -> None:
    """Mock adapter's payment.captured webhook helper produces valid, verifiable payloads."""
    adapter = MockRazorpayAdapter()
    raw_body, signature = adapter.generate_mock_signed_payment_captured(
        order_id="order_mock_12345",
        amount_minor=50000,
        currency="INR",
        payment_id="pay_mock_999",
    )

    secret = adapter._settings.get_effective_webhook_secret()
    assert verify_webhook_signature(raw_body, signature, secret) is True

    parsed_event = parse_webhook_event(raw_body)
    assert parsed_event.event == "payment.captured"
    assert parsed_event.payload.entity.id == "pay_mock_999"
    assert parsed_event.payload.entity.order_id == "order_mock_12345"
    assert parsed_event.payload.entity.amount_minor == 50000
    assert parsed_event.payload.entity.status == "captured"


def test_mock_adapter_failed_webhook_generation() -> None:
    """Mock adapter's payment.failed webhook helper produces valid, verifiable payloads."""
    adapter = MockRazorpayAdapter()
    raw_body, signature = adapter.generate_mock_signed_payment_failed(
        order_id="order_mock_12345",
        amount_minor=50000,
        currency="INR",
        payment_id="pay_mock_888",
        error_code="GATEWAY_ERROR",
        error_description="Payment declined by bank",
    )

    secret = adapter._settings.get_effective_webhook_secret()
    assert verify_webhook_signature(raw_body, signature, secret) is True

    parsed_event = parse_webhook_event(raw_body)
    assert parsed_event.event == "payment.failed"
    assert parsed_event.payload.entity.id == "pay_mock_888"
    assert parsed_event.payload.entity.status == "failed"
    assert parsed_event.payload.entity.error_code == "GATEWAY_ERROR"
    assert parsed_event.payload.entity.error_description == "Payment declined by bank"
