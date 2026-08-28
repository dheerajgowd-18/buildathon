"""Integration tests for the static judge dashboard and trace visualizer."""

import json

from fastapi.testclient import TestClient

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_dashboard_index_returns_200() -> None:
    """Assert the main dashboard route returns HTTP 200 with HTML content."""
    trade_ledger = TradeLedger()
    event = TradeEvent(
        event_id="evt_test_001",
        session_id="sess_dash_001",
        timestamp="2026-08-27T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"nl_utterance": "Looking for a high end laptop"}),
    )
    trade_ledger.record_event(event)

    app = create_app(settings=Settings(razorpay_use_mock=True), trade_ledger=trade_ledger)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "MerchantOS AI" in response.text
    assert "sess_dash_001" in response.text

    # Also test /dashboard alias
    dash_response = client.get("/dashboard")
    assert dash_response.status_code == 200
    assert "sess_dash_001" in dash_response.text


def test_dashboard_trace_returns_200() -> None:
    """Seed the TradeLedger with a complete 4-phase mock session and assert the trace route renders correctly."""
    trade_ledger = TradeLedger()
    session_id = "sess_trace_lifecycle_123"

    # 1. Phase A: Intent & Negotiation
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_01",
            session_id=session_id,
            timestamp="2026-08-27T10:00:00Z",
            event_type="intent_received",
            payload=json.dumps({"nl_utterance": "I need 10 laptops urgently for tomorrow"}),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_02",
            session_id=session_id,
            timestamp="2026-08-27T10:00:01Z",
            event_type="offer_proposed",
            payload=json.dumps(
                {
                    "sku_id": "SKU-LAP-001",
                    "proposed_price_minor": 4500000,
                    "discount_minor": 500000,
                    "shipping_tier": "express",
                }
            ),
        )
    )

    # 2. Phase B: Gate Decision
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_03",
            session_id=session_id,
            timestamp="2026-08-27T10:00:02Z",
            event_type="gate_decision",
            payload=json.dumps(
                {
                    "action": "EXECUTE",
                    "final_state_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90",
                    "final_offer": {
                        "proposed_price_minor": 4500000,
                        "discount_minor": 500000,
                    },
                }
            ),
        )
    )

    # 3. Phase C: Execution
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_04",
            session_id=session_id,
            timestamp="2026-08-27T10:00:03Z",
            event_type="order_created",
            payload=json.dumps(
                {
                    "order_id": "order_mock_123",
                    "amount_minor": 4500000,
                    "currency": "INR",
                }
            ),
        )
    )

    # 4. Phase D: Settlement
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_05",
            session_id=session_id,
            timestamp="2026-08-27T10:00:04Z",
            event_type="payment_captured",
            payload=json.dumps(
                {
                    "order_id": "order_mock_123",
                    "payment_id": "pay_mock_123",
                    "amount_minor": 4500000,
                    "currency": "INR",
                    "status": "captured",
                }
            ),
        )
    )

    app = create_app(settings=Settings(razorpay_use_mock=True), trade_ledger=trade_ledger)
    client = TestClient(app)

    response = client.get(f"/dashboard/trace/{session_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert session_id in response.text
    assert "EXECUTE" in response.text
    assert "order_mock_123" in response.text
    assert "pay_mock_123" in response.text
    assert "₹45,000.00" in response.text


def test_dashboard_handles_empty_ledger() -> None:
    """Assert the dashboard renders gracefully when the ledger is completely empty."""
    trade_ledger = TradeLedger()
    app = create_app(settings=Settings(razorpay_use_mock=True), trade_ledger=trade_ledger)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "No Sessions Recorded in Trade Ledger" in response.text

    trace_response = client.get("/dashboard/trace/sess_non_existent")
    assert trace_response.status_code == 200
    assert "No Events Found for Session sess_non_existent" in trace_response.text
