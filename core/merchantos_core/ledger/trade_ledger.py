"""Immutable Thread-Safe Trade Ledger for MerchantOS AI."""

from __future__ import annotations

import json
import threading

from merchantos_core.contracts import LedgerEntry, TradeEvent


class TradeLedger:
    """Thread-safe in-memory audit ledger tracking the complete lifecycle of commerce trades."""

    def __init__(self) -> None:
        self._sessions: dict[str, list[TradeEvent]] = {}
        self._order_to_session: dict[str, str] = {}
        self._order_expected_amount: dict[str, int] = {}
        self._lock = threading.Lock()

    def record_event(self, event: TradeEvent) -> None:
        """Append an immutable TradeEvent to the session's event trace in a thread-safe manner."""
        with self._lock:
            if event.session_id not in self._sessions:
                self._sessions[event.session_id] = []
            self._sessions[event.session_id].append(event)

            # Auto-index order metadata if present in event payload
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
