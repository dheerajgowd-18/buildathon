# REVIEW_PHASE_08

## 1. Machine-Readable Status
```json
{
  "phase": "08",
  "phase_name": "Static Judge Dashboard & Final Documentation Suite",
  "status": "PASS",
  "date": "2026-08-27",
  "exit_code": 0,
  "tests_collected": 116,
  "tests_passed": 116,
  "tests_failed": 0,
  "branch": "main",
  "dependencies_added": ["jinja2"],
  "external_frontend_frameworks": 0
}
```

---

## 2. Acceptance Checklist

- [x] **Static Judge Dashboard Routes (`apps/api/merchantos_api/routers/dashboard.py`)**:
  - [x] `GET /` and `GET /dashboard` endpoints rendering `index.html` with session table, status badges, and aggregate KPIs.
  - [x] `GET /dashboard/trace/{session_id}` rendering `trace.html` with 4-phase chronological lifecycle cards and collapsible raw JSON inspection.
  - [x] Jinja2 filters for currency formatting (`format_inr` displaying paise as e.g. `₹45,000.00`) and JSON pretty-printing (`format_json`).
- [x] **HTML Templates & Self-Contained Styling (`apps/api/merchantos_api/templates/`)**:
  - [x] `index.html`: Clean session registry, summary KPIs (Total Sessions, Converted, Blocked, Security/Declined), and direct trace links.
  - [x] `trace.html`: 4 visually distinct lifecycle phases (Intent & Negotiation, The Gate with green/amber/red disposition, Execution with Razorpay order, Settlement with payment/decline/error).
  - [x] Collapsible `<details>` raw JSON payloads for 60-second judge inspection.
  - [x] Zero external CDN or frontend build pipeline dependencies.
- [x] **Complete Documentation Suite**:
  - [x] `README.md`: 60-second pitch, core architecture invariant ("LLM Proposes, Code Disposes"), Divergence Thesis summary, and quickstart commands.
  - [x] `ARCHITECTURE.md`: ASCII component topology, trust boundaries, and negotiation sequence diagrams.
  - [x] `EVALUATION.md`: Paired evaluation design, divergence bucketing (Dev & Heldout), gate rejection rates, and freeze commit.
  - [x] `SECURITY.md`: Prompt injection neutralization, cart mutation defense, ground-truth isolation, and sandbox guarantees.
  - [x] `DEMO.md`: Step-by-step 5-minute judge demo script with live adversarial run commands.
- [x] **Integration Testing (`tests/integration/test_dashboard.py`)**:
  - [x] `test_dashboard_index_returns_200`: Verifies index route returns HTTP 200 with HTML content and session list.
  - [x] `test_dashboard_trace_returns_200`: Seeds 4-phase lifecycle trace in `TradeLedger` and verifies rendering of order, payment, and gate disposition.
  - [x] `test_dashboard_handles_empty_ledger`: Verifies graceful fallback rendering when `TradeLedger` is empty.
- [x] **Handoff Artifacts**:
  - [x] `CONTEXT_PHASE_08.md` generated at root.
  - [x] `REVIEW_PHASE_08.md` generated at root.

---

## 3. Critical Code Evidence

### A. Dashboard Router (`apps/api/merchantos_api/routers/dashboard.py`)
```python
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

    sessions_data.reverse()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
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
        "trace.html",
        {
            "request": request,
            "session_id": session_id,
            "summary": summary,
            "events": enriched_events,
            "total_events": len(enriched_events),
        },
    )
```

### B. Generated README.md
```markdown
# MerchantOS AI

> **"When the buyer becomes an AI, the merchant needs an AI that negotiates for value under a deterministic constraint gate."**

MerchantOS AI is an agentic merchant intelligence and commerce platform designed to negotiate autonomously with buyer agents, maximize conversion and contribution margin, and enforce zero-defect commercial safety.

---

## 1. The Core Architecture

> **"LLM Proposes, Code Disposes"** — All agentic reasoning (SKU selection, discount strategy, multi-turn concessions) is treated as untrusted commercial proposal; an immutable deterministic control gate (`CommerceProof`) mathematically clamps discounts to margin floors, validates real-time inventory, and cryptographically binds terms before any payment is authorized.
```

---

## 4. Test Execution Evidence

```
============================= test session starts =============================
platform win32 -- Python 3.10.8, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\buildathon
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.9.0, dash-2.18.2, cov-7.1.0
collected 116 items

tests\adversarial\test_cart_mutation.py ..                               [  1%]
tests\adversarial\test_idempotency.py .                                  [  2%]
tests\adversarial\test_leakage.py .                                      [  3%]
tests\adversarial\test_payment_failure.py ..                             [  5%]
tests\adversarial\test_prompt_injection.py ..                            [  6%]
tests\integration\test_dashboard.py ...                                  [  9%]
tests\integration\test_health_endpoint.py ..                             [ 11%]
tests\integration\test_webhook_endpoint.py .......                       [ 17%]
tests\unit\test_agent_boundary.py ...                                    [ 19%]
tests\unit\test_buyer_simulator.py .....                                 [ 24%]
tests\unit\test_commerceproof.py .........                               [ 31%]
tests\unit\test_contracts.py .............                               [ 43%]
tests\unit\test_evaluation_harness.py .....                              [ 47%]
tests\unit\test_growth_agent.py ....                                     [ 50%]
tests\unit\test_hashing.py ......                                        [ 56%]
tests\unit\test_hmac.py .....                                            [ 60%]
tests\unit\test_live_adapter_request_mapping.py ...                      [ 62%]
tests\unit\test_llm_provider.py ....                                     [ 66%]
tests\unit\test_metrics.py .....                                         [ 70%]
tests\unit\test_mock_adapter.py ....                                     [ 74%]
tests\unit\test_negotiation_engine.py ....                               [ 77%]
tests\unit\test_rules_baseline.py .........                              [ 85%]
tests\unit\test_settings.py .....                                        [ 89%]
tests\unit\test_simulator.py .......                                     [ 95%]
tests\unit\test_trade_ledger.py .....                                    [100%]

============================= 116 passed in 0.65s =============================
```

---

## 5. Git Status Evidence
```
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   README.md
	modified:   apps/api/merchantos_api/main.py
	modified:   pyproject.toml

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	ARCHITECTURE.md
	CONTEXT_PHASE_08.md
	DEMO.md
	EVALUATION.md
	REVIEW_PHASE_08.md
	SECURITY.md
	apps/api/merchantos_api/routers/dashboard.py
	apps/api/merchantos_api/templates/
	tests/integration/test_dashboard.py
```
