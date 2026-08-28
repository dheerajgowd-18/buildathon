# CONTEXT_PHASE_08

## 1. Phase Identity
- **Phase Number**: 08
- **Phase Name**: Static Judge Dashboard (Trace Visualizer) & Final Documentation Suite
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 08 finalizes MerchantOS AI by delivering the **Static Judge Dashboard** and the complete **Documentation Suite** (README.md, ARCHITECTURE.md, EVALUATION.md, SECURITY.md, DEMO.md), completing the system according to Master Plan §14, §15, and §19.

Per the master mandate: *"The dashboard's only job is 60-second judge comprehension of a live trace. A server-rendered page (FastAPI + Jinja) is enough. Every hour on frontend polish is an hour not spent on the evaluation spine."*

Key Deliverables:
1. **Server-Rendered Judge Dashboard (FastAPI + Jinja2)**: Zero frontend build pipelines, zero external CSS dependencies (immune to network issues during judging), instantaneous server-side rendering.
2. **Session Registry (`GET /` and `GET /dashboard`)**: Tabulates all negotiation and checkout sessions from `TradeLedger` with final settlement statuses, gate dispositions, formatted INR amounts, and quick trace navigation.
3. **60-Second Trace Visualizer (`GET /dashboard/trace/{session_id}`)**: Renders chronological audit traces visually segmented into the 4 lifecycle phases:
   - **Phase A: Intent & Negotiation** (`intent_received`, `offer_proposed`)
   - **Phase B: The Gate** (`gate_decision` — highlighting green `EXECUTE`, amber `REPAIR`, or red `BLOCK`)
   - **Phase C: Execution** (`order_created` with Razorpay order details)
   - **Phase D: Settlement & Audit** (`payment_captured`, `payment_failed`, `error`)
   - Every event includes a collapsible `<details>` tag with syntax-highlighted raw JSON payloads.
4. **Documentation Suite**:
   - `README.md`: The 60-second elevator pitch, architecture summary, divergence thesis summary, and quickstart commands.
   - `ARCHITECTURE.md`: ASCII component topology, trust boundaries, and negotiation sequence diagrams.
   - `EVALUATION.md`: Paired evaluation design, divergence thesis breakdown, gate rejection rates, and dataset freeze commit.
   - `SECURITY.md`: Prompt injection neutralization, cart mutation defense, ground-truth isolation, and sandbox guarantees.
   - `DEMO.md`: Exact 5-minute judge demo script with adversarial triggers.

All 116 unit, integration, adversarial, and dashboard tests pass cleanly and deterministically in under 1 second.

## 3. Repository State
- **Git Initialized**: Yes
- **Branch Name**: `main`
- **Staging Status**: Ready for final submission commit.

## 4. Exact File Tree Additions & Modifications
```
merchantos-ai/
  README.md                          <-- Overwritten with final 60-second pitch & quickstart
  ARCHITECTURE.md                    <-- Trust boundary topology & component diagrams
  EVALUATION.md                      <-- Paired design, empirical divergence thesis, freeze commit
  SECURITY.md                        <-- Defense-in-depth, prompt injection, cart mutation defense
  DEMO.md                            <-- Exact 5-minute demo script & run commands
  CONTEXT_PHASE_08.md                <-- Phase 08 Context Handoff Artifact
  REVIEW_PHASE_08.md                 <-- Phase 08 Review & Verification Artifact
  pyproject.toml                     <-- Added jinja2 dependency
  apps/
    api/
      merchantos_api/
        main.py                      <-- Registered dashboard router
        routers/
          dashboard.py               <-- FastAPI Jinja2 HTML routes for judge dashboard & trace visualizer
        templates/
          index.html                 <-- Session registry and summary KPI cards
          trace.html                 <-- Chronological 4-phase trace visualizer with collapsible raw JSON
  tests/
    integration/
      test_dashboard.py              <-- Tests for dashboard index, 4-phase trace rendering, and empty ledger
```

## 5. Dependencies
- Strictly standard library (`threading`, `json`, `uuid`, `datetime`, `re`, `pathlib`, `typing`, `abc`), `pydantic>=2.0`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, `jinja2`, and `pytest`.
- Zero Node.js, npm, Webpack, or frontend build toolchains.
- Zero external CSS/font CDNs (completely self-contained embedded styling).
- All monetary amounts displayed as formatted INR (e.g. ₹45,000.00) while backend remains integer paise minor units.

## 6. The 60-Second Judge Comprehension Strategy

```
                                [Judge Opens Dashboard]
                                            |
                                            v
                     [http://localhost:8000/dashboard]
                                            |
           +--------------------------------+--------------------------------+
           |                                                                 |
   [Summary KPI Cards]                                            [Session Registry Table]
   - Total Sessions                                               - Clickable Session IDs
   - Converted Settlements                                        - Converted / Blocked / Declined
   - Gate Blocks & Repairs                                        - Formatted INR Amounts
   - Security Rejections                                          - Direct "Inspect Trace ->" Link
           |                                                                 |
           +--------------------------------+--------------------------------+
                                            |
                                            v
                 [Judge Inspects: /dashboard/trace/{session_id}]
                                            |
                                            v
                       +-----------------------------------------+
                       | Phase A: Intent & Negotiation           |
                       | - Buyer NL Utterance                    |
                       | - Proposed SKU, Price, Concession       |
                       +-----------------------------------------+
                                            |
                                            v
                       +-----------------------------------------+
                       | Phase B: The Gate (CommerceProof)       |
                       | - Visual Badge: EXECUTE / REPAIR / BLOCK|
                       | - Margin Floor & Cap Enforcements       |
                       | - Canonical SHA-256 State Hash          |
                       +-----------------------------------------+
                                            |
                                            v
                       +-----------------------------------------+
                       | Phase C: Execution                      |
                       | - Razorpay Order ID & Amount            |
                       +-----------------------------------------+
                                            |
                                            v
                       +-----------------------------------------+
                       | Phase D: Settlement & Audit             |
                       | - Verified Payment Captured (HMAC)      |
                       | - Bank Decline / Cart Mutation Alert    |
                       +-----------------------------------------+
                                            |
                                            v
                       [Collapsible <details> Raw JSON Payloads]
                       (Instant Proof of State Integrity)
```

## 7. Submission Readiness & Commands
```bash
# 1. Run all 116 tests
pytest -v

# 2. Run Dev Benchmark
python scripts/run_evaluation.py --dataset dev

# 3. Run Heldout Benchmark
python scripts/run_evaluation.py --dataset heldout

# 4. Launch FastAPI Application & Dashboard
uvicorn merchantos_api.main:app --reload --port 8000
```
- Dashboard UI: `http://localhost:8000/dashboard`
- API Health: `http://localhost:8000/healthz`
