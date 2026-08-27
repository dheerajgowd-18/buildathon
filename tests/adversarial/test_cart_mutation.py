"""Adversarial Cart Mutation Defense Test Suite.

Verifies that attempts to tamper with the agreed commercial checkout amount
(e.g., paying ₹10,000 instead of the approved ₹50,000) are detected and rejected,
even if the webhook payload carries a cryptographically valid Razorpay signature.
"""

from __future__ import annotations

import json
import uuid

from fastapi.testclient import TestClient

from merchantos_api.main import create_app
from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.config import Settings
from merchantos_core.contracts import (
    CumulativeLedger,
    InventoryRecord,
    InventoryState,
    MerchantPolicy,
    Product,
    ProposedOffer,
    TradeEvent,
)
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_razorpay.adapter import MockRazorpayAdapter


def test_webhook_rejects_tampered_payment_amount() -> None:
    """
    Test that a webhook with a valid signature but tampered amount (cart mutation)
    is rejected and logged as an error in the TradeLedger.
    """
    settings = Settings(razorpay_use_mock=True)
    trade_ledger = TradeLedger()
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    session_id = f"session_cart_mut_{uuid.uuid4().hex[:8]}"
    order_id = f"order_tampered_{uuid.uuid4().hex[:8]}"

    catalog = [
        Product(
            sku_id="SKU-EXP-001",
            name="Premium Hardware Unit",
            category="hardware",
            cost_minor=3500000,  # ₹35,000
            base_price_minor=5000000,  # ₹50,000
            inventory_count=10,
        )
    ]
    policy = MerchantPolicy(
        merchant_id="merch_01",
        margin_floor_pct=0.10,
        discount_cap_pct=0.15,
        promotion_budget_minor=5000000,
    )
    inventory = InventoryState(records=[InventoryRecord(sku_id="SKU-EXP-001", available_count=10)])
    ledger = CumulativeLedger(
        merchant_id="merch_01",
        total_promotion_budget_minor=5000000,
        total_discount_minor_used=0,
    )

    # 1. Create and evaluate approved ProposedOffer for ₹50,000 (5,000,000 paise)
    proposed_offer = ProposedOffer(
        offer_id=f"off_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        selected_sku_id="SKU-EXP-001",
        proposed_price_minor=5000000,  # ₹50,000
        discount_minor=0,
        shipping_tier="express",
        rationale="Approved standard commercial price.",
    )

    gate = CommerceProof()
    decision = gate.evaluate(
        offer=proposed_offer,
        policy=policy,
        inventory=inventory,
        ledger=ledger,
        catalog=catalog,
    )
    assert decision.action == "EXECUTE"
    assert decision.final_state_hash is not None

    # 2. Record gate decision and order creation in TradeLedger with expected ₹50,000
    trade_ledger.record_event(
        TradeEvent(
            event_id=f"evt_gate_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            timestamp="2026-08-27T12:00:00Z",
            event_type="gate_decision",
            payload=json.dumps(
                {
                    "decision_id": decision.decision_id,
                    "final_state_hash": decision.final_state_hash,
                    "order_id": order_id,
                    "amount_minor": 5000000,
                }
            ),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id=f"evt_ord_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            timestamp="2026-08-27T12:00:05Z",
            event_type="order_created",
            payload=json.dumps(
                {
                    "order_id": order_id,
                    "amount_minor": 5000000,
                    "session_id": session_id,
                }
            ),
        )
    )

    # 3. Adversary generates validly signed webhook for ₹10,000 (1,000,000 paise) instead of ₹50,000
    adapter = MockRazorpayAdapter(settings=settings)
    raw_body, signature = adapter.generate_mock_signed_payment_captured(
        order_id=order_id,
        amount_minor=1000000,  # Tampered: ₹10,000
        payment_id="pay_adv_mutation_001",
    )

    # 4. Post webhook to /webhooks/razorpay
    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    # 5. Assertions: Webhook is rejected with HTTP 400
    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"
    assert "Cart mutation rejected" in data["message"]

    # 6. Verify TradeLedger recorded the attack as an error and did NOT record payment_captured
    session_trace = trade_ledger.get_session_trace(session_id)
    event_types = [e.event_type for e in session_trace]

    assert "error" in event_types
    assert "payment_captured" not in event_types

    error_event = next(e for e in session_trace if e.event_type == "error")
    error_payload = json.loads(error_event.payload)
    assert error_payload["error"] == "cart_mutation_tampered_amount"
    assert error_payload["captured_amount_minor"] == 1000000
    assert error_payload["expected_amount_minor"] == 5000000


def test_webhook_accepts_untampered_payment_amount() -> None:
    """
    Test that a payment matching the exact expected approved amount succeeds and logs payment_captured.
    """
    settings = Settings(razorpay_use_mock=True)
    trade_ledger = TradeLedger()
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    session_id = f"session_legit_{uuid.uuid4().hex[:8]}"
    order_id = f"order_legit_{uuid.uuid4().hex[:8]}"
    expected_amount_minor = 4500000  # ₹45,000

    trade_ledger.record_event(
        TradeEvent(
            event_id=f"evt_ord_{uuid.uuid4().hex[:8]}",
            session_id=session_id,
            timestamp="2026-08-27T12:00:00Z",
            event_type="order_created",
            payload=json.dumps(
                {
                    "order_id": order_id,
                    "amount_minor": expected_amount_minor,
                    "session_id": session_id,
                }
            ),
        )
    )

    adapter = MockRazorpayAdapter(settings=settings)
    raw_body, signature = adapter.generate_mock_signed_payment_captured(
        order_id=order_id,
        amount_minor=expected_amount_minor,
        payment_id="pay_legit_001",
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

    session_trace = trade_ledger.get_session_trace(session_id)
    event_types = [e.event_type for e in session_trace]
    assert "payment_captured" in event_types
    assert "error" not in event_types
