"""Generate stratified evidence samples and zero-leakage proof for the Evidence Lab."""

from __future__ import annotations

import json
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORE_PATH = _REPO_ROOT / "core"
_SIM_PATH = _REPO_ROOT / "simulator"

for p in (_CORE_PATH, _SIM_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from merchantos_core.contracts import SimulatedScenario
from merchantos_core.evaluation.harness import EvaluationHarness


def load_scenarios(file_path: Path) -> list[SimulatedScenario]:
    """Load simulated scenarios from a JSONL file."""
    scenarios: list[SimulatedScenario] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str:
                scenarios.append(SimulatedScenario.model_validate_json(line_str))
    return scenarios


def generate_evidence_samples(
    scenarios_file: Path | None = None,
    output_samples_file: Path | None = None,
    output_leakage_file: Path | None = None,
) -> tuple[list[dict], dict]:
    """Select 12 stratified scenarios, evaluate rules vs growth, and write evidence JSONs."""
    data_dir = _REPO_ROOT / "data"
    src_scenarios = scenarios_file or (data_dir / "dev_scenarios.jsonl")
    out_samples = output_samples_file or (data_dir / "evidence_samples.json")
    out_leakage = output_leakage_file or (data_dir / "leakage_proof.json")

    all_scenarios = load_scenarios(src_scenarios)

    # 1. Stratify scenarios by divergence
    low_bucket = []
    med_bucket = []
    high_bucket = []

    for sc in all_scenarios:
        div = sc.intent.stated_vs_true_divergence
        if div < 0.3:
            low_bucket.append(sc)
        elif div < 0.6:
            med_bucket.append(sc)
        else:
            high_bucket.append(sc)

    # Deterministically sort by scenario_id and take 4 from each
    low_bucket.sort(key=lambda s: s.scenario_id)
    med_bucket.sort(key=lambda s: s.scenario_id)
    high_bucket.sort(key=lambda s: s.scenario_id)

    selected_scenarios = low_bucket[:4] + med_bucket[:4] + high_bucket[:4]
    selected_scenarios.sort(key=lambda s: (s.intent.stated_vs_true_divergence, s.scenario_id))

    # 2. Run Evaluation Harness on selected scenarios
    harness = EvaluationHarness()
    samples = []

    for sc in selected_scenarios:
        rules_res = harness._evaluate_arm("rules_baseline", sc, harness.rules_agent)
        growth_res = harness._evaluate_arm("growth_agent", sc, harness.growth_agent)

        rules_conv = rules_res.status == "converted"
        growth_conv = growth_res.status == "converted"

        # Growth wins if it converted and rules didn't, or higher price at conversion
        growth_won = (growth_conv and not rules_conv) or (
            growth_conv and rules_conv and (growth_res.final_price_minor or 0) >= (rules_res.final_price_minor or 0)
        )

        sample_item = {
            "scenario_id": sc.scenario_id,
            "utterance": sc.nl_utterance,
            "category": sc.intent.category,
            "divergence": round(sc.intent.stated_vs_true_divergence, 2),
            "true_budget_minor": sc.intent.budget_max_minor,
            "price_sensitivity": round(sc.intent.price_sensitivity, 2),
            "delivery_sensitivity": round(sc.intent.delivery_sensitivity, 2),
            "rules": {
                "status": rules_res.status,
                "final_price_minor": rules_res.final_price_minor,
                "rounds": rules_res.negotiation_rounds,
                "gate_repairs": rules_res.gate_repairs,
            },
            "growth": {
                "status": growth_res.status,
                "final_price_minor": growth_res.final_price_minor,
                "rounds": growth_res.negotiation_rounds,
                "gate_repairs": growth_res.gate_repairs,
            },
            "growth_won": growth_won,
        }
        samples.append(sample_item)

    # Save samples JSON
    out_samples.parent.mkdir(parents=True, exist_ok=True)
    with open(out_samples, "w", encoding="utf-8") as f:
        json.dump(samples, f, indent=2)

    # 3. Build Leakage Proof across all benchmark scenarios
    field_names = ["priority", "category", "budget_max_minor", "stated_vs_true_divergence", "price_sensitivity", "delivery_sensitivity"]
    leak_count = 0
    for sc in all_scenarios:
        utt_lower = sc.nl_utterance.lower()
        for fn in field_names:
            if fn.lower() in utt_lower:
                leak_count += 1
        # Check raw minor paise integers
        if str(sc.intent.budget_max_minor) in sc.nl_utterance:
            leak_count += 1

    sample_utts = [s["utterance"] for s in samples[:3]]
    leakage_proof = {
        "scenarios_scanned": len(all_scenarios),
        "field_names_checked": field_names,
        "raw_values_checked": ["raw integer minor units (paise)"],
        "leaks_found": leak_count,
        "sample_utterances": sample_utts,
    }

    with open(out_leakage, "w", encoding="utf-8") as f:
        json.dump(leakage_proof, f, indent=2)

    return samples, leakage_proof


def print_ascii_table(samples: list[dict]) -> None:
    """Print clean 12-row ASCII summary table."""
    print("=" * 110)
    print(f"{'Scenario ID':<16} | {'Div':<5} | {'Category':<11} | {'True Budget':<12} | {'Rules Result':<14} | {'Growth Result':<14} | {'Winner':<8}")
    print("-" * 110)
    for s in samples:
        budget_str = f"Rs {s['true_budget_minor'] / 100:,.0f}"
        rules_p = (s['rules']['final_price_minor'] or 0) / 100
        growth_p = (s['growth']['final_price_minor'] or 0) / 100
        rules_str = f"{s['rules']['status']} (Rs {rules_p:,.0f})" if s['rules']['status'] == "converted" else s['rules']['status']
        growth_str = f"{s['growth']['status']} (Rs {growth_p:,.0f})" if s['growth']['status'] == "converted" else s['growth']['status']
        winner = "GROWTH" if s["growth_won"] else "RULES"
        print(f"{s['scenario_id']:<16} | {s['divergence']:<5.2f} | {s['category']:<11} | {budget_str:<12} | {rules_str:<14} | {growth_str:<14} | {winner:<8}")
    print("=" * 110)


if __name__ == "__main__":
    samples, leakage = generate_evidence_samples()
    print_ascii_table(samples)
    print(f"\n[Generated] data/evidence_samples.json (12 stratified scenarios)")
    print(f"[Generated] data/leakage_proof.json ({leakage['scenarios_scanned']} scenarios scanned, {leakage['leaks_found']} leaks)")
