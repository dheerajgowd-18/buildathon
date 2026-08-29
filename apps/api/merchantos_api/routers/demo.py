"""Demo Console, SSE live streaming, and interactive sandbox endpoints."""

from __future__ import annotations

import anyio
import asyncio
import json
from pathlib import Path
import queue
import re
import threading
from typing import Annotated, Any
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from merchantos_api.demo_orchestrator import (
    run_cart_mutation_demo,
    run_injection_demo,
    run_negotiation_demo,
)
from merchantos_api.deps import get_settings, get_trade_ledger
from merchantos_core.config import Settings
from merchantos_core.contracts import TradeEvent
from merchantos_core.ledger.trade_ledger import TradeLedger

router = APIRouter(tags=["demo"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class NegotiateRequest(BaseModel):
    utterance: str
    use_live_llm: bool = False


def _clean_utterance(text: str) -> str:
    """Strip control characters and normalize whitespace."""
    if not text:
        return ""
    # Remove control characters except whitespace
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text).strip()
    return cleaned


from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse


@router.get("/demo")
async def demo_console_page() -> RedirectResponse:
    """Redirect legacy /demo route to The Trading Floor (/live)."""
    return RedirectResponse(url="/live", status_code=status.HTTP_302_FOUND)


@router.get("/api/events")
async def sse_events_stream(
    request: Request,
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
    session_id: str | None = Query(default=None),
) -> StreamingResponse:
    """Server-Sent Events (SSE) stream broadcasting real-time TradeLedger events."""
    event_queue: queue.Queue[TradeEvent] = trade_ledger.subscribe()

    target_session = session_id if isinstance(session_id, str) else None

    async def event_generator():
        try:
            # Initial connection handshake comment
            yield ": connected\n\n"
            while True:
                # Disconnect check
                if await request.is_disconnected():
                    break

                # Non-blocking poll on thread queue
                try:
                    event = event_queue.get_nowait()
                    if target_session is None or event.session_id == target_session:
                        data_payload = {
                            "event_id": event.event_id,
                            "session_id": event.session_id,
                            "event_type": event.event_type,
                            "timestamp": event.timestamp,
                            "payload": event.payload,
                        }
                        data_str = json.dumps(data_payload)
                        yield f"event: trade\ndata: {data_str}\n\n"
                except queue.Empty:
                    # Heartbeat / idle yield
                    await anyio.sleep(0.01)
        finally:
            trade_ledger.unsubscribe(event_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/summary")
async def get_ledger_summary(
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> dict[str, int]:
    """Retrieve aggregate counts across all recorded sessions for real-time KPI updates."""
    sessions_raw = trade_ledger.get_all_sessions()
    total_converted = 0
    total_blocked = 0
    total_declined = 0

    for entry in sessions_raw:
        for evt in entry.events:
            if evt.event_type == "payment_captured":
                total_converted += 1
                break
            elif evt.event_type == "gate_decision":
                try:
                    p = json.loads(evt.payload)
                    if p.get("action") == "BLOCK":
                        total_blocked += 1
                        break
                except Exception:
                    pass
            elif evt.event_type in ("payment_failed", "error"):
                total_declined += 1
                break

    return {
        "total_sessions": len(sessions_raw),
        "converted": total_converted,
        "blocked": total_blocked,
        "declined": total_declined,
    }


@router.post("/api/demo/negotiate")
async def trigger_negotiate_demo(
    payload: NegotiateRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> dict[str, str]:
    """Trigger an autonomous negotiation demo flow."""
    cleaned = _clean_utterance(payload.utterance)
    if not cleaned or len(cleaned) > 500:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Utterance must be between 1 and 500 characters.",
        )

    session_id = f"sess_demo_{uuid.uuid4().hex[:8]}"
    thread = threading.Thread(
        target=run_negotiation_demo,
        kwargs={
            "session_id": session_id,
            "utterance": cleaned,
            "use_live_llm": payload.use_live_llm,
            "settings": settings,
            "trade_ledger": trade_ledger,
        },
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id, "mode": "negotiate"}


@router.post("/api/demo/injection")
async def trigger_injection_demo(
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> dict[str, str]:
    """Trigger an adversarial prompt injection attack demo."""
    session_id = f"sess_inj_{uuid.uuid4().hex[:8]}"
    thread = threading.Thread(
        target=run_injection_demo,
        kwargs={
            "session_id": session_id,
            "settings": settings,
            "trade_ledger": trade_ledger,
        },
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id, "mode": "injection"}


@router.post("/api/demo/cart-mutation")
async def trigger_cart_mutation_demo(
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> dict[str, str]:
    """Trigger an adversarial cart mutation attack and recovery demo."""
    session_id = f"sess_mut_{uuid.uuid4().hex[:8]}"
    thread = threading.Thread(
        target=run_cart_mutation_demo,
        kwargs={
            "session_id": session_id,
            "settings": settings,
            "trade_ledger": trade_ledger,
        },
        daemon=True,
    )
    thread.start()

    return {"session_id": session_id, "mode": "cart_mutation"}


@router.post("/api/demo/live-order")
async def trigger_live_order_demo(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Trigger a live Razorpay order creation test (requires RAZORPAY_USE_MOCK=False)."""
    if settings.razorpay_use_mock:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live Razorpay test mode is not configured (RAZORPAY_USE_MOCK=True). Set live credentials in .env to use live order execution.",
        )

    session_id = f"sess_live_{uuid.uuid4().hex[:8]}"
    return {"session_id": session_id, "mode": "live_order"}
