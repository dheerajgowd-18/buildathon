# CONTEXT_PHASE_09

## 1. Phase Identity
- **Phase Number**: 09
- **Phase Name**: Light-Mode Editorial Showroom & Design System Redesign
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-28
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 09 delivers a complete visual redesign of the MerchantOS AI Judge Dashboard into a light-mode, editorial-minimalist **Showroom** that communicates the entire system story in 60 seconds.

Guided by the constraint of *Stripe/Linear-grade restraint* and strict prohibition of AI boilerplate (zero dark mode, zero gradients, zero emoji icons, zero external CSS/font CDNs), Phase 09 establishes a clean, hairline-driven design system implemented via semantic CSS, inline SVGs, and FastAPI/Jinja2 server-side rendering.

### Key Deliverables:
1. **Design System & Stylesheet (`apps/api/merchantos_api/static/design.css`)**:
   - Palette tokens (`--paper: #FAFAF8`, `--surface: #FFFFFF`, `--ink: #17171C`, `--muted: #6E6E76`, `--hairline: #E6E6E0`, `--accent: #1F4FD8`, `--success: #15803D`, `--warning: #B45309`, `--danger: #B91C1C`).
   - Strict typography hierarchy: body sans, headline serif (`Charter, Georgia`), monospace code metrics.
   - Restrained hairline borders (1px) and tabular numeric formatting.
2. **Server-Rendered SVG Chart Generator (`apps/api/merchantos_api/charts.py`)**:
   - Generates deterministic, zero-JS, inline SVG grouped bar charts visualizing the **Divergence Thesis** benchmark directly on the page.
3. **Showroom Overview Page (`GET /` rendering `overview.html`)**:
   - **Section 1 (Hero)**: Asymmetric 7/5 two-column layout with serif headline *"The buyer is an AI now. Who negotiates for the merchant?"* and monospace invariant panel (*"LLM PROPOSES. CODE DISPOSES."*).
   - **Section 2 (Lifecycle Rail)**: 5-step numbered horizontal rail (*01 Intent &rarr; 02 Negotiation &rarr; 03 The Gate &rarr; 04 Execution &rarr; 05 Settlement*).
   - **Section 3 (Proof, Not Promises)**: Grouped bar chart SVG with divergence delta table proving +38.5% and +26.3% lift on ambiguous intent.
   - **Section 4 (KPI Band)**: Hairline-separated tabular metric row (+19.0% Conversion Lift, 5.0% Gate Rejection, 121/121 Passing, 1.37 Avg Rounds).
   - **Section 5 (Trust Boundary Topology)**: Full-width inline SVG diagram illustrating the boundary between the probabilistic zone, CommerceProof authority gate, and deterministic payment zone.
   - **Section 6 (Security Posture)**: Hairline table documenting defense-in-depth guarantees (prompt injection, cart mutation, leakage, network retries).
4. **Base Layout & Unified Session Registry (`GET /dashboard` & `GET /dashboard/trace/{session_id}`)**:
   - `base.html` provides sticky topbar with wordmark, mode pill, live pulsing dot, and unified footer.
   - `index.html` and `trace.html` restyled to match the design system tokens.

---

## 3. Exact File Tree Additions & Modifications
```
merchantos-ai/
  CONTEXT_PHASE_09.md                        <-- Phase 09 Context Handoff Artifact
  REVIEW_PHASE_09.md                         <-- Phase 09 Review & Verification Artifact
  apps/
    api/
      merchantos_api/
        charts.py                            <-- Server-side SVG grouped bar chart generator
        main.py                              <-- Mounted /static StaticFiles directory
        routers/
          dashboard.py                       <-- Updated / route for overview.html & /dashboard for registry
        static/
          design.css                         <-- Light-mode design system stylesheet & tokens
        templates/
          base.html                          <-- Master layout with sticky topbar, live dot, and footer
          overview.html                      <-- 6-section 60-second showroom overview page
          index.html                         <-- Restyled live ledger session registry
          trace.html                         <-- Restyled 4-phase chronological trace visualizer
  tests/
    integration/
      test_dashboard.py                      <-- Comprehensive test suite covering showroom, SVG, and design tokens
```

---

## 4. Design System Tokens Specification

```css
:root {
    color-scheme: light;

    /* Palette Tokens */
    --paper: #FAFAF8;          /* Background surface */
    --surface: #FFFFFF;        /* Elevated card surface */
    --ink: #17171C;            /* High-contrast primary text */
    --muted: #6E6E76;          /* Secondary descriptive text */
    --hairline: #E6E6E0;       /* 1px structural dividing rules */
    --accent: #1F4FD8;         /* Single cobalt brand accent */
    --accent-soft: #EEF2FE;    /* Soft accent background */
    --success: #15803D;        /* Approved / Paid green */
    --success-soft: #ECFDF3;   /* Soft success badge fill */
    --warning: #B45309;        /* Repaired / Warning amber */
    --warning-soft: #FFFBEB;   /* Soft warning badge fill */
    --danger: #B91C1C;         /* Blocked / Security red */
    --danger-soft: #FEF2F2;    /* Soft danger badge fill */

    /* Typography Hierarchy */
    --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    --font-serif: Charter, Georgia, "Times New Roman", serif;
    --font-mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
```

---

## 5. Route Map

| Method | Path | Template | Purpose |
| :--- | :--- | :--- | :--- |
| `GET` | `/` | `overview.html` | 60-Second Showroom: Hero, Lifecycle Rail, Divergence Chart, KPIs, Topology, Security |
| `GET` | `/dashboard` | `index.html` | Live Ledger Session Registry: Tabulates all in-memory and persistent sessions |
| `GET` | `/dashboard/trace/{session_id}` | `trace.html` | 4-Phase Chronological Trace Visualizer: Detailed audit log with collapsible raw JSON |
| `GET` | `/healthz` | JSON | API Health and Readiness Check |
| `POST` | `/api/v1/payments/razorpay/webhook` | JSON | HMAC-Verified Webhook Endpoint |

---

## 6. What Phase 10 Must Build (Next Steps)
1. **Server-Sent Events (SSE) Live Ledger Feed**: Real-time event streaming for `/dashboard` when new transactions occur without requiring page refreshes.
2. **Animated Trace Timeline**: Stepped lifecycle animation during live demo evaluation.
3. **Interactive Demo Console / Simulation Trigger**: In-browser sandbox runner allowing judges to test custom buyer utterances directly from the UI.

---

## 7. Execution & Submission Commands
```bash
# 1. Run full test suite (125 tests)
pytest -v

# 2. Run Dev Benchmark
python scripts/run_evaluation.py --dataset dev

# 3. Launch FastAPI Server & View Light-Mode Showroom
uvicorn merchantos_api.main:app --reload --port 8000
```
- Showroom UI: `http://localhost:8000/`
- Live Ledger: `http://localhost:8000/dashboard`
