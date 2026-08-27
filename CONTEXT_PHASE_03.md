# CONTEXT_PHASE_03

## 1. Phase Identity
- **Phase Number**: 03
- **Phase Name**: Strict Agent Input Boundary & Deterministic Rules Baseline Agent
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 03 implements the strict Agent Input Boundary (`AgentInput`) and the deterministic Rules Baseline Agent (`RulesBaselineAgent`). The boundary physically prevents downstream decision agents from accessing ground-truth buyer intent or simulation metadata via strict Pydantic v2 validation (`extra="forbid"`). The Rules Baseline Agent parses buyer natural language utterances using Python standard library regular expressions, extracts structured signals (`ExtractedSignals`), selects products from the available catalog, and calculates commercial discounts mathematically guaranteed never to exceed merchant discount caps or breach margin floors. All 63 unit, integration, and adversarial tests pass deterministically.

## 3. Repository State
- **Git Initialized**: Yes
- **Branch Name**: `main`
- **Staging Status**: Staged with `git add -A`, ready for human reviewer commit.

## 4. Exact File Tree Additions
```
merchantos-ai/
  CONTEXT_PHASE_03.md
  REVIEW_PHASE_03.md
  core/
    merchantos_core/
      contracts.py                 <-- Added AgentInput, ExtractedSignals, ProposedOffer
      agents/
        __init__.py                <-- Exports RulesBaselineAgent
        rules_baseline.py          <-- Deterministic Rules Baseline Agent
  tests/
    unit/
      test_agent_boundary.py       <-- Physical boundary enforcement & ground-truth rejection
      test_rules_baseline.py       <-- Signal extraction, policy compliance & determinism tests
```

## 5. Dependencies
- Strictly standard library (`re`, `json`, `pathlib`, `typing`), `pydantic>=2.0`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, and `pytest`.
- Zero external NLP or machine learning libraries (no spaCy, no NLTK, no transformers, no LangChain).

## 6. Public Interfaces Created

### 1. Data Contracts (`merchantos_core.contracts`)
- `AgentInput`:
  - **Import Path**: `from merchantos_core.contracts import AgentInput` (also exported from `merchantos_core`)
  - **Fields**:
    - `session_id: str` (min_length=1)
    - `nl_utterance: str` (min_length=1)
    - `available_catalog: list[Product]` (min_length=1)
    - `merchant_policy: MerchantPolicy`
  - **Invariants**: `extra="forbid"`. Strictly contains zero ground-truth fields (`BuyerIntent`, `price_sensitivity`, `budget_max_minor`, etc.).
- `ExtractedSignals`:
  - **Import Path**: `from merchantos_core.contracts import ExtractedSignals`
  - **Fields**:
    - `estimated_budget_minor: int | None` (ge=0, integer paise)
    - `estimated_category: str | None`
    - `keywords: list[str]`
    - `urgency_level: Literal["low", "medium", "high"]`
  - **Invariants**: `extra="forbid"`.
- `ProposedOffer`:
  - **Import Path**: `from merchantos_core.contracts import ProposedOffer`
  - **Fields**:
    - `offer_id: str` (min_length=1)
    - `session_id: str` (min_length=1)
    - `selected_sku_id: str` (min_length=1)
    - `proposed_price_minor: int` (ge=0, integer paise)
    - `discount_minor: int` (ge=0, integer paise)
    - `shipping_tier: Literal["standard", "express"]`
    - `rationale: str` (min_length=1)
  - **Invariants**: `extra="forbid"`, `proposed_price_minor + discount_minor == product.base_price_minor`.

### 2. Rules Baseline Agent (`merchantos_core.agents.rules_baseline`)
- **Import Path**: `from merchantos_core.agents import RulesBaselineAgent` or `from merchantos_core.agents.rules_baseline import RulesBaselineAgent`
- **Class**: `RulesBaselineAgent`
  - `extract_signals(self, utterance: str) -> ExtractedSignals`:
    Deterministic regex and string matching to parse buyer budget, category, urgency, and keywords.
  - `score_and_propose(self, agent_input: AgentInput) -> ProposedOffer`:
    Validates input type, filters catalog, computes constrained discounts, selects shipping tier, and returns deterministic offer.

## 7. The Fairness Guarantee

### Physical Boundary Enforcement
1. **Schema Isolation**: `AgentInput` defines only the exact fields a real merchant decision agent would receive from the front-end: `session_id`, `nl_utterance`, `available_catalog`, and `merchant_policy`.
2. **Rejection of Ground Truth**: `AgentInput` enforces `model_config = ConfigDict(extra="forbid")`. Any attempt to pass `BuyerIntent`, `SimulatedScenario`, or dictionaries containing ground-truth evaluation fields (e.g. `price_sensitivity`, `budget_max_minor`, `acceptance_threshold`, `stated_vs_true_divergence`, `priority`, `hard_exclusions`) triggers an immediate Pydantic `ValidationError`.
3. **Agent Signature Restriction**: `RulesBaselineAgent.score_and_propose` strictly accepts `AgentInput`. Passing incompatible objects or dictionary payloads with extra keys is rejected at runtime.

## 8. Signal Extraction Logic

### Budget Extraction Regex
Budget parsing extracts buyer target amounts deterministically into minor units (paise):
1. **'k' / 'K' Notation**: `(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b`
   - Maps `"under 60k"`, `"60k"`, `"budget 50k"` -> `int(round(value * 1000 * 100))` paise.
2. **'lakh' / 'lac' Notation**: `(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b`
   - Maps `"1 lakh"`, `"1.5 lakhs"` -> `int(round(value * 100000 * 100))` paise.
3. **Explicit Currency Notation**: `(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+)`
   - Maps `"₹50,000"`, `"₹85,000"`, `"Rs. 60,000"` -> `int(round(value * 100))` paise.
4. **Context Phrases**: `(?:under|around|budget|below|less than|within|approx|max(?:imum)?|upto|up to|in the)\s*(?:of\s*)?(\d{1,3}(?:,\d{2,3})+|\d{4,})`
   - Maps `"under 60000"`, `"budget 50000"` -> `int(round(value * 100))` paise.

### Urgency Extraction Patterns
1. **High Urgency (`"high"`)**:
   - `\b(?:urgent|urgently|fast|faster|tomorrow|express|asap|expedited|immediately|quick|quickly)\b`
   - `\b(?:within\s+(?:1|2)\s+days?)\b`
   - `\b(?:1|2)\s*[- ]day\s+delivery\b`
2. **Low Urgency (`"low"`)**:
   - `\b(?:flexible|no\s+hurry|relaxed|no\s+rush|can\s+wait|not\s+urgent|take\s+your\s+time)\b`
   - `\b(?:within\s+[5-9]\s+days?|week\s+or\s+more)\b`
3. **Medium Urgency (`"medium"`)**:
   - Matches `"standard"` or defaults to `"medium"` when neither high nor low patterns match.

### Pricing & Margin Floor Mathematical Guarantees
For any selected product:
- `max_discount_cap_minor = int(base_price_minor * policy.discount_cap_pct)`
- `min_price_margin_minor = int(cost_minor * (1.0 + policy.margin_floor_pct))`
- `min_price_cap_minor = base_price_minor - max_discount_cap_minor`
- `min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)`
- `max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)`
- Invariant Guaranteed: `proposed_price_minor >= min_price_margin_minor` AND `discount_minor <= max_discount_cap_minor`.

## 9. Phase 4 Handoff (Merchant Growth Agent)

### Ingestion and Interface Guidelines:
1. **Identical Signature**: The Phase 4 Merchant Growth Agent (LLM-based) MUST implement the exact same method signature:
   ```python
   class MerchantGrowthAgent:
       def score_and_propose(self, agent_input: AgentInput) -> ProposedOffer:
           ...
   ```
2. **Apples-to-Apples Evaluation**: The Phase 6 Evaluation Harness will iterate over test scenarios, package each into an `AgentInput`, pass it independently to `RulesBaselineAgent` and `MerchantGrowthAgent`, and compare downstream business metrics (conversion rate, revenue, margin preserved).
3. **No Direct Scenario Access**: Neither agent is permitted to receive `SimulatedScenario` or `BuyerIntent`.

## 10. Commands

### Run Full Test Suite
```bash
pytest -v
```

### Run Phase 03 Boundary and Baseline Tests Exclusively
```bash
pytest tests/unit/test_agent_boundary.py tests/unit/test_rules_baseline.py -v
```

### Run Adversarial Ground-Truth Leakage Test
```bash
pytest tests/adversarial/test_leakage.py -v
```
