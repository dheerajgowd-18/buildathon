"""Immutable Thread-Safe Trade Ledger for MerchantOS AI with optional persistence."""

from __future__ import annotations

import json
from pathlib import Path
import queue
import threading

from merchantos_core.contracts import LedgerEntry, TradeEvent


class TradeLedger:
    """Thread-safe in-memory and optionally persistent audit ledger tracking the complete lifecycle of commerce trades."""

    def __init__(self, persist_path: Path | str | None = None) -> None:
        self.persist_path = Path(persist_path) if persist_path is not None else None
        self._sessions: dict[str, list[TradeEvent]] = {}
        self._order_to_session: dict[str, str] = {}
        self._order_expected_amount: dict[str, int] = {}
        self._subscribers: list[queue.Queue[TradeEvent]] = []
        self._lock = threading.Lock()

        if self.persist_path is not None:
            self._load_from_disk()

    def _index_event_payload(self, event: TradeEvent) -> None:
        """Helper to index order metadata from an event payload."""
        try:
            data = json.loads(event.payload)
            if isinstance(data, dict):
                order_id = data.get("order_id")
                if order_id and isinstance(order_id, str):
                    self._order_to_session[order_id] = event.session_id
                    if "amount_minor" in data and isinstance(data["amount_minor"], int):
                        self._order_expected_amount[order_id] = data["amount_minor"]
                    elif "amount" in data and isinstance(data["amount"], int):
                        self._order_expected_amount[order_id] = data["amount"]
                    elif "final_offer" in data and isinstance(data["final_offer"], dict):
                        price = data["final_offer"].get("proposed_price_minor")
                        if isinstance(price, int):
                            self._order_expected_amount[order_id] = price
                    elif "proposed_price_minor" in data and isinstance(data["proposed_price_minor"], int):
                        self._order_expected_amount[order_id] = data["proposed_price_minor"]
        except Exception:
            pass

    def _load_from_disk(self) -> None:
        """Load up to the last 2000 events from the persistence JSONL file."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Keep only the last 2000 events if capped
            if len(lines) > 2000:
                lines = lines[-2000:]

            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = TradeEvent.model_validate_json(line)
                    if event.session_id not in self._sessions:
                        self._sessions[event.session_id] = []
                    self._sessions[event.session_id].append(event)
                    self._index_event_payload(event)
                except Exception:
                    continue
        except Exception:
            pass

    def subscribe(self, maxsize: int = 1000) -> queue.Queue[TradeEvent]:
        """Register a new event subscription queue for real-time SSE streaming."""
        q: queue.Queue[TradeEvent] = queue.Queue(maxsize=maxsize)
        with self._lock:
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: queue.Queue[TradeEvent]) -> None:
        """Unregister an event subscription queue."""
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def record_event(self, event: TradeEvent) -> None:
        """Append an immutable TradeEvent to the session's event trace in a thread-safe manner."""
        with self._lock:
            if event.session_id not in self._sessions:
                self._sessions[event.session_id] = []
            self._sessions[event.session_id].append(event)

            # Dispatch non-blocking to all active subscribers (drop on full to never block writers)
            for sub in list(self._subscribers):
                try:
                    sub.put_nowait(event)
                except queue.Full:
                    pass

            self._index_event_payload(event)

            # Append to persistent JSONL if configured
            if self.persist_path is not None:
                try:
                    self.persist_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.persist_path, "a", encoding="utf-8") as f:
                        f.write(event.model_dump_json() + "\n")
                except Exception:
                    pass

    def get_session_trace(self, session_id: str) -> list[TradeEvent]:
        """Return chronological list of trade events recorded for a specific session."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def get_all_sessions(self) -> list[LedgerEntry]:
        """Return all recorded sessions as LedgerEntry instances."""
        with self._lock:
            return [
                LedgerEntry(session_id=s_id, events=list(events))
                for s_id, events in self._sessions.items()
            ]

    def get_expected_amount_for_order(self, order_id: str) -> int | None:
        """Retrieve the expected amount (in paise minor units) for a given Razorpay order ID."""
        with self._lock:
            return self._order_expected_amount.get(order_id)

    def get_session_id_for_order(self, order_id: str) -> str | None:
        """Retrieve the associated session ID for a given Razorpay order ID."""
        with self._lock:
            return self._order_to_session.get(order_id)

    def clear(self) -> None:
        """Reset all internal ledger state and indexes (used for test isolation)."""
        with self._lock:
            self._sessions.clear()
            self._order_to_session.clear()
            self._order_expected_amount.clear()
            self._subscribers.clear()
            if self.persist_path is not None and self.persist_path.exists():
                try:
                    self.persist_path.unlink()
                except Exception:
                    pass
