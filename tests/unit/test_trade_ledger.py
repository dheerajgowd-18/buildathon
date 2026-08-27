"""Unit tests for TradeLedger implementation and TradeEvent contracts."""

from __future__ import annotations

import json
import threading

import pytest

from merchantos_core.contracts import LedgerEntry, TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


def test_trade_event_strict_validation() -> None:
    """TradeEvent validates required fields and forbids extra keys."""
    event = TradeEvent(
        event_id="evt_001",
        session_id="sess_001",
        timestamp="2026-08-27T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"msg": "hello"}),
    )
    assert event.event_id == "evt_001"
    assert event.session_id == "sess_001"
    assert event.event_type == "intent_received"

    # Forbid extra fields
    with pytest.raises(Exception):
        TradeEvent(
            event_id="evt_002",
            session_id="sess_001",
            timestamp="2026-08-27T10:00:00Z",
            event_type="intent_received",
            payload="{}",
            extra_field="unauthorized",  # type: ignore[call-arg]
        )


def test_ledger_entry_model() -> None:
    """LedgerEntry holds list of TradeEvents for a session."""
    events = [
        TradeEvent(
            event_id=f"evt_{i}",
            session_id="sess_abc",
            timestamp=f"2026-08-27T10:0{i}:00Z",
            event_type="intent_received" if i == 0 else "gate_decision",
            payload=json.dumps({"round": i}),
        )
        for i in range(3)
    ]
    entry = LedgerEntry(session_id="sess_abc", events=events)
    assert entry.session_id == "sess_abc"
    assert len(entry.events) == 3


def test_trade_ledger_record_and_get_session_trace() -> None:
    """TradeLedger records events chronologically per session."""
    ledger = TradeLedger()

    evt1 = TradeEvent(
        event_id="evt_1",
        session_id="sess_100",
        timestamp="2026-08-27T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"text": "budget 50k"}),
    )
    evt2 = TradeEvent(
        event_id="evt_2",
        session_id="sess_100",
        timestamp="2026-08-27T10:01:00Z",
        event_type="offer_proposed",
        payload=json.dumps({"sku": "SKU-01", "proposed_price_minor": 4500000}),
    )
    evt3 = TradeEvent(
        event_id="evt_3",
        session_id="sess_200",
        timestamp="2026-08-27T10:02:00Z",
        event_type="intent_received",
        payload=json.dumps({"text": "budget 10k"}),
    )

    ledger.record_event(evt1)
    ledger.record_event(evt2)
    ledger.record_event(evt3)

    trace100 = ledger.get_session_trace("sess_100")
    assert len(trace100) == 2
    assert trace100[0].event_id == "evt_1"
    assert trace100[1].event_id == "evt_2"

    trace200 = ledger.get_session_trace("sess_200")
    assert len(trace200) == 1
    assert trace200[0].event_id == "evt_3"

    all_sessions = ledger.get_all_sessions()
    assert len(all_sessions) == 2
    session_ids = {s.session_id for s in all_sessions}
    assert session_ids == {"sess_100", "sess_200"}


def test_trade_ledger_thread_safety() -> None:
    """TradeLedger safely handles concurrent writes from multiple threads."""
    ledger = TradeLedger()
    num_threads = 10
    events_per_thread = 50

    def worker(thread_idx: int) -> None:
        session_id = f"thread_sess_{thread_idx}"
        for i in range(events_per_thread):
            event = TradeEvent(
                event_id=f"evt_{thread_idx}_{i}",
                session_id=session_id,
                timestamp=f"2026-08-27T10:00:{i:02d}Z",
                event_type="offer_proposed",
                payload=json.dumps({"count": i}),
            )
            ledger.record_event(event)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    all_sessions = ledger.get_all_sessions()
    assert len(all_sessions) == num_threads

    for thread_idx in range(num_threads):
        session_id = f"thread_sess_{thread_idx}"
        trace = ledger.get_session_trace(session_id)
        assert len(trace) == events_per_thread


def test_trade_ledger_order_indexing_and_lookup() -> None:
    """TradeLedger automatically indexes order_id and expected amount from event payloads."""
    ledger = TradeLedger()

    event = TradeEvent(
        event_id="evt_ord_idx",
        session_id="session_order_indexing",
        timestamp="2026-08-27T10:00:00Z",
        event_type="order_created",
        payload=json.dumps({"order_id": "order_idx_123", "amount_minor": 6000000}),
    )
    ledger.record_event(event)

    assert ledger.get_expected_amount_for_order("order_idx_123") == 6000000
    assert ledger.get_session_id_for_order("order_idx_123") == "session_order_indexing"
    assert ledger.get_expected_amount_for_order("nonexistent_order") is None
    assert ledger.get_session_id_for_order("nonexistent_order") is None
