"""Unit tests for TradeLedger disk persistence, reload, and capping."""

import json
from pathlib import Path

import pytest

from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_trade_ledger_default_in_memory() -> None:
    """TradeLedger() with default constructor is purely in-memory with persist_path=None."""
    ledger = TradeLedger()
    assert ledger.persist_path is None

    event = TradeEvent(
        event_id="evt_mem_01",
        session_id="sess_mem_01",
        timestamp="2026-08-29T12:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"utterance": "In memory test"}),
    )
    ledger.record_event(event)
    assert len(ledger.get_session_trace("sess_mem_01")) == 1


def test_trade_ledger_persists_and_reloads(tmp_path: Path) -> None:
    """TradeLedger with persist_path writes JSONL and reloads all sessions on restart."""
    persist_file = tmp_path / "ledger_history.jsonl"
    ledger1 = TradeLedger(persist_path=persist_file)

    event1 = TradeEvent(
        event_id="evt_p_01",
        session_id="sess_p_01",
        timestamp="2026-08-29T12:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"utterance": "Persistent utterance"}),
    )
    event2 = TradeEvent(
        event_id="evt_p_02",
        session_id="sess_p_01",
        timestamp="2026-08-29T12:00:01Z",
        event_type="order_created",
        payload=json.dumps({"order_id": "order_p_999", "amount_minor": 4500000}),
    )
    ledger1.record_event(event1)
    ledger1.record_event(event2)

    assert persist_file.exists()
    with open(persist_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2

    # Instantiate new TradeLedger from same persistence file
    ledger2 = TradeLedger(persist_path=persist_file)
    trace = ledger2.get_session_trace("sess_p_01")
    assert len(trace) == 2
    assert trace[0].event_id == "evt_p_01"
    assert trace[1].event_id == "evt_p_02"
    assert ledger2.get_expected_amount_for_order("order_p_999") == 4500000
    assert ledger2.get_session_id_for_order("order_p_999") == "sess_p_01"


def test_trade_ledger_cap_behavior(tmp_path: Path) -> None:
    """TradeLedger caps loaded lines at 2000 events when history file is large."""
    persist_file = tmp_path / "large_ledger.jsonl"

    # Pre-write 2200 event lines directly
    with open(persist_file, "w", encoding="utf-8") as f:
        for i in range(2200):
            evt = TradeEvent(
                event_id=f"evt_cap_{i:04d}",
                session_id=f"sess_cap_{i // 10}",
                timestamp="2026-08-29T12:00:00Z",
                event_type="intent_received",
                payload=json.dumps({"idx": i}),
            )
            f.write(evt.model_dump_json() + "\n")

    ledger = TradeLedger(persist_path=persist_file)
    all_sessions = ledger.get_all_sessions()
    total_events = sum(len(s.events) for s in all_sessions)
    assert total_events == 2000
