"""Integration tests for the /history archive page and /dashboard backward-compatibility."""

import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_history_page_renders_with_sessions(tmp_path: Path) -> None:
    """GET /history displays recorded trade sessions with status tags and event counts."""
    persist_file = tmp_path / "ledger_history.jsonl"
    trade_ledger = TradeLedger(persist_path=persist_file)

    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_hist_01",
            session_id="sess_hist_101",
            timestamp="2026-08-29T14:00:00Z",
            event_type="intent_received",
            payload=json.dumps({"utterance": "Looking for workstation pro", "mode": "solo"}),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_hist_02",
            session_id="sess_hist_101",
            timestamp="2026-08-29T14:00:01Z",
            event_type="payment_captured",
            payload=json.dumps({"payment_id": "pay_hist_001", "amount_minor": 5200000}),
        )
    )

    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True, ledger_persist_enabled=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.get("/history")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Trade Ledger Session Registry & Archive" in res.text or "Trade Ledger Session Registry &amp; Archive" in res.text
    assert "sess_hist_101" in res.text
    assert "Converted" in res.text


def test_dashboard_alias_remains_200() -> None:
    """GET /dashboard remains functional as a backward-compatible alias of /history."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.get("/dashboard")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]


def test_session_trace_page_renders() -> None:
    """GET /dashboard/trace/{session_id} renders rich event cards and phase badges."""
    trade_ledger = TradeLedger()
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_tr_01",
            session_id="sess_tr_202",
            timestamp="2026-08-29T14:10:00Z",
            event_type="intent_received",
            payload=json.dumps({"utterance": "Trace test"}),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_tr_02",
            session_id="sess_tr_202",
            timestamp="2026-08-29T14:10:02Z",
            event_type="gate_decision",
            payload=json.dumps({"action": "EXECUTE", "final_offer": {"proposed_price_minor": 4600000}}),
        )
    )

    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings, trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.get("/dashboard/trace/sess_tr_202")
    assert res.status_code == 200
    assert "sess_tr_202" in res.text
    assert "INTENT" in res.text
    assert "COMMERCEPROOF GATE" in res.text
