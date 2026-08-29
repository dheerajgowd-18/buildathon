"""Integration tests for The Trading Floor SSE choreography and theater protocol."""

import asyncio
import json

from fastapi.testclient import TestClient
import pytest

from merchantos_api.main import create_app
from merchantos_api.theater import (
    TheaterRunRequest,
    _run_theater_session,
    sse_theater_events,
    trigger_theater_run,
)
from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger


class StubRequest:
    """Stub request simulating SSE connection lifecycle."""

    def __init__(self, disconnected: bool = False) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.anyio
async def test_theater_solo_run_sse() -> None:
    """Solo mode executes 8 stages + reveal, records ledger events, and yields valid SSE sequence."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    req = StubRequest()

    trigger_data = await trigger_theater_run(
        payload=TheaterRunRequest(utterance="Need high performance laptop fast", mode="solo", use_live_llm=False),
        settings=settings,
        trade_ledger=trade_ledger,
        step_delay_seconds=0.0,
    )
    run_id = trigger_data["run_id"]
    session_id = trigger_data["session_id"]
    assert run_id.startswith("th_run_")
    assert session_id.startswith("sess_floor_")

    response = await sse_theater_events(request=req, run_id=run_id)
    iterator = response.body_iterator

    first_chunk = await asyncio.wait_for(anext(iterator), timeout=2.0)
    assert ": connected" in first_chunk

    # Collect all stages emitted by the orchestrator
    stages_seen = []
    reveal_payload = None

    while True:
        try:
            chunk = await asyncio.wait_for(anext(iterator), timeout=3.0)
            if "event: done" in chunk:
                break
            if "event: step" in chunk:
                data_line = [l for l in chunk.splitlines() if l.startswith("data: ")][0]
                step = json.loads(data_line[6:])
                stages_seen.append(step["stage"])
                if step["stage"] == "reveal":
                    reveal_payload = json.loads(step["payload_json"])
        except StopAsyncIteration:
            break

    await iterator.aclose()

    # Verify strict stage order for Solo mode
    expected_stages = ["intent", "salesperson", "offers", "gate", "razorpay", "settle", "outcome", "reveal"]
    assert stages_seen == expected_stages

    # Verify canonical TradeLedger trace
    trace = trade_ledger.get_session_trace(session_id)
    event_types = [e.event_type for e in trace]
    assert "intent_received" in event_types
    assert "offer_proposed" in event_types
    assert "gate_decision" in event_types
    assert "order_created" in event_types
    assert "payment_captured" in event_types

    # Verify reveal payload
    assert reveal_payload is not None
    assert "divergence" in reveal_payload
    assert "true_budget_minor" in reveal_payload


@pytest.mark.anyio
async def test_theater_race_run_sse() -> None:
    """Race mode includes 'clerk' stage and returns 2 outcome lanes (growth vs baseline rules)."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    req = StubRequest()

    trigger_data = await trigger_theater_run(
        payload=TheaterRunRequest(utterance="Looking for laptop under 50k urgently", mode="race", use_live_llm=False),
        settings=settings,
        trade_ledger=trade_ledger,
        step_delay_seconds=0.0,
    )
    run_id = trigger_data["run_id"]
    response = await sse_theater_events(request=req, run_id=run_id)
    iterator = response.body_iterator

    first_chunk = await asyncio.wait_for(anext(iterator), timeout=2.0)
    assert ": connected" in first_chunk

    stages_seen = []
    outcome_payload = None

    while True:
        try:
            chunk = await asyncio.wait_for(anext(iterator), timeout=3.0)
            if "event: done" in chunk:
                break
            if "event: step" in chunk:
                data_line = [l for l in chunk.splitlines() if l.startswith("data: ")][0]
                step = json.loads(data_line[6:])
                stages_seen.append(step["stage"])
                if step["stage"] == "outcome":
                    outcome_payload = json.loads(step["payload_json"])
        except StopAsyncIteration:
            break

    await iterator.aclose()

    assert "clerk" in stages_seen
    assert "salesperson" in stages_seen
    assert outcome_payload is not None
    lanes = outcome_payload.get("lanes", [])
    assert len(lanes) == 2
    arms = [l["arm"] for l in lanes]
    assert "growth" in arms
    assert "rules" in arms


@pytest.mark.anyio
async def test_theater_random_buyer() -> None:
    """random=True generates dynamic buyer intent utterance and valid divergence."""
    trade_ledger = TradeLedger()
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)

    trigger_data = await trigger_theater_run(
        payload=TheaterRunRequest(random=True, mode="solo", use_live_llm=False),
        settings=settings,
        trade_ledger=trade_ledger,
        step_delay_seconds=0.0,
    )
    assert trigger_data["utterance"] is not None
    assert len(trigger_data["utterance"]) > 0


def test_theater_live_llm_conflict_when_mock() -> None:
    """POST /api/theater/run with use_live_llm=True returns 409 when LLM_USE_MOCK=True."""
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)

    res = client.post("/api/theater/run", json={"use_live_llm": True, "mode": "solo"})
    assert res.status_code == 409
    assert "Live LLM requested but LLM_USE_MOCK=True" in res.json()["detail"]
