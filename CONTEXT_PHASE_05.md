# CONTEXT_PHASE_05

## 1. Phase Identity
- **Phase Number**: 05
- **Phase Name**: CommerceProof Deterministic Control Layer
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 05 implements the `CommerceProof` Deterministic Control Layer (`CommerceProof`), establishing the uncompromised P0 security and commercial integrity barrier for MerchantOS AI.

Per the architectural axiom: *"Everything left of CommerceProof can be wrong. Nothing right of CommerceProof can be wrong without being caught. The LLM has zero authority to move money. It can only propose."*

CommerceProof intercepts every `ProposedOffer`, validates it against deterministic merchant policy caps, margin floors, live inventory state (`InventoryState`), and cumulative promotion ledgers (`CumulativeLedger`). It either:
1. **EXECUTES** valid commercial offers,
2. **REPAIRS** offers with repairable policy violations by clamping prices/discounts to exact mathematical boundaries and annotating the audit trail, or
3. **BLOCKS** offers that are commercially fatal (unlisted SKU, out-of-stock items, or exhausted promotion budgets).

For every executable or repaired transaction, `CommerceProof` creates an immutable `CheckoutSnapshot` and computes a cryptographic SHA-256 state hash (`final_state_hash`) using `canonical_checkout_hash`. This hash cryptographically binds the agreed checkout state, ensuring that any downstream tampering (even by a single paise) will mismatch and abort payment execution.

All 87 tests (unit, integration, adversarial, and CommerceProof P0 gates) pass deterministically.

## 3. Repository State
- **Git Initialized**: Yes
- **Branch Name**: `main`
- **Staging Status**: Ready for human reviewer commit.

## 4. Exact File Tree Additions
```
merchantos-ai/
  CONTEXT_PHASE_05.md
  REVIEW_PHASE_05.md
  core/
    merchantos_core/
      contracts.py                 <-- Added InventoryRecord, InventoryState, CumulativeLedger, PolicyCheck, CommerceDecision
      commerceproof/
        __init__.py                <-- Exports CommerceProof
        engine.py                  <-- CommerceProof Control Layer (Deterministic evaluation, clamping, state binding)
  tests/
    unit/
      test_commerceproof.py        <-- P0 Gate Rejection, Repair, Ledger, Inventory & Cryptographic Binding Tests
```

## 5. Dependencies
- Strictly standard library (`re`, `json`, `pathlib`, `typing`, `abc`, `uuid`, `hashlib`), `pydantic>=2.0`, `pydantic-settings`, `fastapi`, `uvicorn`, `httpx`, and `pytest`.
- Zero LLM libraries or external orchestration frameworks. CommerceProof is 100% deterministic Python math and logic.

## 6. Public Interfaces Created

### 1. Data Contracts (`merchantos_core.contracts`)
- `InventoryRecord`:
  - **Import Path**: `from merchantos_core.contracts import InventoryRecord`
  - **Fields**:
    - `sku_id: str` (min_length=1)
    - `available_count: int` (ge=0)
  - **Invariants**: `extra="forbid"`.
- `InventoryState`:
  - **Import Path**: `from merchantos_core.contracts import InventoryState`
  - **Fields**:
    - `records: list[InventoryRecord]`
  - **Invariants**: `extra="forbid"`.
- `CumulativeLedger`:
  - **Import Path**: `from merchantos_core.contracts import CumulativeLedger`
  - **Fields**:
    - `merchant_id: str` (min_length=1)
    - `total_promotion_budget_minor: int` (ge=0)
    - `total_discount_minor_used: int` (ge=0)
  - **Invariants**: `extra="forbid"`.
- `PolicyCheck`:
  - **Import Path**: `from merchantos_core.contracts import PolicyCheck`
  - **Fields**:
    - `check_name: str` (min_length=1)
    - `status: Literal["pass", "fail", "repaired"]`
    - `message: str` (min_length=1)
  - **Invariants**: `extra="forbid"`.
- `CommerceDecision`:
  - **Import Path**: `from merchantos_core.contracts import CommerceDecision`
  - **Fields**:
    - `decision_id: str` (min_length=1)
    - `session_id: str` (min_length=1)
    - `action: Literal["EXECUTE", "REPAIR", "ESCALATE", "BLOCK"]`
    - `violations: list[str]` (default=`[]`)
    - `repairs: list[str]` (default=`[]`)
    - `checks: list[PolicyCheck]` (default=`[]`)
    - `original_offer_id: str` (min_length=1)
    - `final_offer: ProposedOffer | None` (default=`None`)
    - `final_state_hash: str | None` (default=`None`)
  - **Invariants**: `extra="forbid"`.

### 2. CommerceProof Control Layer (`merchantos_core.commerceproof`)
- `CommerceProof`:
  - **Import Path**: `from merchantos_core.commerceproof import CommerceProof`
  - **Method**:
    ```python
    def evaluate(
        self,
        offer: ProposedOffer,
        policy: MerchantPolicy,
        inventory: InventoryState,
        ledger: CumulativeLedger,
        catalog: list[Product],
    ) -> CommerceDecision
    ```

## 7. The Trust Boundary Topology

CommerceProof establishes an absolute deterministic barrier between upstream probabilistic decision agents (LLMs/heuristics) and downstream financial infrastructure (Razorpay/Order execution):

```
+-------------------------------------------------------------+
|                PROBABILISTIC / UNTRUSTED ZONE               |
|                                                             |
|   [Buyer NL Utterance] ---> [Merchant Growth Agent (LLM)]   |
|                                     |                       |
|                                     v                       |
|                              [ProposedOffer]                |
+-------------------------------------------------------------+
                              ||
                              || (Crosses Trust Boundary)
                              \/
+-------------------------------------------------------------+
|             COMMERCEPROOF DETERMINISTIC CONTROL             |
|                                                             |
|   1. Catalog & SKU Existence Validation                     |
|   2. Cost & Margin Floor Clamping (min_allowed_price)       |
|   3. Policy Discount Cap Clamping (max_allowed_discount)    |
|   4. Real-time Inventory Verification (available_count > 0) |
|   5. Cumulative Promotion Budget Verification               |
|   6. Immutable CheckoutSnapshot Construction                |
|   7. Cryptographic SHA-256 State Binding                    |
+-------------------------------------------------------------+
                              ||
                              || (Deterministic CommerceDecision)
                              \/
+-------------------------------------------------------------+
|                   SECURE EXECUTION LAYER                    |
|                                                             |
|   EXECUTE / REPAIR ---> Razorpay Order (with state_hash)    |
|   BLOCK            ---> Transaction Aborted (Zero Money Out)|
+-------------------------------------------------------------+
```

### Deterministic Invariants Enforced:
1. **Catalog Integrity**: If `selected_sku_id` does not exist in `catalog`, action is immediately `BLOCK`.
2. **Margin Floor**: `min_allowed_price = int(cost_minor * (1.0 + policy.margin_floor_pct))`. If `proposed_price < min_allowed_price`, it is clamped to `min_allowed_price` and discount is recomputed.
3. **Discount Cap**: `max_allowed_discount = int(base_price_minor * policy.discount_cap_pct)`. If `discount > max_allowed_discount`, discount is clamped to `max_allowed_discount` and price is recomputed.
4. **Inventory Availability**: If `available_count <= 0` or SKU is unlisted in inventory, action is `BLOCK`. Out-of-stock items are never repaired.
5. **Cumulative Budget**: `remaining_budget = total_promotion_budget_minor - total_discount_minor_used`. If `remaining_budget <= 0`, action is `BLOCK`. If `0 < remaining_budget < discount`, discount is clamped to `remaining_budget`.
6. **Cryptographic Binding**: `final_state_hash` is computed directly on the canonical `CheckoutSnapshot`.

## 8. State Machine Logic

| Condition | Outcome | `final_offer` | `final_state_hash` |
| :--- | :--- | :--- | :--- |
| SKU missing from catalog | `BLOCK` | `None` | `None` |
| SKU out of stock (`available_count <= 0`) | `BLOCK` | `None` | `None` |
| Cumulative promotion budget exhausted (`remaining <= 0`) | `BLOCK` | `None` | `None` |
| Margin floor breached (`price < min_price`) | `REPAIR` | Repaired `ProposedOffer` | Computed SHA-256 |
| Discount cap breached (`discount > max_discount`) | `REPAIR` | Repaired `ProposedOffer` | Computed SHA-256 |
| Partial budget remaining (`discount > remaining > 0`) | `REPAIR` | Repaired `ProposedOffer` | Computed SHA-256 |
| Perfectly compliant offer | `EXECUTE` | Original `ProposedOffer` | Computed SHA-256 |

## 9. Phase 6 Handoff (Evaluation Harness & Benchmark Metrics)
In Phase 6, the Evaluation Harness will execute automated scenario batches across baseline and growth agents:
1. **Gate Rejection Rate**: Computed as `count(decision.action == "BLOCK") / total_scenarios`.
2. **Repair Rate**: Computed as `count(decision.action == "REPAIR") / total_scenarios`.
3. **Execution Rate**: Computed as `count(decision.action == "EXECUTE") / total_scenarios`.
4. **Policy Violation Breakdown**: Aggregated from `CommerceDecision.violations` and `CommerceDecision.checks` to audit where agent proposals diverge from merchant safety rules.

## 10. Test Commands
```bash
# Run entire test suite (all 87 tests)
pytest -v

# Run Phase 05 tests specifically
pytest tests/unit/test_commerceproof.py -v
```
