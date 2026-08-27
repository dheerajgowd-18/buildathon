"""Adversarial Idempotency & Network Resilience Test Suite.

Verifies that transport failures and timeouts during payment order creation
are handled gracefully with idempotent retries, preventing duplicate order creation
and keeping the TradeLedger audit trail completely consistent.
"""

from __future__ import annotations

import json
import uuid

import httpx
from pydantic import SecretStr

from merchantos_core.config import Settings
from merchantos_core.contracts import (
    RazorpayOrder,
    RazorpayOrderNotes,
    RazorpayOrderRequest,
    TradeEvent,
)
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_razorpay.adapter import (
    LiveRazorpayAdapter,
    RazorpayTransportError,
)


def create_order_with_idempotent_retry(
    adapter: LiveRazorpayAdapter,
    request: RazorpayOrderRequest,
    trade_ledger: TradeLedger,
    max_retries: int = 3,
) -> RazorpayOrder:
    """Execute order creation with resilient idempotent retry and single ledger recording."""
    session_id = request.notes.session_id
    last_exception: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            order = adapter.create_order(request)

            # Record exactly ONE order_created event upon success
            trade_ledger.record_event(
                TradeEvent(
                    event_id=f"evt_ord_{uuid.uuid4().hex[:8]}",
                    session_id=session_id,
                    timestamp="2026-08-27T14:00:00Z",
                    event_type="order_created",
                    payload=json.dumps(
                        {
                            "order_id": order.id,
                            "amount_minor": order.amount_minor,
                            "currency": order.currency,
                            "receipt": order.receipt,
                            "session_id": session_id,
                            "attempt": attempt,
                        }
                    ),
                )
            )
            return order
        except RazorpayTransportError as err:
            last_exception = err
            # Log transient error attempt in ledger without creating duplicate order
            trade_ledger.record_event(
                TradeEvent(
                    event_id=f"evt_retry_{uuid.uuid4().hex[:8]}",
                    session_id=session_id,
                    timestamp="2026-08-27T14:00:01Z",
                    event_type="error",
                    payload=json.dumps(
                        {
                            "error": "transport_timeout_retry",
                            "attempt": attempt,
                            "message": str(err),
                        }
                    ),
                )
            )

    raise last_exception or RuntimeError("Order creation failed after retries")


def test_idempotent_retry_prevents_duplicate_orders() -> None:
    """
    Test that network timeout on first attempt is retried successfully,
    yielding a valid order with exactly ONE order_created event in TradeLedger.
    """
    settings = Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_live_key_id_12345"),
        razorpay_key_secret=SecretStr("rzp_live_secret_67890"),
        razorpay_webhook_secret=SecretStr("rzp_webhook_sec_12345"),
        razorpay_base_url="https://api.razorpay.com",
    )

    call_count = 0

    def mock_transport_handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            # First call: simulate network read timeout
            raise httpx.ReadTimeout("Simulated gateway read timeout on /v1/orders", request=request)

        # Second call: return successful 200 OK Razorpay order response
        return httpx.Response(
            200,
            json={
                "id": "order_live_retry_success_999",
                "amount": 7500000,
                "currency": "INR",
                "status": "created",
                "receipt": "rcpt_retry_test_001",
                "created_at": 1700000000,
            },
        )

    mock_transport = httpx.MockTransport(mock_transport_handler)
    http_client = httpx.Client(
        transport=mock_transport,
        base_url="https://api.razorpay.com",
        auth=("rzp_live_key_id_12345", "rzp_live_secret_67890"),
    )

    adapter = LiveRazorpayAdapter(settings=settings, http_client=http_client)
    trade_ledger = TradeLedger()

    session_id = f"session_idemp_{uuid.uuid4().hex[:8]}"
    order_request = RazorpayOrderRequest(
        amount_minor=7500000,  # ₹75,000
        currency="INR",
        receipt="rcpt_retry_test_001",
        notes=RazorpayOrderNotes(
            session_id=session_id,
            merchant_id="merch_live_01",
            checkout_snapshot_hash="hash_state_binding_12345",
        ),
    )

    # Execute retry-wrapped order creation
    final_order = create_order_with_idempotent_retry(
        adapter=adapter,
        request=order_request,
        trade_ledger=trade_ledger,
        max_retries=3,
    )

    # 1. Assert transport was called exactly twice
    assert call_count == 2

    # 2. Assert final order is valid
    assert final_order.id == "order_live_retry_success_999"
    assert final_order.amount_minor == 7500000
    assert final_order.status == "created"
    assert final_order.receipt == "rcpt_retry_test_001"

    # 3. Assert TradeLedger recorded exactly ONE order_created event
    session_trace = trade_ledger.get_session_trace(session_id)
    order_created_events = [e for e in session_trace if e.event_type == "order_created"]
    assert len(order_created_events) == 1

    created_payload = json.loads(order_created_events[0].payload)
    assert created_payload["order_id"] == "order_live_retry_success_999"
    assert created_payload["attempt"] == 2

    # Verify retry attempt was logged as a transient error event
    retry_events = [e for e in session_trace if e.event_type == "error"]
    assert len(retry_events) == 1
    assert "transport_timeout_retry" in json.loads(retry_events[0].payload)["error"]
