"""Integration tests for the interactive Demo Console and scenario triggers."""

import time

from fastapi.testclient import TestClient

from merchantos_api.build_info import TESTS_PASSING
from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_demo_page_renders() -> None:
    """GET /demo returns 200 with Demo Console UI and controls."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/demo")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Interactive Demo Console" in res.text
    assert "Negotiate — Mock LLM" in res.text or "Negotiate &mdash; Mock LLM" in res.text


def test_demo_negotiate_valid() -> None:
    """POST /api/demo/negotiate returns session_id and orchestrates negotiation events in ledger."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.post(
        "/api/demo/negotiate",
        json={"utterance": "Need a developer laptop under 60k fast", "use_live_llm": False},
    )
    assert res.status_code == 200
    data = res.json()
    assert "session_id" in data
    session_id = data["session_id"]
    assert data["mode"] == "negotiate"

    # Fast synchronous execution verification for testing
    from merchantos_api.demo_orchestrator import run_negotiation_demo
    run_negotiation_demo(session_id=session_id, utterance="Need a developer laptop under 60k fast", use_live_llm=False, settings=settings, trade_ledger=trade_ledger, step_delay_seconds=0.0)

    trace = trade_ledger.get_session_trace(session_id)
    event_types = [e.event_type for e in trace]
    assert "intent_received" in event_types
    assert "offer_proposed" in event_types
    assert "gate_decision" in event_types


def test_demo_negotiate_oversized_utterance() -> None:
    """POST /api/demo/negotiate with >500 character utterance returns 422."""
    trade_ledger = TradeLedger()
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True), trade_ledger=trade_ledger)
    client = TestClient(app)

    oversized = "a" * 600
    res = client.post("/api/demo/negotiate", json={"utterance": oversized, "use_live_llm": False})
    assert res.status_code == 422


def test_demo_injection_scenario() -> None:
    """POST /api/demo/injection triggers prompt injection attack resulting in CommerceProof gate intervention."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.post("/api/demo/injection")
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    from merchantos_api.demo_orchestrator import run_injection_demo
    run_injection_demo(session_id=session_id, settings=settings, trade_ledger=trade_ledger, step_delay_seconds=0.0)

    trace = trade_ledger.get_session_trace(session_id)
    gate_events = [e for e in trace if e.event_type == "gate_decision"]
    assert len(gate_events) >= 1
    assert "BLOCK" in gate_events[0].payload or "REPAIR" in gate_events[0].payload


def test_demo_cart_mutation_scenario() -> None:
    """POST /api/demo/cart-mutation records cart_mutation_tampered_amount error then payment_captured recovery."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.post("/api/demo/cart-mutation")
    assert res.status_code == 200
    session_id = res.json()["session_id"]

    from merchantos_api.demo_orchestrator import run_cart_mutation_demo
    run_cart_mutation_demo(session_id=session_id, settings=settings, trade_ledger=trade_ledger, step_delay_seconds=0.0)

    trace = trade_ledger.get_session_trace(session_id)
    event_types = [e.event_type for e in trace]
    assert "error" in event_types
    assert "payment_captured" in event_types


def test_demo_live_order_disabled_when_mock() -> None:
    """POST /api/demo/live-order returns 409 Conflict when razorpay_use_mock is True."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.post("/api/demo/live-order")
    assert res.status_code == 409
    assert "RAZORPAY_USE_MOCK=True" in res.json()["detail"]


def test_demo_live_llm_button_disabled_in_html() -> None:
    """GET /demo shows disabled attribute on Live LLM button when llm_use_mock is True."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/demo")
    assert res.status_code == 200
    assert 'id="btn-negotiate-live"' in res.text
    assert "disabled" in res.text


def test_overview_kpi_renders_build_info_constant() -> None:
    """GET / renders dynamic test count from build_info.TESTS_PASSING in KPI band."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert f"{TESTS_PASSING}/{TESTS_PASSING}" in res.text
