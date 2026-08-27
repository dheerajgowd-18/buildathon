# CONTEXT_PHASE_04

## 1. Phase Identity
- **Phase Number**: 04
- **Phase Name**: Merchant Growth Agent (LLM-based), Swappable Provider Abstraction, Buyer Simulator & Multi-Round Negotiation State Machine
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 04 implements the LLM-driven Merchant Growth Agent (`MerchantGrowthAgent`), a swappable LLM provider abstraction (`AbstractLLMProvider` and deterministic `MockLLMProvider`), a multi-attribute utility Buyer Simulator (`BuyerSimulator`), and a multi-round state machine (`NegotiationEngine`).

The Growth Agent enforces the critical **"LLM Proposes, Code Disposes"** safety invariant: while the LLM reasons about buyer natural language and negotiation history to propose a commercial deal, deterministic Python code validates the selected SKU against the catalog and mathematically clamps discounts to merchant policy caps and margin floors before any `ProposedOffer` is returned. The Buyer Simulator models realistic buyer behavior via price-, delivery-, and category-utility scoring. The Negotiation Engine manages turns up to `MAX_ROUNDS = 3` while strictly isolating ground-truth intent from decision agents. All 78 unit, integration, and adversarial tests pass deterministically.

## 3. Repository State
- **Git Initialized**: Yes
- **Branch Name**: `main`
- **Staging Status**: Ready for human reviewer commit.

## 4. Exact File Tree Additions
```
merchantos-ai/
  CONTEXT_PHASE_04.md
  REVIEW_PHASE_04.md
  core/
    merchantos_core/
      contracts.py                 <-- Added NegotiationEvent, BuyerResponse, NegotiationSessionState, LLMOutput; updated AgentInput
      llm/
        __init__.py                <-- Exports AbstractLLMProvider, MockLLMProvider, build_merchant_prompt
        provider.py                <-- AbstractLLMProvider (ABC), MockLLMProvider (deterministic simulation)
        prompts.py                 <-- build_merchant_prompt (JSON-schema enforced prompting)
      agents/
        __init__.py                <-- Exports MerchantGrowthAgent, RulesBaselineAgent
        growth_agent.py            <-- MerchantGrowthAgent ("LLM proposes, code disposes")
      negotiation/
        __init__.py                <-- Exports BuyerSimulator, NegotiationEngine
        buyer_simulator.py         <-- BuyerSimulator (Multi-attribute utility evaluator)
        engine.py                  <-- NegotiationEngine (Multi-round turn state machine)
  tests/
    unit/
      test_llm_provider.py         <-- Determinism & policy bounds for MockLLMProvider
      test_growth_agent.py         <-- Interface compliance & policy clamping tests
      test_buyer_simulator.py      <-- Multi-attribute utility acceptance/rejection/counter tests
      test_negotiation_engine.py   <-- Multi-round state progression & ground-truth isolation tests
```

## 5. Dependencies
- Strictly standard library (`re`, `json`, `pathlib`, `typing`, `abc`, `inspect`), `pydantic>=2.0`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, and `pytest`.
- Zero external orchestration frameworks (no LangChain, no LangGraph, no LlamaIndex).
- Swappable provider architecture allows hermetic, zero-cost deterministic mock evaluation during CI and live API key integration in production.

## 6. Public Interfaces Created

### 1. Data Contracts (`merchantos_core.contracts`)
- `AgentInput` (Updated):
  - **Import Path**: `from merchantos_core.contracts import AgentInput`
  - **Fields**:
    - `session_id: str` (min_length=1)
    - `nl_utterance: str` (min_length=1)
    - `available_catalog: list[Product]` (min_length=1)
    - `merchant_policy: MerchantPolicy`
    - `negotiation_history: list[NegotiationEvent]` (default=`[]`)
  - **Invariants**: `extra="forbid"`. Strictly contains zero ground-truth fields (`BuyerIntent`, `budget_max_minor`, `price_sensitivity`, etc.).
- `NegotiationEvent`:
  - **Import Path**: `from merchantos_core.contracts import NegotiationEvent`
  - **Fields**:
    - `session_id: str` (min_length=1)
    - `round: int` (ge=1)
    - `actor: Literal["merchant_agent", "buyer_agent"]`
    - `message_type: Literal["initial_offer", "counter_offer", "accept", "reject"]`
    - `offer_id: str | None`
    - `proposed_offer: ProposedOffer | None`
    - `reason_text: str`
  - **Invariants**: `extra="forbid"`.
- `BuyerResponse`:
  - **Import Path**: `from merchantos_core.contracts import BuyerResponse`
  - **Fields**:
    - `action: Literal["accept", "reject", "counter"]`
    - `reason: str`
    - `counter_utterance: str | None`
  - **Invariants**: `extra="forbid"`.
- `NegotiationSessionState`:
  - **Import Path**: `from merchantos_core.contracts import NegotiationSessionState`
  - **Fields**:
    - `session_id: str` (min_length=1)
    - `status: Literal["in_progress", "accepted", "rejected", "max_rounds_reached"]`
    - `current_round: int` (ge=0)
    - `history: list[NegotiationEvent]`
    - `final_offer: ProposedOffer | None`
  - **Invariants**: `extra="forbid"`.
- `LLMOutput`:
  - **Import Path**: `from merchantos_core.contracts import LLMOutput`
  - **Fields**:
    - `selected_sku_id: str` (min_length=1)
    - `proposed_price_minor: int` (ge=0)
    - `discount_minor: int` (ge=0)
    - `shipping_tier: Literal["standard", "express"]`
    - `rationale: str` (min_length=1)
  - **Invariants**: `extra="forbid"`.

### 2. LLM Provider Abstraction (`merchantos_core.llm`)
- `AbstractLLMProvider` (ABC):
  - `generate_offer_proposal(self, system_prompt: str, user_prompt: str) -> LLMOutput`
- `MockLLMProvider`:
  - Deterministic simulation of LLM inference parsing prompt signals and catalog items. Supports test injection hooks (`override_output`).
- `build_merchant_prompt(agent_input: AgentInput) -> tuple[str, str]`:
  - Generates system and user prompts enforcing raw JSON output conforming to `LLMOutput` schema without hallucination.

### 3. Merchant Growth Agent (`merchantos_core.agents.growth_agent`)
- `MerchantGrowthAgent`:
  - **Method**: `score_and_propose(self, agent_input: AgentInput) -> ProposedOffer`
  - Identical signature and return type as `RulesBaselineAgent`.

### 4. Buyer Simulator & Negotiation Engine (`merchantos_core.negotiation`)
- `BuyerSimulator`:
  - **Method**: `evaluate_offer(self, offer: ProposedOffer, intent: BuyerIntent, catalog: list[Product]) -> BuyerResponse`
- `NegotiationEngine`:
  - **Method**: `run_session(self, scenario: SimulatedScenario, merchant_agent: RulesBaselineAgent | MerchantGrowthAgent, buyer_simulator: BuyerSimulator | None = None) -> NegotiationSessionState`

## 7. The "LLM Proposes, Code Disposes" Topology

To eliminate commercial risk from LLM hallucination or prompt injection, the system implements a strict two-layer boundary:

```
[AgentInput] ---> [LLM Provider (Reasoning / Suggestion)]
                          |
                          v (Raw LLMOutput)
                  [Deterministic Guardrail Code]
                          |
                          +--> Check SKU exists in Available Catalog (Fallback if hallucinated)
                          +--> Calculate Max Allowed Discount: min(discount_cap, margin_floor_headroom)
                          +--> Clamp Discount: clamped_discount = min(raw_discount, max_allowed_discount)
                          +--> Enforce Price: proposed_price = base_price - clamped_discount >= margin_floor
                          |
                          v
                   [ProposedOffer (Mathematically Guaranteed)]
```

### Clamping Mathematical Guarantees:
1. `max_discount_cap_minor = int(base_price_minor * policy.discount_cap_pct)`
2. `min_price_margin_minor = int(cost_minor * (1.0 + policy.margin_floor_pct))`
3. `min_price_cap_minor = base_price_minor - max_discount_cap_minor`
4. `min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)`
5. `max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)`
6. `clamped_discount = min(max(0, llm_output.discount_minor), max_allowed_discount_minor)`
7. `clamped_price = base_price_minor - clamped_discount`

## 8. Buyer Simulator Utility Model
The buyer simulator evaluates proposed offers using a multi-attribute utility function:
- **Price Score**: `1.0` if `price <= budget`; decays linearly to `0.0` at `2x budget` (`max(0.0, 1.0 - (price - budget) / budget)`).
- **Delivery Score**: `1.0` if `shipping_tier == "express"` and `delivery_sensitivity > 0.5`, else `0.8`.
- **Product Fit**: `1.0` if catalog product category matches buyer intent category, else `0.5`.
- **Utility Calculation**:
  - `w_price = intent.price_sensitivity`
  - `w_delivery = intent.delivery_sensitivity`
  - `w_product = max(0.0, 1.0 - w_price - w_delivery)`
  - `utility = (w_price * price_score) + (w_delivery * delivery_score) + (w_product * product_fit)`
- **Decision Rules**:
  - `utility >= intent.acceptance_threshold` -> `accept`
  - `utility < intent.acceptance_threshold * 0.5` -> `reject`
  - Otherwise -> `counter` (with dynamic counter-utterance)

## 9. Negotiation State Machine
The `NegotiationEngine` loops up to `MAX_ROUNDS = 3`:
1. In round $r$, packages current buyer utterance, catalog, merchant policy, and negotiation history into `AgentInput`.
2. Calls `merchant_agent.score_and_propose(agent_input)`.
3. Appends merchant `NegotiationEvent` to session history.
4. Evaluates offer against ground truth `BuyerIntent` using `BuyerSimulator`.
5. Appends buyer `NegotiationEvent` (`accept`, `reject`, or `counter_offer`).
6. Terminates immediately on `accept` or `reject`.
7. On `counter`, updates buyer NL utterance with counter feedback and proceeds to round $r+1$.
8. If 3 rounds elapse without acceptance, sets status to `max_rounds_reached`.

## 10. Phase 5 Handoff (CommerceProof Deterministic Control Layer)
In Phase 5, the `CommerceProof` control layer will:
1. Intercept `ProposedOffer` instances output by `RulesBaselineAgent` or `MerchantGrowthAgent`.
2. Convert accepted commercial terms into immutable `CheckoutSnapshot` models.
3. Compute deterministic cryptographic hashes (`final_state_hash`) using `canonical_checkout_hash`.
4. Transmit signed orders to Razorpay and verify webhook callbacks via HMAC-SHA256 before capturing payment.

## 11. Test Commands
```bash
# Run entire test suite (all 78 tests)
pytest -v

# Run Phase 04 tests specifically
pytest tests/unit/test_llm_provider.py tests/unit/test_growth_agent.py tests/unit/test_buyer_simulator.py tests/unit/test_negotiation_engine.py -v
```
