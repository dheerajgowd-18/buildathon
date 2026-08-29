# CONTEXT_PHASE_10

## 1. Phase Identity
- **Phase Number**: 10
- **Phase Name**: UI Remediation & Dynamic Layer (SSE Live Streaming, Animated Trace & Demo Console)
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-29
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 10 completes MerchantOS AI by pairing critical visual remediations with the **Dynamic Layer** — enabling judges and operators to interact with the system live from a browser.

Judges can now enter arbitrary buyer utterances or select adversarial attack suites, watch the system negotiate and apply CommerceProof invariants in real time over Server-Sent Events (SSE), and inspect the resulting cryptographic audit trail without touching a terminal.

### Key Deliverables:
1. **UI Remediation (Section 10.0)**:
   - Fixed chart label collisions in `apps/api/merchantos_api/charts.py`: delta chips sit `min(r_y, g_y) - 46` with 8px+ clearance above value labels; increased SVG height to `340px` and `plot_y = 64px` for 96%+ bars.
   - Dynamic passing test count via `apps/api/merchantos_api/build_info.py` (`TESTS_PASSING = 140`) rendered directly in the Overview KPI band (`140/140`).
   - Hero button "Run the demo" updated to link directly to `/demo`.
   - Registry empty state updated with primary CTA button "Open Demo Console" linking `/demo`.
   - Standardized page H1s across all views to `28px, weight 650, letter-spacing -0.02em, sans`.
2. **TradeLedger Subscription Architecture (`core/merchantos_core/ledger/trade_ledger.py`)**:
   - Implemented thread-safe `subscribe(maxsize=1000)` and `unsubscribe(q)` methods.
   - `record_event` puts events into active subscriber queues non-blocking (`drop on full`), guaranteeing zero latency impact on transaction writers.
3. **SSE & Summary Streaming Endpoints (`apps/api/merchantos_api/routers/demo.py`)**:
   - `GET /api/events?session_id=<optional>`: FastAPI `StreamingResponse` (media type `text/event-stream`) streaming real-time JSON event packets.
   - `GET /api/summary`: Aggregate counts (`total_sessions`, `converted`, `blocked`, `declined`) for instant UI counter updates.
4. **Interactive Demo Console (`GET /demo` & API Endpoints)**:
   - `demo.html` providing clean 2-column layout: control triggers on the left, real-time monospace terminal on the right with direct trace deep-linking.
   - `POST /api/demo/negotiate`: Autonomous commercial proposal with live character validation (1..500 chars).
   - `POST /api/demo/injection`: Jailbreak override attack test intercepted and neutralized by CommerceProof.
   - `POST /api/demo/cart-mutation`: Multi-stage cart tampering attack demonstrating ledger cross-check defense and subsequent recovery.
   - `POST /api/demo/live-order`: Live Razorpay order creation check (returns 409 when in mock mode).
5. **Dynamic Frontend Engine (`apps/api/merchantos_api/static/live.js`)**:
   - Pure vanilla ES6, zero external dependencies, zero CDNs.
   - Real-time row prepending and KPI updates on the Session Registry (`/dashboard`).
   - Live event card streaming and smart auto-scrolling on the Trace Visualizer (`/dashboard/trace/{session_id}`).
   - Interactive runner with live counter on the Demo Console (`/demo`).
   - Full support for `prefers-reduced-motion`.

---

## 3. Exact File Tree Additions & Modifications
```
merchantos-ai/
  CONTEXT_PHASE_10.md                        <-- Phase 10 Context Handoff Artifact
  REVIEW_PHASE_10.md                         <-- Phase 10 Review & Verification Artifact
  apps/
    api/
      merchantos_api/
        build_info.py                        <-- Centralized dynamic test count constant
        charts.py                            <-- Remediated SVG chart generator (headroom & clearance)
        demo_orchestrator.py                 <-- Background demo worker and adversarial runner
        main.py                              <-- Registered demo router and static files mount
        routers/
          dashboard.py                       <-- Uses build_info.TESTS_PASSING in overview context
          demo.py                            <-- SSE /api/events, /api/summary, and /api/demo/* routes
        static/
          design.css                         <-- Light-mode tokens & styling
          live.js                            <-- Vanilla SSE client & dynamic DOM updater
        templates/
          base.html                          <-- Master layout with Demo Console nav link & live.js script
          demo.html                          <-- Interactive Demo Console UI template
          index.html                         <-- Registry with live table hooks & empty state CTA
          overview.html                      <-- Showroom with dynamic test count & /demo hero button
          trace.html                         <-- Chronological trace with live SSE timeline hooks
  core/
    merchantos_core/
      ledger/
        trade_ledger.py                      <-- Extended with subscribe/unsubscribe event queue methods
  tests/
    integration/
      test_dashboard.py                      <-- Showroom & design system integration tests
      test_demo_console.py                   <-- Demo console & scenario trigger integration tests
      test_sse.py                            <-- Server-Sent Events stream & summary tests
    unit/
      test_trade_ledger.py                   <-- Unit tests for TradeLedger subscription & concurrency
```

---

## 4. Route Map (Complete System)

| Method | Path | Template / Content | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | `overview.html` | 60-Second Showroom: Hero, Lifecycle Rail, Divergence Chart, KPIs, Topology, Security |
| `GET` | `/dashboard` | `index.html` | Live Ledger Session Registry: Real-time table prepending via SSE |
| `GET` | `/dashboard/trace/{session_id}` | `trace.html` | Chronological Trace Visualizer: Real-time event card append via SSE |
| `GET` | `/demo` | `demo.html` | Interactive Demo Console: Sandbox controls and execution terminal |
| `GET` | `/api/events` | `text/event-stream` | Server-Sent Events stream of TradeEvents with session filtering |
| `GET` | `/api/summary` | JSON | Aggregate KPI counts (`total_sessions`, `converted`, `blocked`, `declined`) |
| `POST` | `/api/demo/negotiate` | JSON | Trigger autonomous negotiation demo flow |
| `POST` | `/api/demo/injection` | JSON | Trigger prompt injection attack demo |
| `POST` | `/api/demo/cart-mutation` | JSON | Trigger cart mutation attack and recovery demo |
| `POST` | `/api/demo/live-order` | JSON | Trigger live Razorpay order test (409 in mock mode) |
| `GET` | `/healthz` | JSON | Service health and readiness endpoint |
| `POST` | `/api/v1/payments/razorpay/webhook` | JSON | Razorpay HMAC-SHA256 verified webhook receiver |

---

## 5. Execution & Submission Guide

```bash
# 1. Run full test suite (140 tests)
pytest

# 2. Run Paired Evaluation Benchmark
python scripts/run_evaluation.py --dataset dev

# 3. Launch FastAPI Development Server
uvicorn merchantos_api.main:app --reload --port 8000
```
- **Showroom Overview**: `http://localhost:8000/`
- **Interactive Demo Console**: `http://localhost:8000/demo`
- **Live Ledger Registry**: `http://localhost:8000/dashboard`
