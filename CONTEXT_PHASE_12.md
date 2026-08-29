# CONTEXT_PHASE_12

## 1. Phase Identity
- **Phase Number**: 12
- **Phase Name**: The Trading Floor (Live 5-Character Choreography, Paired-Lane Fairness Races, Evaluator Reveals & Persistent History)
- **Build Status**: PASS (Exit Code: 0, 165/165 tests passing in 11.07s)
- **Date / Execution Label**: 2026-08-29
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 12 transforms the MerchantOS AI user interface into **"The Trading Floor"** — a live, server-rendered theatre where the system's five core characters (Robot Customer, Rulebook Clerk, Veteran Salesperson, The Accountant, and Bank + Camera) act out every commerce trade in choreographed real time.

Key innovations delivered:
1. **The Stage**: 5 animated character cards connected by hairline connector tracks with animated traveling token dots and dynamic inner screens.
2. **Paired-Lane Fairness Races**: Simultaneous execution of the Rulebook Clerk (baseline heuristics) and Veteran Salesperson (growth agent) with comparative offer side-by-side display and winner lane highlighting.
3. **Evaluator-Only Ground-Truth Reveal**: Benchmark audit card (true budget, price & delivery sensitivities, divergence factor) revealed strictly after transaction settlement.
4. **Persistent Trade History**: Extended `TradeLedger` with optional JSONL disk persistence (`data/ledger_history.jsonl`, capped at 2000 events) and a dedicated `/history` archive route.
5. **Live Health Monitoring**: Topbar status chips reading `data/validation_report.json` to show live LLM latency and Razorpay test-mode gateway status.

---

## 3. Architecture & Core Components

### 3.1 Design Language ("Minimal Canvas, Maximal Life")
- **Palette**: Strict Phase 09 light editorial tokens (`--paper #FAFAF8`, `--surface #FFFFFF`, `--hairline #E6E6E0`, `--ink #17171C`, `--accent #1F4FD8`, and semantic softs).
- **Actor Accent Dots & Borders**:
  - `Buyer`: `--ink` (#17171C)
  - `Clerk`: `#8A8A93`
  - `Salesperson`: `--accent` (#1F4FD8)
  - `Accountant`: `--warning` (#B45309)
  - `Bank + Camera`: `--success` (#15803D)
- **Choreography & Motion**: 200-400ms ease-out transitions, traveling connector dots, 120ms staggered check animations inside the gate card, tabular count-up numerals on completion, and full `@media (prefers-reduced-motion: reduce)` support.

### 3.2 Routes & Navigation
- `GET /live`: The Trading Floor centerpiece (`live.html`).
- `GET /history`: Persistent session registry & archive (`history.html`).
- `GET /dashboard`: Backward-compatible alias of `/history`.
- `GET /demo`: HTTP 302 redirect to `/live`.
- `GET /`: Showroom overview with hero CTAs `[Enter the Trading Floor]` (accent) and `[See the evidence]` (outline).
- **Topbar Nav Order**: `Overview` / `Trading Floor` / `History` / `Validation` + live health status chips.

### 3.3 Persistent Trade Ledger (`core/merchantos_core/ledger/trade_ledger.py`)
- `TradeLedger(persist_path: Path | None = None)`:
  - In-memory by default (ensures 100% hermetic isolation for test suites).
  - When `persist_path` is configured: auto-reloads last 2000 events from JSONL on initialization and appends new `TradeEvent`s on each `record_event()` under thread-safe lock.
- `Settings.ledger_persist_enabled: bool = False`: Wired in `deps.py` to `data/ledger_history.jsonl`.

### 3.4 Theatre Choreography Protocol (`apps/api/merchantos_api/theater.py`)
- `POST /api/theater/run`: Validates request (`utterance`, `random`, `mode`, `use_live_llm`), rejects invalid live LLM requests with 409, generates lossy buyer utterances on `random=true`, and launches daemon thread orchestrator.
- `GET /api/theater/events?run_id=`: Streams SSE sequence:
  1. `intent` (Robot Customer)
  2. `clerk` (Rulebook Clerk; Race mode only)
  3. `salesperson` (Veteran Salesperson; live LLM or mock with fallback)
  4. `offers` (System)
  5. `gate` (The Accountant; 4 CommerceProof invariant checks)
  6. `razorpay` (Bank + Camera; authorized order creation)
  7. `settle` (Bank + Camera; HMAC-SHA256 verified capture)
  8. `outcome` (System; conversion evaluation across lanes)
  9. `reveal` (System; evaluator ground-truth reveal)
- Replay buffering in `TheaterSessionManager` prevents race conditions when clients connect after background execution starts.

---

## 4. Verification & Testing
- Total test count: **165 / 165 passed in 11.07s** (0 failures, 0 errors, 0 skips).
- Bounded async testing patterns with `pytest-timeout = 20s`.
