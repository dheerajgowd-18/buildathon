# CONTEXT_PHASE_02

## 1. Phase Identity
- **Phase Number**: 02
- **Phase Name**: Synthetic Data Generator, Lossy NLG Engine & Pre-Computation
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 02 delivers the deterministic Synthetic Data Generator, the Lossy Natural Language Utterance Engine (NLG), and the pre-computation pipeline. It produces 100 Development scenarios and 50 Held-out evaluation scenarios serialized as JSONL. The lossy NLG engine models human-buyer stated vs. true preference divergence while guaranteeing that ground-truth fields and raw minor currency units are never leaked to downstream decision agents. All 52 unit, integration, and adversarial tests pass deterministically.

## 3. Repository State
- **Git Initialized**: Yes
- **Branch Name**: `main`
- **Staging Status**: Staged with `git add -A`, ready for human reviewer commit.

## 4. Exact File Tree Additions
```
merchantos-ai/
  CONTEXT_PHASE_02.md
  REVIEW_PHASE_02.md
  data/
    dev_scenarios.jsonl
    heldout_scenarios.jsonl
  scripts/
    __init__.py
    generate_scenarios.py
  simulator/
    merchantos_simulator/
      __init__.py
      buyers.py
      marketplace.py
      nlg.py
  tests/
    adversarial/
      __init__.py
      test_leakage.py
    unit/
      test_simulator.py
```

## 5. Dependencies
- Retained strictly to Python standard library (`random`, `json`, `pathlib`, `argparse`), `pydantic>=2.0`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, and `pytest`.
- Zero additional external dependencies (no `faker`, `jinja2`, `numpy`, or `pandas`).

## 6. Public Interfaces Created

### 1. Data Contracts (`merchantos_core.contracts`)
- `Product`:
  - Fields: `sku_id: str`, `name: str`, `category: str`, `cost_minor: int`, `base_price_minor: int`, `inventory_count: int`.
  - Invariants: `base_price_minor >= cost_minor`, integer paise units, `extra="forbid"`.
- `MerchantPolicy`:
  - Fields: `merchant_id: str`, `margin_floor_pct: float`, `discount_cap_pct: float`, `promotion_budget_minor: int`.
  - Invariants: Percentages bounded `[0.0, 1.0]`, `extra="forbid"`.
- `BuyerIntent` *(Ground Truth - Evaluator Only)*:
  - Fields: `session_id: str`, `category: str`, `budget_max_minor: int`, `delivery_days_max: int`, `priority: list[str]`, `hard_exclusions: list[str]`, `price_sensitivity: float`, `delivery_sensitivity: float`, `acceptance_threshold: float`, `stated_vs_true_divergence: float`.
  - Invariants: Sensitivities and thresholds bounded `[0.0, 1.0]`, `extra="forbid"`.
- `SimulatedScenario`:
  - Fields: `scenario_id: str`, `intent: BuyerIntent`, `nl_utterance: str`, `available_catalog: list[Product]`, `merchant_policy: MerchantPolicy`.
  - Invariants: Full container for evaluation traces, `extra="forbid"`.

### 2. Catalog Generator (`merchantos_simulator.marketplace`)
- `generate_catalog(seed: int, category: str, sku_count: int = 5) -> list[Product]`
  - Produces realistic INR priced items with guaranteed positive margins (`base_price_minor > cost_minor`).

### 3. Buyer Intent Generator (`merchantos_simulator.buyers`)
- `generate_buyer_intent(seed: int, category: str, divergence: float) -> BuyerIntent`
  - Deterministically constructs ground-truth preferences, budget constraints, priorities, and sensitivities.

### 4. Lossy NLG Utterance Engine (`merchantos_simulator.nlg`)
- `generate_lossy_utterance(intent: BuyerIntent, seed: int) -> str`
  - Produces natural language buyer prompt strings reflecting stated preferences with controlled noise/distortion.

## 7. Data Generation Strategy

### Deterministic Random Seeds
- **Dev Set**: Seeds `1000` through `1099` (100 scenarios).
- **Held-out Set**: Seeds `5000` through `5049` (50 scenarios).
- Complete isolation between evaluation partitions with zero seed overlap.

### Divergence Modeling
- Each scenario is deterministically assigned a divergence level from `[0.1, 0.4, 0.8]` (Low, Med, High).
- **Low Divergence (`<= 0.2`)**: The buyer states priorities, constraints, and delivery expectations faithfully in natural language.
- **Medium Divergence (`0.3 <= div < 0.6`)**: Approximate budgets (e.g. `around 60k`), partial requirements, or optional clauses.
- **High Divergence (`>= 0.6`)**: The stated utterance contradicts or obscures the highest true sensitivity (e.g., buyer text claims budget is flexible or focuses purely on non-price features when true `price_sensitivity` is 0.95; or states relaxed delivery when true `delivery_sensitivity` is high).

### Security & Privacy Guardrails
1. **Zero Internal Schema Leakage**: Internal field names (`price_sensitivity`, `budget_max_minor`, `acceptance_threshold`, `priority`, etc.) are never emitted in utterances.
2. **No Raw Minor Currency Units**: Raw paise integers (e.g. `6000000`) are strictly formatted as natural language terms (e.g. `₹60,000` or `60k`).
3. **Automated P0 Leakage Test**: `tests/adversarial/test_leakage.py` runs against all 150 generated scenarios in CI.

## 8. Phase 3 Handoff (Rules Baseline Agent)

### Ingestion Guidelines:
1. **Loading Data**:
   ```python
   import json
   from merchantos_core.contracts import SimulatedScenario

   def load_scenario(jsonl_line: str) -> tuple[str, list[Product], MerchantPolicy]:
       scenario = SimulatedScenario.model_validate_json(jsonl_line)
       # AGENT INPUTS (DO NOT ACCESS scenario.intent):
       return scenario.nl_utterance, scenario.available_catalog, scenario.merchant_policy
   ```
2. **Blind Decision Making**: Downstream baseline and growth agents must make ranking, discounting, and recommendation decisions using *only* `nl_utterance`, `available_catalog`, and `merchant_policy`.
3. **Ground Truth Separation**: `scenario.intent` is reserved exclusively for the evaluation harness to compute customer satisfaction, conversion rate, and revenue metrics.

## 9. Commands

### Run Scenario Generation Script
```bash
python -m scripts.generate_scenarios
```

### Run All Tests (Unit, Integration, Adversarial)
```bash
pytest -q
```

### Run P0 Leakage Test Exclusively
```bash
pytest tests/adversarial/test_leakage.py -v
```

## 10. Ambiguities Resolved
1. **Pydantic Field Name Collision in Natural Language**: Natural language text initially used the common English word "priority" (e.g. "Top priority is..."). Because `priority` is also an exact field name on `BuyerIntent`, the P0 leakage test flagged this. Resolved by using natural synonyms in NLG ("Main focus is...", "Key need is...", "Primary requirement is...") to preserve strict zero-leakage guarantees.
2. **Singularization of Categories**: Replaced naive `.rstrip("s")` with a mapped dictionary lookup to ensure natural English phrasing (e.g. `accessories` -> `tech accessory`, `smartwatches` -> `smartwatch`).
3. **Paise vs. INR Formatting**: Ensured all raw integer numbers for money amounts are displayed with appropriate context (`₹60,000`, `60k`) rather than unformatted digit sequences.
