"""Integration tests for the static judge dashboard, overview showroom, and trace visualizer."""

from pathlib import Path
import json

from fastapi.testclient import TestClient

from merchantos_api.build_info import TESTS_PASSING
from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_overview_renders_hero() -> None:
    """Assert GET / renders the Phase 09 Overview page with headline and hero elements."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Who negotiates for the merchant" in response.text
    assert "LLM PROPOSES. CODE DISPOSES." in response.text
    assert "0 unverified money movements" in response.text


def test_overview_renders_divergence_svg() -> None:
    """Assert GET / contains the server-rendered inline SVG divergence chart."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "<svg" in response.text
    assert "Divergence" in response.text or "divergence" in response.text
    assert "The Divergence Thesis" in response.text or "THE DIVERGENCE THESIS" in response.text


def test_overview_renders_trust_boundary() -> None:
    """Assert GET / renders the topology trust boundary and 'only path to money' invariant."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "CommerceProof" in response.text
    assert "only path to money" in response.text
    assert "PROBABILISTIC" in response.text
    assert "DETERMINISTIC" in response.text


def test_overview_kpi_band() -> None:
    """Assert GET / renders the 4-metric KPI band with Gate Rejection Rate."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "GATE REJECTION RATE" in response.text or "Gate rejection" in response.text.lower()
    assert "CONVERSION LIFT" in response.text
    assert f"{TESTS_PASSING}/{TESTS_PASSING}" in response.text


def test_registry_still_works() -> None:
    """Assert GET /dashboard renders the session registry with new layout tokens."""
    trade_ledger = TradeLedger()
    event = TradeEvent(
        event_id="evt_test_001",
        session_id="sess_dash_001",
        timestamp="2026-08-27T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"nl_utterance": "Looking for a high end laptop"}),
    )
    trade_ledger.record_event(event)

    app = create_app(
        settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True),
        trade_ledger=trade_ledger,
    )
    client = TestClient(app)

    response = client.get("/dashboard")
    assert response.status_code == 200
    assert "MerchantOS AI" in response.text
    assert "sess_dash_001" in response.text
    assert "Trade Ledger Session Registry" in response.text


def test_trace_route_still_200_with_seed() -> None:
    """Seed the TradeLedger with a complete 4-phase mock session and assert trace route renders."""
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

    app = create_app(
        settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True),
        trade_ledger=trade_ledger,
    )
    client = TestClient(app)

    response = client.get(f"/dashboard/trace/{session_id}")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert session_id in response.text
    assert "EXECUTE" in response.text
    assert "order_mock_123" in response.text
    assert "pay_mock_123" in response.text
    assert "₹45,000.00" in response.text


def test_no_dark_mode() -> None:
    """Assert design.css enforces light mode and strictly avoids prefers-color-scheme: dark."""
    css_path = Path(__file__).resolve().parent.parent.parent / "apps" / "api" / "merchantos_api" / "static" / "design.css"
    assert css_path.exists(), f"design.css not found at {css_path}"

    css_content = css_path.read_text(encoding="utf-8")
    assert "color-scheme: light" in css_content
    assert "prefers-color-scheme: dark" not in css_content
    assert "prefers-color-scheme:dark" not in css_content
