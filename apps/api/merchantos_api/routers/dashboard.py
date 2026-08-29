"""Dashboard, Trading Floor, and History router for judge comprehension."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from merchantos_api.build_info import TESTS_PASSING
from merchantos_api.charts import render_divergence_svg
from merchantos_api.deps import get_settings, get_trade_ledger
from merchantos_core.config import Settings
from merchantos_core.ledger.trade_ledger import TradeLedger

router = APIRouter(tags=["dashboard"])

# Setup Jinja2 templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"


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


def _get_health_chips(settings: Settings) -> dict[str, Any]:
    """Read data/validation_report.json and format topbar health status chips."""
    llm_chip = "LLM: MOCK" if settings.llm_use_mock else "LLM: LIVE"
    rzp_chip = "RZP: MOCK" if settings.razorpay_use_mock else "RZP: LIVE"
    llm_state = "neutral"
    rzp_state = "neutral"

    val_report_path = DATA_DIR / "validation_report.json"
    if val_report_path.exists():
        try:
            with open(val_report_path, "r", encoding="utf-8") as f:
                val_data = json.load(f)
                for r in val_data.get("results", []):
                    c_id = r.get("check_id")
                    st = r.get("status")
                    lat = r.get("latency_ms", 0)
                    ev_str = r.get("evidence_json", "")
                    if c_id == "live_llm":
                        if st == "pass":
                            llm_chip = f"LLM: LIVE · {lat}ms"
                            llm_state = "success"
                        elif st == "skipped":
                            llm_chip = "LLM: MOCK"
                            llm_state = "neutral"
                        elif st == "fail":
                            llm_chip = f"LLM: FAIL ({lat}ms)"
                            llm_state = "danger"
                    elif c_id == "live_razorpay":
                        if st == "pass":
                            ev = json.loads(ev_str) if ev_str else {}
                            oid = ev.get("order_id", "order_xxx")
                            rzp_chip = f"RZP: LIVE · {oid[:10]}"
                            rzp_state = "success"
                        elif st == "skipped":
                            rzp_chip = "RZP: MOCK"
                            rzp_state = "neutral"
                        elif st == "fail":
                            rzp_chip = f"RZP: FAIL ({lat}ms)"
                            rzp_state = "danger"
        except Exception:
            pass

    return {
        "llm_chip": llm_chip,
        "llm_state": llm_state,
        "rzp_chip": rzp_chip,
        "rzp_state": rzp_state,
    }


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
    kind = "demo"

    for event in events:
        last_timestamp = event.timestamp
        payload = _parse_payload(event.payload)

        if "race" in str(payload.get("mode", "")).lower() or "race" in event.session_id.lower():
            kind = "race"
        elif "floor" in event.session_id.lower() or "theater" in str(payload).lower():
            kind = "trading_floor"
        elif "inj" in event.session_id.lower() or "mut" in event.session_id.lower() or "attack" in str(payload).lower():
            kind = "attack"
        elif "val" in event.session_id.lower():
            kind = "validation"

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
            if "amount_minor" in payload and isinstance(payload["amount_minor"], int):
                final_amount_minor = payload["amount_minor"]
            elif "amount" in payload and isinstance(payload["amount"], int):
                final_amount_minor = payload["amount"]
        elif event.event_type == "payment_captured":
            has_captured = True
        elif event.event_type == "payment_failed":
            has_failed = True
        elif event.event_type == "error":
            has_error = True

    if has_captured:
        status_label = "Converted (Paid)"
        status_badge = "badge-success"
    elif has_block:
        status_label = "Blocked by Gate"
        status_badge = "badge-blocked"
    elif has_repair and has_order:
        status_label = "Repaired & Ordered"
        status_badge = "badge-repair"
    elif has_failed:
        status_label = "Payment Failed"
        status_badge = "badge-failed"
    elif has_error:
        status_label = "Security Intercept"
        status_badge = "badge-danger"
    else:
        status_label = "In Progress"
        status_badge = "badge-neutral"

    return {
        "status_label": status_label,
        "status_badge": status_badge,
        "gate_action": gate_action,
        "rounds": max(rounds_count, 1),
        "final_amount_minor": final_amount_minor,
        "event_count": len(events),
        "last_timestamp": last_timestamp,
        "kind": kind,
    }


def _enrich_event_for_display(event: Any) -> dict[str, Any]:
    """Transform raw TradeEvent into rich view-model for trace timeline."""
    payload = _parse_payload(event.payload)
    event_type = event.event_type

    phase_code = "00"
    phase_name = "AUDIT"
    phase_class = "phase-audit"
    gate_highlight = ""

    if event_type == "intent_received":
        phase_code = "01"
        phase_name = "INTENT"
        phase_class = "phase-intent"
    elif event_type == "offer_proposed":
        phase_code = "02"
        phase_name = "NEGOTIATION"
        phase_class = "phase-negotiation"
    elif event_type == "gate_decision":
        phase_code = "03"
        phase_name = "COMMERCEPROOF GATE"
        phase_class = "phase-gate"
    elif event_type == "order_created":
        phase_code = "04"
        phase_name = "EXECUTION (RAZORPAY)"
        phase_class = "phase-execution"
    elif event_type in ("payment_captured", "payment_failed"):
        phase_code = "05"
        phase_name = "SETTLEMENT & WEBHOOK"
        phase_class = "phase-settlement"
    elif event_type == "error":
        phase_code = "ERR"
        phase_name = "SECURITY INTERCEPT"
        phase_class = "phase-error"

    if event_type == "gate_decision":
        action = payload.get("action", "")
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
async def overview_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render the 60-Second Overview Showroom explaining MerchantOS AI architecture and proofs."""
    report_data: dict[str, Any] | None = None
    dev_report_path = DATA_DIR / "evaluation_report_dev.json"
    if dev_report_path.exists():
        try:
            with open(dev_report_path, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception:
            report_data = None

    divergence_svg = render_divergence_svg(data_dict=report_data)

    # Read latest validation report for proof strip
    last_live_razorpay = "not run"
    last_live_llm = "not run"
    val_report_path = DATA_DIR / "validation_report.json"
    if val_report_path.exists():
        try:
            with open(val_report_path, "r", encoding="utf-8") as f:
                val_data = json.load(f)
                for r in val_data.get("results", []):
                    c_id = r.get("check_id")
                    st = r.get("status")
                    lat = r.get("latency_ms", 0)
                    ev_str = r.get("evidence_json", "")
                    if c_id == "live_razorpay":
                        if st == "pass":
                            ev = json.loads(ev_str) if ev_str else {}
                            oid = ev.get("order_id", "order_xxx")
                            last_live_razorpay = f"pass {oid} · {lat}ms"
                        elif st == "skipped":
                            last_live_razorpay = "skipped (mock)"
                        elif st == "fail":
                            last_live_razorpay = f"fail ({lat}ms)"
                    elif c_id == "live_llm":
                        if st == "pass":
                            ev = json.loads(ev_str) if ev_str else {}
                            model = ev.get("model", "llm")
                            last_live_llm = f"pass {model} · {lat}ms"
                        elif st == "skipped":
                            last_live_llm = "skipped (mock)"
                        elif st == "fail":
                            last_live_llm = f"fail ({lat}ms)"
        except Exception:
            pass

    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context={
            "divergence_svg": divergence_svg,
            "tests_passing": TESTS_PASSING,
            "last_live_razorpay": last_live_razorpay,
            "last_live_llm": last_live_llm,
            "health": _get_health_chips(settings),
            "active_nav": "overview",
        },
    )


@router.get("/live", response_class=HTMLResponse)
async def live_trading_floor(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render The Trading Floor live theatre view (Phase 12 Centerpiece)."""
    return templates.TemplateResponse(
        request=request,
        name="live.html",
        context={
            "settings": settings,
            "health": _get_health_chips(settings),
            "active_nav": "live",
        },
    )


@router.get("/history", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def history_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
) -> HTMLResponse:
    """Render the Persistent Trade History Session Archive."""
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
                "kind": summary["kind"],
            }
        )

    # Sort sessions newest-first
    sessions_data.reverse()

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "sessions": sessions_data,
            "total_sessions": len(sessions_data),
            "total_converted": total_converted,
            "total_blocked": total_blocked,
            "total_failed_or_error": total_failed_or_error,
            "settings": settings,
            "health": _get_health_chips(settings),
            "active_nav": "history",
        },
    )


@router.get("/dashboard/trace/{session_id}", response_class=HTMLResponse)
async def dashboard_trace(
    session_id: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
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
            "settings": settings,
            "health": _get_health_chips(settings),
            "active_nav": "history",
        },
    )


@router.get("/evidence", response_class=HTMLResponse)
async def evidence_lab_page(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> HTMLResponse:
    """Render the Evidence Lab page proving empirical benchmark and invariant defenses."""
    # 1. Load Dev and Heldout Evaluation Reports
    dev_data: dict[str, Any] | None = None
    heldout_data: dict[str, Any] | None = None

    dev_path = DATA_DIR / "evaluation_report_dev.json"
    if dev_path.exists():
        try:
            with open(dev_path, "r", encoding="utf-8") as f:
                dev_data = json.load(f)
        except Exception:
            dev_data = None

    heldout_path = DATA_DIR / "evaluation_report_heldout.json"
    if heldout_path.exists():
        try:
            with open(heldout_path, "r", encoding="utf-8") as f:
                heldout_data = json.load(f)
        except Exception:
            heldout_data = None

    dev_chart_svg = render_divergence_svg(data_dict=dev_data)
    heldout_chart_svg = render_divergence_svg(data_dict=heldout_data)

    # 2. Load 12 Stratified Evidence Samples
    evidence_samples: list[dict[str, Any]] = []
    samples_path = DATA_DIR / "evidence_samples.json"
    if samples_path.exists():
        try:
            with open(samples_path, "r", encoding="utf-8") as f:
                evidence_samples = json.load(f)
        except Exception:
            evidence_samples = []

    # 3. Load Adversarial Evidence
    adversarial_records: list[dict[str, Any]] = []
    adv_path = DATA_DIR / "adversarial_evidence.json"
    if adv_path.exists():
        try:
            with open(adv_path, "r", encoding="utf-8") as f:
                adversarial_records = json.load(f)
        except Exception:
            adversarial_records = []

    # 4. Load Leakage Proof
    leakage_proof: dict[str, Any] | None = None
    leak_path = DATA_DIR / "leakage_proof.json"
    if leak_path.exists():
        try:
            with open(leak_path, "r", encoding="utf-8") as f:
                leakage_proof = json.load(f)
        except Exception:
            leakage_proof = None

    # 5. Load Pytest and Validation Reports
    test_run_report: dict[str, Any] | None = None
    test_run_path = DATA_DIR / "test_run_report.json"
    if test_run_path.exists():
        try:
            with open(test_run_path, "r", encoding="utf-8") as f:
                test_run_report = json.load(f)
        except Exception:
            test_run_report = None

    val_report: dict[str, Any] | None = None
    val_path = DATA_DIR / "validation_report.json"
    if val_path.exists():
        try:
            with open(val_path, "r", encoding="utf-8") as f:
                val_report = json.load(f)
        except Exception:
            val_report = None

    return templates.TemplateResponse(
        request=request,
        name="evidence.html",
        context={
            "dev_chart_svg": dev_chart_svg,
            "heldout_chart_svg": heldout_chart_svg,
            "dev_data": dev_data,
            "heldout_data": heldout_data,
            "evidence_samples": evidence_samples,
            "adversarial_records": adversarial_records,
            "leakage_proof": leakage_proof,
            "test_run_report": test_run_report,
            "val_report": val_report,
            "settings": settings,
            "health": _get_health_chips(settings),
            "active_nav": "evidence",
        },
    )
