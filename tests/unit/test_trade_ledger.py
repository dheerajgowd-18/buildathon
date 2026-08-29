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


def test_trade_ledger_subscribe_receives_events() -> None:
    """Subscribers receive recorded events in real time."""
    ledger = TradeLedger()
    q = ledger.subscribe()

    evt1 = TradeEvent(
        event_id="evt_sub_1",
        session_id="sess_sub",
        timestamp="2026-08-28T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"msg": "first"}),
    )
    ledger.record_event(evt1)

    received = q.get_nowait()
    assert received.event_id == "evt_sub_1"
    assert received.session_id == "sess_sub"


def test_trade_ledger_unsubscribe_stops_delivery() -> None:
    """Unsubscribing prevents future events from being enqueued."""
    ledger = TradeLedger()
    q = ledger.subscribe()

    evt1 = TradeEvent(
        event_id="evt_sub_1",
        session_id="sess_sub",
        timestamp="2026-08-28T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"msg": "first"}),
    )
    ledger.record_event(evt1)
    assert q.get_nowait().event_id == "evt_sub_1"

    ledger.unsubscribe(q)

    evt2 = TradeEvent(
        event_id="evt_sub_2",
        session_id="sess_sub",
        timestamp="2026-08-28T10:00:01Z",
        event_type="offer_proposed",
        payload=json.dumps({"msg": "second"}),
    )
    ledger.record_event(evt2)

    assert q.empty()


def test_trade_ledger_subscribe_ordering_and_drop_on_full() -> None:
    """Events maintain strict FIFO ordering; drops on full queue never block writers."""
    ledger = TradeLedger()
    q = ledger.subscribe(maxsize=3)

    for i in range(5):
        event = TradeEvent(
            event_id=f"evt_drop_{i}",
            session_id="sess_drop",
            timestamp=f"2026-08-28T10:00:0{i}Z",
            event_type="intent_received",
            payload=json.dumps({"i": i}),
        )
        ledger.record_event(event)  # Must never raise or block

    # Queue size was 3, so first 3 events were queued
    assert q.qsize() == 3
    e0 = q.get_nowait()
    e1 = q.get_nowait()
    e2 = q.get_nowait()
    assert e0.event_id == "evt_drop_0"
    assert e1.event_id == "evt_drop_1"
    assert e2.event_id == "evt_drop_2"


def test_trade_ledger_concurrent_subscribe_record_no_deadlock() -> None:
    """Concurrent threads subscribing, unsubscribing, and recording never deadlock."""
    ledger = TradeLedger()
    stop_event = threading.Event()

    def recorder():
        idx = 0
        while not stop_event.is_set():
            evt = TradeEvent(
                event_id=f"evt_con_{idx}",
                session_id=f"sess_con_{idx % 4}",
                timestamp="2026-08-28T10:00:00Z",
                event_type="intent_received",
                payload="{}",
            )
            ledger.record_event(evt)
            idx += 1

    def subscriber():
        for _ in range(20):
            q = ledger.subscribe(maxsize=50)
            # read some
            for _ in range(5):
                try:
                    q.get_nowait()
                except Exception:
                    pass
            ledger.unsubscribe(q)

    threads = [
        threading.Thread(target=recorder),
        threading.Thread(target=recorder),
        threading.Thread(target=subscriber),
        threading.Thread(target=subscriber),
    ]
    for t in threads:
        t.start()

    time_start = threading.Timer(0.3, stop_event.set)
    time_start.start()

    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive(), "Deadlock detected during concurrent subscription / record"
