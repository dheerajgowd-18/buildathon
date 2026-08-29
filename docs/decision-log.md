# Decision Log — What Was Cut and Why (Master Plan §18 / §20)

This document records architectural decisions, scoping trade-offs, and deliberate omissions made during the development of MerchantOS AI for the Razorpay Buildathon.

---

## 1. Paired Benchmark Sample Size: 150 Scenarios vs 2,000+ Aspirational
- **Decision**: Evaluated 150 seed-locked scenarios (100 development / 50 held-out) instead of 2,000+ aspirational full-scale runs.
- **Rationale**: Time and computation constraint for deterministic CI turnaround (<15s test runtime). The empirical divergence-curve direction is statistically consistent across both the development and held-out test splits. Disclosed prominently in `EVALUATION.md` Limitations.

---

## 2. Treatment Arm Benchmark: Deterministic MockLLMProvider
- **Decision**: The treatment arm in the benchmark evaluation harness runs against `MockLLMProvider` rather than live OpenAI/Groq API endpoints.
- **Rationale**: Ensures 100% reproducible, zero-cost, hermetic paired evaluations without rate-limit flakes or non-deterministic test noise. Live-LLM connectivity, token handling, and latency are verified independently via the Validation Center (`/validation`) and live Trading Floor toggle. Disclosed in `EVALUATION.md`.

---

## 3. Buyer-Type Segmentation: Divergence & Category Tiering
- **Decision**: Buyer segmentation is reported by divergence tier (Low `<0.3`, Medium `0.3-0.6`, High `>=0.6`) and product category (laptops, tablets, audio, smartwatches). Explicit behavioral persona segmentation (e.g., brand-sensitive, bundle-seeking) is deferred beyond the P0 core subset.
- **Rationale**: Stated-vs-true preference divergence is the load-bearing independent variable that directly tests the core thesis.

---

## 4. One-Shot AI Ablation Arm (P1): Cut
- **Decision**: Omitted the single-turn one-shot AI ablation arm.
- **Rationale**: The multi-turn paired comparison between `RulesBaselineAgent` and `MerchantGrowthAgent` directly validates multi-round bargaining dynamics and concession modeling.

---

## 5. Sensitivity Sweep Across Noise Settings (P1): Cut
- **Decision**: Reported a single calibrated configuration across low, medium, and high divergence rather than a continuous multi-dimensional noise parameter sweep.
- **Rationale**: Fixed calibration provides clear, auditable categorical buckets for judge comprehension.

---

## 6. Oracle-Intent Upper-Bound Arm (P2): Cut
- **Decision**: Omitted the oracle-intent upper-bound comparison arm.
- **Rationale**: Ground truth buyer intent is strictly quarantined from decision agents by construction (`AgentInput` contract boundary).

---

## 7. Database Engine: In-Memory TradeLedger + JSONL Persistence (§14)
- **Decision**: Replaced PostgreSQL with an in-memory `TradeLedger` featuring optional JSONL disk persistence (`data/ledger_history.jsonl`, capped at 2,000 events).
- **Rationale**: Ensures instant, zero-dependency local execution for judging while preserving full immutable session history and cryptographic auditability. Production deployments can swap the persistence adapter to PostgreSQL.

---

## 8. Cost & Token Accounting per Session
- **Decision**: Reported as ₹0 under mock provider and live ping latency via the Validation Center; full token usage accounting per session is deferred.
- **Rationale**: Real-world token economics depend on host provider model selection; latency and fallback reliability are the critical runtime constraints.

---

## 9. Frontend Framework: Server-Rendered Jinja + Vanilla JS
- **Decision**: Not a cut — Master Plan §14 explicitly mandated a server-rendered UI without bloated client-side frameworks (no React, no Next.js, no external CDNs).
- **Outcome**: Exceeded the specification by delivering "The Trading Floor" live theatre with choreographed SSE animations, tabular numerals, and accessibility in pure HTML, CSS, and vanilla JS.
