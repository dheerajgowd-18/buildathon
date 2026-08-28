# MerchantOS AI — System Architecture

## 1. High-Level Component Topology

```
+----------------------------------------------------------------------------------------------------+
|                                      BUYER INTERACTION SURFACE                                     |
|                                                                                                    |
|   [Buyer Agent / Buyer User Utterance] <======================================================+    |
+-----------------------------------------------------------------------------------------------|----+
                                                                                                |
                                                                                                v
+----------------------------------------------------------------------------------------------------+
|                                    PROBABILISTIC / AGENTIC LAYER                                   |
|                                                                                                    |
|   +----------------------------------------------------+                                           |
|   |             Merchant Growth Agent (LLM)            | <--- Multi-round history, catalog, policy |
|   |         - Intent Interpretation                    |                                           |
|   |         - Adaptive Concession Strategy             |                                           |
|   +----------------------------------------------------+                                           |
|                             |                                                                      |
|                             v                                                                      |
|                      [ProposedOffer]                                                               |
+----------------------------------------------------------------------------------------------------+
                              ||
                              ||  <--- CROSSES STRICT TRUST BOUNDARY
                              \/
+----------------------------------------------------------------------------------------------------+
|                               COMMERCEPROOF DETERMINISTIC CONTROL GATE                             |
|                                                                                                    |
|   [CommerceProof Control Engine]                                                                   |
|   ├── 1. Catalog & SKU Existence Validation                                                         |
|   ├── 2. Cost & Margin Floor Preservation (min_allowed_price = cost * (1 + margin_floor_pct))      |
|   ├── 3. Merchant Policy Discount Cap Clamping (max_discount = base_price * discount_cap_pct)       |
|   ├── 4. Real-time Inventory Verification (available_count > 0)                                    |
|   ├── 5. Cumulative Promotion Budget Verification                                                  |
|   ├── 6. Immutable CheckoutSnapshot Construction                                                   |
|   └── 7. Canonical SHA-256 State Hash Binding (canonical_checkout_hash)                            |
|                             |                                                                      |
|                             +--------------------+--------------------+                            |
|                             |                    |                    |                            |
|                             v                    v                    v                            |
|                        [EXECUTE]              [REPAIR]             [BLOCK]                         |
|                   (Passes Invariants)     (Clamped to Floor)  (Fatal Violation)                    |
+----------------------------------------------------------------------------------------------------+
                              ||                                        ||
                              || (CommerceDecision)                     || (Zero Outbound Order)
                              \/                                        \/
+----------------------------------------------------------------------------------------------------+
|                                    IMMUTABLE TRADE LEDGER & AUDIT                                  |
|                                                                                                    |
|   [TradeLedger (Thread-Safe In-Memory Audit Trail)]                                                |
|   ├── intent_received  --> offer_proposed --> gate_decision --> order_created                       |
|   └── payment_captured / payment_failed / error                                                    |
+----------------------------------------------------------------------------------------------------+
                              ||
                              \/
+----------------------------------------------------------------------------------------------------+
|                                FINANCIAL EXECUTION & ADAPTER LAYER                                 |
|                                                                                                    |
|   +----------------------------------+          +----------------------------------------------+   |
|   |    Razorpay Adapter (Outbound)   |          |          Inbound Webhook Router              |   |
|   |  - Idempotent Order Creation     |          |  - Raw HMAC SHA-256 Signature Verification   |   |
|   |  - Exponential Backoff & Retry   |          |  - Ledger Cross-Reference (Cart Defense)     |   |
|   +----------------------------------+          +----------------------------------------------+   |
|                   |                                                     ^                          |
|                   v                                                     |                          |
|   [Razorpay Payment Gateway API] ---------------------------------------+                          |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. The Trust Boundary Topology

> **Architectural Axiom:**
> *"Everything left of `CommerceProof` can be wrong. Nothing right of `CommerceProof` can be wrong without being caught. The LLM has zero authority to move money. It can only propose."*

```
[ UNTRUSTED ZONE: Probabilistic Reasoning ]           [ TRUSTED ZONE: Deterministic Invariants ]
===========================================           ===========================================
Buyer Utterances (Prompt Injections)       |
Untrusted Natural Language Counters        |
LLM Hallucinations / Over-discounts        |  ======>  [ CommerceProof Deterministic Gate ]
Non-deterministic Multi-round Heuristics   |                      |
                                                                  +--> Clamps to Margin Floor
                                                                  +--> Enforces Discount Caps
                                                                  +--> Checks Inventory Counts
                                                                  +--> Creates Immutable Hash
                                                                  |
                                                                  v
                                                       [ Razorpay Order Execution ]
                                                       [ HMAC Webhook Settlement ]
                                                       [ Immutable Trade Ledger ]
```

### Invariant Table:
| Property | Left of Gate (Probabilistic) | Right of Gate (Deterministic) |
| :--- | :--- | :--- |
| **Authority** | Propose commercial terms | Authorize and execute financial movement |
| **Price Floor** | Can be violated by LLM prompt injection | Strictly clamped to `cost * (1 + margin_floor_pct)` |
| **Discount Cap** | Can exceed allowable promotion budgets | Strictly clamped to `min(cap, remaining_budget)` |
| **Inventory** | Can assume hypothetical stock | Strictly verified against `InventoryState` |
| **State Tampering** | Vulnerable to cart mutation | Defended by `TradeLedger` cross-reference & SHA-256 |

---

## 3. Negotiation & Settlement Sequence Diagram

```
Buyer Agent                  MerchantGrowthAgent        CommerceProof          TradeLedger         Razorpay / Webhook
    |                                 |                       |                     |                      |
    |---- 1. Stated NL Utterance ---->|                       |                     |                      |
    |     ("Need laptop under 50k")   |                       |                     |                      |
    |                                 |-- 2. Propose Offer -->|                     |                      |
    |                                 |  (SKU, Price, Disc.)  |                     |                      |
    |                                 |                       |-- 3. Invariant Check|                      |
    |                                 |                       |  (Floor, Cap, OOS)  |                      |
    |                                 |                       |                     |                      |
    |                                 |                       |-- 4. Record Event ->|                      |
    |                                 |                       |   (gate_decision)   |                      |
    |                                 |                       |                     |                      |
    |                                 |<-- 5. Gate Decision --|                     |                      |
    |<--- 6. Calibrated Counter ------|  (EXECUTE / REPAIR)   |                     |                      |
    |     ("₹45,000 + Express Ship")  |                       |                     |                      |
    |                                 |                       |                     |                      |
    |==== 7. Buyer Accepts Offer =====|                       |                     |                      |
    |                                                         |-- 8. Create Order ------------------------>|
    |                                                         |   (Idempotent Retry)|                      |
    |                                                         |                     |<-- 9. Order Created -|
    |                                                         |-- 10. Record Event->|   (order_id: rzp_123)|
    |                                                         |   (order_created)   |                      |
    |                                                                               |                      |
    |---- 11. Customer Completes Payment at Gateway ------------------------------------------------------>|
    |                                                                               |                      |
    |                                                                               |    12. Webhook Event |
    |                                                                               |    (payment.captured)|
    |                                                                               |<---------------------|
    |                                                                               |                      |
    |                                                                               |-- 13. Verify HMAC    |
    |                                                                               |-- 14. Check Ledger   |
    |                                                                               |   (Amount Match)     |
    |                                                                               |-- 15. Record Event ->|
    |                                                                               |   (payment_captured) |
    |                                                                               |<-- 16. HTTP 200 OK --|
```
