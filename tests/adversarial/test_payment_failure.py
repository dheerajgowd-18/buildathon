"""Adversarial Payment Failure Handling Test Suite.

Verifies that bank gateway payment failures (e.g. insufficient funds, card decline, timeout)
are handled gracefully by the webhook subsystem, returning HTTP 200 to acknowledge webhook receipt,
recording a payment_failed event in the TradeLedger, and maintaining ledger state consistency.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_razorpay.adapter import MockRazorpayAdapter


def test_payment_failure_graceful_handling() -> None:
    """
    Test that a valid signed payment.failed webhook is processed cleanly:
    - Returns HTTP 200 acknowledgment.
    - Records a payment_failed event with error details in the TradeLedger.
    - Preserves chronological ledger consistency without unhandled exceptions.
    """
    settings = Settings(razorpay_use_mock=True)
    trade_ledger = TradeLedger()
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    session_id = f"session_fail_{uuid.uuid4().hex[:8]}"
    order_id = f"order_fail_{uuid.uuid4().hex[:8]}"
    amount_minor = 3500000  # ₹35,000

    # 1. Pre-record initial intent and order creation in TradeLedger
    trade_ledger.record_event(
        TradeEvent(
            event_id=f"evt_intent_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            timestamp="2026-08-27T15:00:00Z",
            event_type="intent_received",
            payload=json.dumps({"utterance": "Looking for a tablet under 40k"}),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id=f"evt_ord_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            timestamp="2026-08-27T15:01:00Z",
            event_type="order_created",
            payload=json.dumps(
                {
                    "order_id": order_id,
                    "amount_minor": amount_minor,
                    "session_id": session_id,
                }
            ),
        )
    )

    # 2. Generate signed payment.failed webhook
    adapter = MockRazorpayAdapter(settings=settings)
    raw_body, signature = adapter.generate_mock_signed_payment_failed(
        order_id=order_id,
        amount_minor=amount_minor,
        payment_id="pay_fail_gateway_001",
        error_code="GATEWAY_ERROR",
        error_description="Card issuer declined transaction: Insufficient funds",
    )

    # 3. Post webhook payload to /webhooks/razorpay
    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    # 4. Assertions
    # The endpoint returns HTTP 200 (acknowledging receipt of the valid webhook)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.failed"
    assert "processed successfully" in data["message"]

    # The TradeLedger records a payment_failed event
    session_trace = trade_ledger.get_session_trace(session_id)
    assert len(session_trace) == 3
    assert [e.event_type for e in session_trace] == ["intent_received", "order_created", "payment_failed"]

    failed_event = session_trace[2]
    failed_payload = json.loads(failed_event.payload)
    assert failed_payload["order_id"] == order_id
    assert failed_payload["payment_id"] == "pay_fail_gateway_001"
    assert failed_payload["error_code"] == "GATEWAY_ERROR"
    assert "Insufficient funds" in failed_payload["error_description"]
    assert failed_payload["status"] == "failed"


def test_payment_failure_for_unregistered_session_handles_gracefully() -> None:
    """
    Test that a payment.failed event for an unknown or unindexed session ID
    is still gracefully accepted (HTTP 200) and recorded without raising unhandled exceptions.
    """
    settings = Settings(razorpay_use_mock=True)
    trade_ledger = TradeLedger()
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    order_id = "order_unregistered_999"
    adapter = MockRazorpayAdapter(settings=settings)
    raw_body, signature = adapter.generate_mock_signed_payment_failed(
        order_id=order_id,
        amount_minor=120000,
        payment_id="pay_unreg_001",
        error_code="BAD_REQUEST_ERROR",
        error_description="Payment cancelled by buyer",
    )

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.failed"

    # Verify event was recorded using fallback session_id = order_id
    trace = trade_ledger.get_session_trace(order_id)
    assert len(trace) == 1
    assert trace[0].event_type == "payment_failed"
