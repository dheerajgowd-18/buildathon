"""Integration tests for Server-Sent Events (SSE) and live summary endpoints."""

import asyncio
import json

from fastapi.testclient import TestClient
import pytest

from merchantos_api.main import create_app
from merchantos_api.routers.demo import sse_events_stream
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger


class StubRequest:
    """Stub request that simulates client connection state."""

    def __init__(self, disconnected: bool = False) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.anyio
async def test_sse_endpoint_connects() -> None:
    """GET /api/events establishes SSE streaming response with initial handshake."""
    trade_ledger = TradeLedger()
    req = StubRequest()
    response = await sse_events_stream(request=req, trade_ledger=trade_ledger)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    iterator = response.body_iterator
    first_chunk = await asyncio.wait_for(anext(iterator), timeout=5.0)
    assert ": connected" in first_chunk
    await iterator.aclose()


@pytest.mark.anyio
async def test_sse_streams_recorded_events() -> None:
    """GET /api/events delivers live recorded events to the client."""
    trade_ledger = TradeLedger()
    req = StubRequest()
    response = await sse_events_stream(request=req, trade_ledger=trade_ledger)
    iterator = response.body_iterator

    first_chunk = await asyncio.wait_for(anext(iterator), timeout=5.0)
    assert ": connected" in first_chunk

    event = TradeEvent(
        event_id="evt_sse_test_01",
        session_id="sess_sse_01",
        timestamp="2026-08-28T10:00:00Z",
        event_type="intent_received",
        payload=json.dumps({"utterance": "Live test"}),
    )
    trade_ledger.record_event(event)

    chunk = await asyncio.wait_for(anext(iterator), timeout=5.0)
    assert "event: trade" in chunk
    assert "evt_sse_test_01" in chunk
    assert "sess_sse_01" in chunk
    await iterator.aclose()


def test_summary_endpoint() -> None:
    """GET /api/summary returns aggregate KPI counts from ledger."""
    trade_ledger = TradeLedger()
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_sum_01",
            session_id="sess_sum_01",
            timestamp="2026-08-28T10:00:00Z",
            event_type="payment_captured",
            payload=json.dumps({"amount_minor": 5200000}),
        )
    )
    trade_ledger.record_event(
        TradeEvent(
            event_id="evt_sum_02",
            session_id="sess_sum_02",
            timestamp="2026-08-28T10:00:01Z",
            event_type="gate_decision",
            payload=json.dumps({"action": "BLOCK"}),
        )
    )

    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True), trade_ledger=trade_ledger)
    client = TestClient(app)

    res = client.get("/api/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_sessions"] == 2
    assert data["converted"] == 1
    assert data["blocked"] == 1
    assert data["declined"] == 0
