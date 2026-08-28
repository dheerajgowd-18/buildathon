# MerchantOS AI — Evaluation Spine & Benchmark Results

## 1. The Two Evaluation Arms

To measure the true value of adaptive agentic intelligence versus static heuristics, the benchmark compares two arms under identical conditions:

1. **`RulesBaselineAgent` (Static Policy Arm)**:
   - Evaluates buyer intent on Round 1 using rigid keyword matching and static discount heuristics.
   - Proposes a single offer and repeats that identical offer on subsequent rounds, completely ignoring buyer counter-proposals, budget feedback, and urgency cues.
2. **`MerchantGrowthAgent` (Adaptive LLM Arm)**:
   - Reasons over multi-turn negotiation history, buyer stated vs. implicit constraints, category preferences, and delivery urgency.
   - Anchors strategically on Round 1, makes calibrated price concessions on Round 2, and provides high-concession or shipping upgrades on Round 3 under strict `CommerceProof` boundary protection.

---

## 2. Paired Benchmark Design

### Why Paired Design Over Unpaired Volume?
Running 10,000 unpaired random sessions introduces immense variance from catalog distribution, buyer budget outliers, and stochastic prompt generation. 

MerchantOS AI uses a **strictly paired benchmark design**:
- Every scenario $S_i = (\text{Seed}_i, \text{Utterance}_i, \text{Catalog}_i, \text{Policy}_i, \text{GroundTruthIntent}_i)$ is executed against **both** `RulesBaselineAgent` and `MerchantGrowthAgent`.
- Both arms face the exact same `BuyerSimulator` utility evaluation curves, inventory states, and promotion budgets.
- All deltas ($\Delta \text{Conversion} = \text{Growth} - \text{Rules}$) isolate pure negotiation strategy performance with zero confounding noise.

---

## 3. The Divergence Thesis: Empirical Evidence

> **Thesis:** *"Static rules perform well when buyer communication is simple and low-divergence. As divergence increases (noisy budget statements, implicit urgency, category mismatch), adaptive agentic intelligence significantly outperforms static rules."*

### Benchmark Results on Dev Split (100 Scenarios)

| Divergence Bucket | Scenarios | Rules Conversion | Growth Conversion | Conversion Delta ($\Delta$) | Rules Avg Rounds | Growth Avg Rounds |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Low (`< 0.3`)** | 36 | 83.3% | 80.6% | **-2.8%** | 1.22 | 1.44 |
| **Medium (`0.3 - 0.6`)** | 26 | 57.7% | 96.2% | **+38.5%** | 1.77 | 1.42 |
| **High (`>= 0.6`)** | 38 | 68.4% | 94.7% | **+26.3%** | 1.53 | 1.26 |
| **Overall Dev** | **100** | **71.0%** | **90.0%** | **+19.0%** | **1.48** | **1.37** |

### Validation Results on Heldout Split (50 Scenarios)

| Divergence Bucket | Scenarios | Rules Conversion | Growth Conversion | Conversion Delta ($\Delta$) | Rules Avg Rounds | Growth Avg Rounds |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Low (`< 0.3`)** | 14 | 85.7% | 92.9% | **+7.1%** | 1.14 | 1.36 |
| **Medium (`0.3 - 0.6`)** | 17 | 52.9% | 94.1% | **+41.2%** | 1.82 | 1.47 |
| **High (`>= 0.6`)** | 19 | 68.4% | 94.7% | **+26.3%** | 1.63 | 1.32 |
| **Overall Heldout** | **50** | **68.0%** | **94.0%** | **+26.0%** | **1.56** | **1.38** |

### Key Takeaways:
- At **Low Divergence**, static rules match AI performance at zero LLM cost.
- At **Medium & High Divergence**, the Growth Agent unlocks **+26.3% to +41.2% conversion gains** by dynamically interpreting counter-utterances, upgrading shipping tiers, and making bounded concessions.

---

## 4. Load-Bearing Gate Integrity

The deterministic `CommerceProof` control gate is not a passive logging filter—it actively protects merchant solvency:

- **Gate Rejection Rate**: **5.0% on Dev, 6.0% on Heldout**  
  Fatal violations (unlisted SKUs, zero inventory stock, or exhausted merchant promotion pools) were blocked immediately with zero money movement.
- **Gate Repair Rate**: **3.0% - 5.0% on Dev, 4.0% - 6.0% on Heldout**  
  Proposals that breached margin floors (`cost * (1 + margin_floor_pct)`) or exceeded merchant discount caps (`base_price * discount_cap_pct`) were mathematically repaired to policy bounds.
- **Margin Floor Breaches**: **0% (Absolute Zero Defect Guarantee)**.

---

## 5. Dev Dataset Freeze Commit

The development scenario dataset (`data/dev_scenarios.jsonl`) and evaluation harness contracts were frozen prior to final benchmark runs:

```
FREEZE_COMMIT_HASH: a7f89d4e21b06c8842e61df3e0d869b2d8e4c19a
FREEZE_DATE: 2026-08-27
DATASET_SPLITS: dev (100 scenarios, seed 42-141), heldout (50 scenarios, seed 142-191)
```
