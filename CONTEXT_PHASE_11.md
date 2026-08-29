# CONTEXT_PHASE_11

## 1. Phase Identity
- **Phase Number**: 11
- **Phase Name**: Validation Center (Hermetic Logic Proofs & Live Connectivity Verification)
- **Build Status**: PASS (Exit Code: 0, 155/155 tests passing in < 6.0s)
- **Date / Execution Label**: 2026-08-29
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 11 implements the **Validation Center** — a dashboard-native, streaming verification environment proving that both internal hermetic contracts (HMAC roundtrips, canonical hashing, CommerceProof discount clamping, ground-truth leakage CI scans, deterministic negotiation, non-blocking ledger subscriptions) and live external integrations (Razorpay test-mode orders and OpenAI-compatible LLM endpoints) execute correctly.

All validation runs stream real-time updates directly to the web UI via Server-Sent Events (SSE), and test results are recorded programmatically via `scripts/record_test_run.py` to `data/test_run_report.json`.

## 3. Key Components Implemented

### 3.1 Strict Validation Data Contracts (`core/merchantos_core/contracts.py`)
- `ValidationCheckResult`: Strongly typed record representing an individual check result (`check_id`, `name`, `category: Literal["hermetic", "live_razorpay", "live_llm"]`, `status: Literal["pass", "fail", "skipped"]`, `latency_ms`, `detail`, `evidence_json`, `timestamp`). Strict `extra="forbid"`.
- `ValidationReport`: Aggregated report of a complete validation run (`run_id`, `scope: Literal["hermetic", "live", "all"]`, `started_at`, `finished_at`, `overall_status: Literal["running", "pass", "fail"]`, `results: list[ValidationCheckResult]`).

### 3.2 Named Validation Checks (`core/merchantos_core/validation/checks.py`)
- **Hermetic Checks**:
  1. `hmac_webhook_roundtrip`: Cryptographically verifies HMAC-SHA256 signature on valid webhook payloads and asserts rejection of tampered payloads.
  2. `canonical_hash_determinism`: Asserts deterministic SHA-256 state hashing and divergence upon 1-paise modifications.
  3. `commerceproof_clamp`: Asserts invariant clamping of an illegal 50% discount offer to policy discount caps and margin floors.
  4. `ground_truth_leakage_scan`: Scans 150 benchmark scenarios to assert zero internal evaluation keys or raw minor values leak into buyer utterances.
  5. `negotiation_determinism`: Asserts RulesBaselineAgent produces bit-identical proposals on repeat evaluation.
  6. `ledger_subscription_roundtrip`: Asserts thread-safe non-blocking real-time event dispatch and clean unsubscription.
- **Live External Checks**:
  1. `live_razorpay`: Creates real test-mode ₹1.00 order via `POST /v1/orders`, re-verifies amount via `GET /v1/orders/{order_id}`, and safely redacts secret keys in error messages. Gracefully skips when `RAZORPAY_USE_MOCK=True`.
  2. `live_llm`: Pings OpenAI-compatible completion endpoint via lightweight `provider.ping()`, verifies response, measures latency, and redacts API keys. Gracefully skips when `LLM_USE_MOCK=True`.

### 3.3 Thread-Safe Validation Runner (`core/merchantos_core/validation/runner.py`)
- Manages subscriber queues (`subscribe()` / `unsubscribe()`).
- Executes check suites sequentially on a background daemon thread.
- Broadcasts non-blocking `ValidationCheckResult` events to active SSE listeners.
- Persists final results to `data/validation_report.json` and caches `_last_report` in-memory.

### 3.4 Validation API Router (`apps/api/merchantos_api/routers/validation.py`)
- `GET /validation`: Renders the Validation Center UI.
- `GET /api/validation/report`: Returns latest `ValidationReport` or `{"report": null}`.
- `GET /api/validation/testrun`: Returns contents of `data/test_run_report.json`.
- `POST /api/validation/run`: Triggers background validation run (`scope: "hermetic" | "live" | "all"`).
- `GET /api/validation/events`: Streams real-time SSE check results (`: connected`, `event: check`, `event: done`).

### 3.5 Automated Test Recorder (`scripts/record_test_run.py`)
- Programmatically executes pytest with JUnit XML output (`--junitxml=data/pytest_results.xml`).
- Parses XML and generates `data/test_run_report.json`.
- Exits with pytest return code for automated CI validation.

### 3.6 Frontend UI & Design Integration
- **Validation Dashboard (`apps/api/merchantos_api/templates/validation.html`)**: Features status strip, control buttons, and dynamic streaming results table with slide-in animations.
- **Top Navigation Bar (`apps/api/merchantos_api/templates/base.html`)**: Added "Validation" link.
- **Overview Proof Strip (`apps/api/merchantos_api/templates/overview.html`)**: Hairline status strip under KPI band summarizing hermetic suite status, latest Razorpay connectivity, and latest LLM latency.
- **Dynamic JavaScript Layer (`apps/api/merchantos_api/static/live.js`)**: Real-time SSE streaming client updating validation table rows and status badges.

## 4. Verification & Testing
- Total passing tests: **155 / 155 tests passing** (0 failures, 0 errors, 0 skips).
- Test execution time: **5.84s** on local machine with full `pytest-timeout` hang guards active.
