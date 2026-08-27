"""Unit tests for Pydantic v2 core contracts."""

import pytest
from pydantic import ValidationError

from merchantos_core.contracts import (
    CheckoutLineItem,
    CheckoutSnapshot,
    RazorpayOrder,
    RazorpayOrderNotes,
    RazorpayOrderRequest,
    RazorpayPaymentCapturedEvent,
    RazorpayPaymentEntity,
    RazorpayPaymentFailedEvent,
    RazorpayWebhookPaymentPayload,
    UnknownWebhookEvent,
)


def test_valid_checkout_snapshot_passes(sample_snapshot: CheckoutSnapshot) -> None:
    """A valid snapshot should pass validation."""
    assert sample_snapshot.session_id == "sess_abc123"
    assert sample_snapshot.merchant_id == "merch_xyz999"
    assert sample_snapshot.currency == "INR"
    assert sample_snapshot.amount_minor == 350000
    assert len(sample_snapshot.line_items) == 2


def test_checkout_snapshot_negative_amount_fails(sample_line_items: list[CheckoutLineItem]) -> None:
    """Negative amount_minor must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CheckoutSnapshot(
            session_id="sess_1",
            merchant_id="merch_1",
            currency="INR",
            amount_minor=-100,
            line_items=sample_line_items,
        )
    assert "amount_minor" in str(exc_info.value)


def test_checkout_snapshot_non_inr_currency_fails(sample_line_items: list[CheckoutLineItem]) -> None:
    """Non-INR currency must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CheckoutSnapshot(
            session_id="sess_1",
            merchant_id="merch_1",
            currency="USD",  # type: ignore[arg-type]
            amount_minor=1000,
            line_items=sample_line_items,
        )
    assert "currency" in str(exc_info.value)


def test_checkout_snapshot_empty_line_items_fails() -> None:
    """Empty line items list must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CheckoutSnapshot(
            session_id="sess_1",
            merchant_id="merch_1",
            currency="INR",
            amount_minor=1000,
            line_items=[],
        )
    assert "line_items" in str(exc_info.value)


def test_checkout_line_item_invalid_quantity_fails() -> None:
    """Line item with quantity < 1 must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CheckoutLineItem(
            sku_id="SKU-1",
            name="Test Product",
            quantity=0,
            unit_amount_minor=100,
            line_total_minor=100,
        )
    assert "quantity" in str(exc_info.value)


def test_checkout_line_item_negative_amount_fails() -> None:
    """Line item with negative amounts must fail validation."""
    with pytest.raises(ValidationError) as exc_info:
        CheckoutLineItem(
            sku_id="SKU-1",
            name="Test Product",
            quantity=1,
            unit_amount_minor=-50,
            line_total_minor=50,
        )
    assert "unit_amount_minor" in str(exc_info.value)


def test_contracts_extra_fields_forbidden() -> None:
    """Internal models must forbid extra attributes."""
    with pytest.raises(ValidationError):
        CheckoutLineItem(
            sku_id="SKU-1",
            name="Item",
            quantity=1,
            unit_amount_minor=100,
            line_total_minor=100,
            extra_field="disallowed",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        RazorpayOrderNotes(
            session_id="sess_1",
            merchant_id="merch_1",
            checkout_snapshot_hash="hash_123",
            extra_field="disallowed",  # type: ignore[call-arg]
        )


def test_razorpay_order_request_serialization_aliases() -> None:
    """RazorpayOrderRequest must serialize amount_minor as 'amount'."""
    notes = RazorpayOrderNotes(
        session_id="sess_123",
        merchant_id="merch_456",
        checkout_snapshot_hash="snap_hash_abc",
    )
    req = RazorpayOrderRequest(
        amount_minor=25000,
        currency="INR",
        receipt="rcpt_001",
        notes=notes,
    )
    serialized = req.model_dump(by_alias=True, mode="json")
    assert "amount" in serialized
    assert serialized["amount"] == 25000
    assert "amount_minor" not in serialized
    assert serialized["currency"] == "INR"
    assert serialized["receipt"] == "rcpt_001"
    assert serialized["notes"]["session_id"] == "sess_123"


def test_razorpay_order_inbound_parsing() -> None:
    """RazorpayOrder must parse response JSON using validation aliases."""
    raw_response = {
        "id": "order_EKwxwAgItmmXdp",
        "entity": "order",
        "amount": 50000,
        "amount_paid": 0,
        "amount_due": 50000,
        "currency": "INR",
        "receipt": "rcpt_789",
        "status": "created",
        "created_at": 1582628071,
    }
    order = RazorpayOrder.model_validate(raw_response)
    assert order.id == "order_EKwxwAgItmmXdp"
    assert order.amount_minor == 50000
    assert order.currency == "INR"
    assert order.status == "created"
    assert order.receipt == "rcpt_789"
    assert order.created_at_unix == 1582628071


def test_razorpay_payment_entity_inbound_parsing() -> None:
    """RazorpayPaymentEntity parses amount from 'amount'."""
    raw_payment = {
        "id": "pay_29QQoUBcx96mgK",
        "entity": "payment",
        "order_id": "order_EKwxwAgItmmXdp",
        "amount": 50000,
        "currency": "INR",
        "status": "captured",
        "method": "upi",
    }
    entity = RazorpayPaymentEntity.model_validate(raw_payment)
    assert entity.id == "pay_29QQoUBcx96mgK"
    assert entity.order_id == "order_EKwxwAgItmmXdp"
    assert entity.amount_minor == 50000
    assert entity.currency == "INR"
    assert entity.status == "captured"
    assert entity.error_code is None


def test_razorpay_webhook_event_parsing() -> None:
    """Webhook event models should correctly parse captured and failed events."""
    captured_json = {
        "entity": "event",
        "event": "payment.captured",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_captured_123",
                    "order_id": "order_123",
                    "amount": 10000,
                    "currency": "INR",
                    "status": "captured",
                }
            }
        },
    }
    event_captured = RazorpayPaymentCapturedEvent.model_validate(captured_json)
    assert event_captured.event == "payment.captured"
    assert event_captured.payload.entity.id == "pay_captured_123"
    assert event_captured.payload.entity.status == "captured"

    failed_json = {
        "entity": "event",
        "event": "payment.failed",
        "payload": {
            "entity": {
                "id": "pay_failed_456",
                "order_id": "order_456",
                "amount": 10000,
                "currency": "INR",
                "status": "failed",
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Insufficient balance",
            }
        },
    }
    event_failed = RazorpayPaymentFailedEvent.model_validate(failed_json)
    assert event_failed.event == "payment.failed"
    assert event_failed.payload.entity.id == "pay_failed_456"
    assert event_failed.payload.entity.status == "failed"
    assert event_failed.payload.entity.error_code == "BAD_REQUEST_ERROR"


def test_unknown_webhook_event_model() -> None:
    """Unknown webhook events are represented in a strictly typed model."""
    event = UnknownWebhookEvent(
        event="refund.processed",
        raw_body_sha256="abc123def456",
    )
    assert event.event == "refund.processed"
    assert event.raw_body_sha256 == "abc123def456"
