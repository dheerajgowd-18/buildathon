# CONTEXT_PHASE_13

## 1. Phase Identity
- **Phase Number**: 13 (Final Build Phase)
- **Phase Name**: The Evidence Lab (`/evidence`) & Submission Polish
- **Build Status**: **PASS** (Exit code: 0, 171/171 tests passing in 11.94s)
- **Date / Execution Label**: 2026-08-29
- **Repository Root Path**: `d:\buildathon`

---

## 2. Executive Summary
Phase 13 establishes **The Evidence Lab (`/evidence`)** — the definitive, empirical verification center proving that MerchantOS AI's claims are backed by seed-locked data, paired statistical comparisons, adversarial penetration audits, and cryptographic invariant safety, rather than vanity metrics.

Key deliverables completed:
1. **Evidence Data Generators**:
   - `scripts/generate_evidence_samples.py`: Deterministically selects 12 stratified scenarios (4 low, 4 medium, 4 high divergence) from `data/dev_scenarios.jsonl`, runs `EvaluationHarness` across baseline and growth arms, and outputs `data/evidence_samples.json` alongside `data/leakage_proof.json`.
   - `scripts/generate_adversarial_evidence.py`: Executes in-process penetration attack simulations (prompt injection, cart mutation, payment failure, idempotent replay) and outputs `data/adversarial_evidence.json` with zero secrets.
2. **The Evidence Lab Page (`GET /evidence` -> `evidence.html`)**:
   - **Section 1 ("The Benchmark is Paired")**: Side-by-side SVG divergence charts for Dev (N=100) and Held-Out (N=50) splits, bucketed conversion comparison table, and citation to `v1.0.0-submission-freeze`.
   - **Section 2 ("Twelve Scenarios, Both Arms, Raw")**: Interactive stratified scenario explorer table with expandable rows revealing multi-turn pricing and hidden evaluator-only ground truth.
   - **Section 3 ("Attacks We Survived")**: Adversarial hall of fame cards showing attack name, monospace payload snippet, defense description, trace event tags, and outcome status (`REPAIRED`, `BLOCKED`, `RECOVERED`).
   - **Section 4 ("Leakage: Zero by Construction")**: Hairline audit stats confirming zero internal variable or minor paise leaks across all benchmark scenarios, plus sample audited utterances.
   - **Section 5 ("Continuous Test & Live Verification")**: Pytest execution reports and live Validation Center gateway proofs with direct navigation links.
3. **Documentation Polish**:
   - `EVALUATION.md`: Added mandatory `## Limitations` section (verbatim) and `Frozen at commit: <HASH-PENDING>`.
   - `README.md`: Updated quickstart with Trading Floor, Evidence Lab, Validation Center, and evidence generator scripts (<60s read).
   - `DEMO.md`: Updated 5-minute script pointing to `/live` Race with high-divergence reveal at 0:15-1:15 and `/evidence` at 2:45-3:45.
4. **Integration & Schema Tests**:
   - `tests/integration/test_evidence.py`: 6 tests verifying route 200, missing JSON fallback handling, nav consistency across all 5 pages, overview CTA link, and generator schema validation.

---

## 3. Architecture & Code Map

### 3.1 Data Flow Topology
```
[dev_scenarios.jsonl] 
        |
        v
[generate_evidence_samples.py] -------> [data/evidence_samples.json]
                                 -------> [data/leakage_proof.json]

[Adversarial Attack Suite] 
        |
        v
[generate_adversarial_evidence.py] ----> [data/adversarial_evidence.json]

[evaluation_report_*.json] + [test_run_report.json] + [validation_report.json]
        |
        v
[GET /evidence (dashboard.py)] ---------> [evidence.html (The Evidence Lab)]
```

### 3.2 Key Files Modified / Created
- `scripts/generate_evidence_samples.py`: Stratified sample evaluator and leakage proof generator.
- `scripts/generate_adversarial_evidence.py`: In-process adversarial defense recorder.
- `apps/api/merchantos_api/routers/dashboard.py`: Added `GET /evidence` route with graceful error handling.
- `apps/api/merchantos_api/templates/evidence.html`: The Evidence Lab Jinja template.
- `apps/api/merchantos_api/templates/base.html`: Updated topbar nav (`Overview`, `Trading Floor`, `History`, `Evidence`, `Validation`).
- `apps/api/merchantos_api/templates/overview.html`: Updated hero CTA "See the evidence" to `href="/evidence"`.
- `apps/api/merchantos_api/static/design.css`: Appended Phase 13 styling rules (charts grid, scenario explorer, attack cards, leakage stats).
- `apps/api/merchantos_api/build_info.py`: Updated `TESTS_PASSING = 171`.
- `EVALUATION.md`, `README.md`, `DEMO.md`: Submission documentation polish.
- `tests/integration/test_evidence.py`: 6 integration and unit tests.
