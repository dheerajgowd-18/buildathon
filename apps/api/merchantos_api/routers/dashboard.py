"""Dashboard router for judge comprehension and live session trace visualization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from merchantos_api.deps import get_trade_ledger
from merchantos_core.ledger.trade_ledger import TradeLedger

router = APIRouter(tags=["dashboard"])

# Setup Jinja2 templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def format_inr(value: Any) -> str:
    """Format paise minor units cleanly as INR string (e.g. 4500000 -> ₹45,000.00)."""
    if value is None or value == "":
        return "—"
    try:
        val_int = int(value)
        return f"₹{val_int / 100:,.2f}"
    except (ValueError, TypeError):
        return str(value)


def format_json(value: Any) -> str:
    """Pretty-print JSON string or object with 2-space indentation."""
    if not value:
        return "{}"
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2)
        except Exception:
            return value
    try:
        return json.dumps(value, indent=2)
    except Exception:
        return str(value)


# Register template filters
templates.env.filters["format_inr"] = format_inr
templates.env.filters["format_json"] = format_json


def _parse_payload(payload_str: str) -> dict[str, Any]:
    """Safely parse JSON payload string."""
    try:
        data = json.loads(payload_str)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def _determine_session_summary(events: list[Any]) -> dict[str, Any]:
    """Compute summary metrics and final status for a session."""
    has_captured = False
    has_failed = False
    has_error = False
    has_block = False
    has_repair = False
    has_order = False
    gate_action = "N/A"
    rounds_count = 0
    final_amount_minor: int | None = None
    last_timestamp = "—"

    for event in events:
        last_timestamp = event.timestamp
        payload = _parse_payload(event.payload)

        if event.event_type == "intent_received":
            rounds_count += 1
        elif event.event_type == "gate_decision":
            action = payload.get("action")
            if action:
                gate_action = action
                if action == "BLOCK":
                    has_block = True
                elif action == "REPAIR":
                    has_repair = True
            if "final_offer" in payload and isinstance(payload["final_offer"], dict):
                price = payload["final_offer"].get("proposed_price_minor")
                if isinstance(price, int):
                    final_amount_minor = price
        elif event.event_type == "order_created":
            has_order = True
            amount = payload.get("amount") or payload.get("amount_minor")
            if isinstance(amount, int):
                final_amount_minor = amount
        elif event.event_type == "payment_captured":
            has_captured = True
            amount = payload.get("amount_minor")
            if isinstance(amount, int):
                final_amount_minor = amount
        elif event.event_type == "payment_failed":
            has_failed = True
        elif event.event_type == "error":
            has_error = True

    # Determine display status and badge styling
    if has_captured:
        status_label = "Converted"
        status_badge = "badge-success"
    elif has_error:
        status_label = "Security Rejection (Cart Tampered)"
        status_badge = "badge-danger"
    elif has_block:
        status_label = "Blocked by Gate"
        status_badge = "badge-danger"
    elif has_failed:
        status_label = "Payment Failed (Bank Declined)"
        status_badge = "badge-warning"
    elif has_order:
        status_label = "Order Created (Pending Settlement)"
        status_badge = "badge-info"
    elif has_repair:
        status_label = "Repaired by Gate"
        status_badge = "badge-warning"
    else:
        status_label = "In Negotiation"
        status_badge = "badge-secondary"

    return {
        "status_label": status_label,
        "status_badge": status_badge,
        "gate_action": gate_action,
        "rounds": max(1, rounds_count) if events else 0,
        "final_amount_minor": final_amount_minor,
        "last_timestamp": last_timestamp,
        "event_count": len(events),
    }


def _enrich_event_for_display(event: Any) -> dict[str, Any]:
    """Enrich TradeEvent with display metadata, lifecycle phase, and parsed payload."""
    payload = _parse_payload(event.payload)
    event_type = event.event_type

    if event_type in ("intent_received", "offer_proposed"):
        phase_code = "negotiation"
        phase_name = "Phase A: Intent & Negotiation"
        phase_class = "card-phase-negotiation"
    elif event_type == "gate_decision":
        phase_code = "gate"
        phase_name = "Phase B: The Gate (CommerceProof Control)"
        phase_class = "card-phase-gate"
    elif event_type == "order_created":
        phase_code = "execution"
        phase_name = "Phase C: Execution (Razorpay Order)"
        phase_class = "card-phase-execution"
    elif event_type in ("payment_captured", "payment_failed", "error"):
        phase_code = "settlement"
        phase_name = "Phase D: Settlement & Audit"
        phase_class = "card-phase-settlement"
    else:
        phase_code = "audit"
        phase_name = "Phase: Audit Log"
        phase_class = "card-phase-audit"

    # Specific Gate highlighting
    gate_highlight = None
    if event_type == "gate_decision":
        action = payload.get("action", "EXECUTE")
        if action == "EXECUTE":
            gate_highlight = "gate-execute"
        elif action == "REPAIR":
            gate_highlight = "gate-repair"
        elif action in ("BLOCK", "ESCALATE"):
            gate_highlight = "gate-block"

    return {
        "event_id": event.event_id,
        "session_id": event.session_id,
        "timestamp": event.timestamp,
        "event_type": event_type,
        "raw_payload": event.payload,
        "parsed_payload": payload,
        "phase_code": phase_code,
        "phase_name": phase_name,
        "phase_class": phase_class,
        "gate_highlight": gate_highlight,
    }


@router.get("/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_index(
    request: Request,
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> HTMLResponse:
    """Render the Static Judge Dashboard index showing all recorded negotiation & checkout sessions."""
    sessions_raw = trade_ledger.get_all_sessions()
    sessions_data = []

    total_converted = 0
    total_blocked = 0
    total_failed_or_error = 0

    for entry in sessions_raw:
        summary = _determine_session_summary(entry.events)
        if "Converted" in summary["status_label"]:
            total_converted += 1
        elif "Blocked" in summary["status_label"]:
            total_blocked += 1
        elif "Failed" in summary["status_label"] or "Security" in summary["status_label"]:
            total_failed_or_error += 1

        sessions_data.append(
            {
                "session_id": entry.session_id,
                "event_count": summary["event_count"],
                "rounds": summary["rounds"],
                "gate_action": summary["gate_action"],
                "final_amount_minor": summary["final_amount_minor"],
                "status_label": summary["status_label"],
                "status_badge": summary["status_badge"],
                "last_timestamp": summary["last_timestamp"],
            }
        )

    # Sort sessions with newest or most active first
    sessions_data.reverse()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "sessions": sessions_data,
            "total_sessions": len(sessions_data),
            "total_converted": total_converted,
            "total_blocked": total_blocked,
            "total_failed_or_error": total_failed_or_error,
        },
    )


@router.get("/dashboard/trace/{session_id}", response_class=HTMLResponse)
async def dashboard_trace(
    session_id: str,
    request: Request,
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> HTMLResponse:
    """Render the 60-second Judge Comprehension Chronological Trace Visualizer for a specific session."""
    raw_events = trade_ledger.get_session_trace(session_id)
    summary = _determine_session_summary(raw_events)
    enriched_events = [_enrich_event_for_display(event) for event in raw_events]

    return templates.TemplateResponse(
        request=request,
        name="trace.html",
        context={
            "session_id": session_id,
            "summary": summary,
            "events": enriched_events,
            "total_events": len(enriched_events),
        },
    )
