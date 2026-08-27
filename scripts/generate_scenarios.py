"""Pre-computation entrypoint for generating synthetic evaluation scenarios."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

from merchantos_core.contracts import MerchantPolicy, SimulatedScenario
from merchantos_simulator.buyers import generate_buyer_intent
from merchantos_simulator.marketplace import generate_catalog
from merchantos_simulator.nlg import generate_lossy_utterance

CATEGORIES = [
    "laptops",
    "smartphones",
    "audio",
    "tablets",
    "smartwatches",
    "accessories",
]

DIVERGENCE_LEVELS = [0.1, 0.4, 0.8]


def generate_scenario_set(
    start_seed: int,
    count: int,
    id_prefix: str,
) -> list[SimulatedScenario]:
    """Generate a deterministic set of simulated scenarios.

    Args:
        start_seed: Starting seed for the deterministic sequence.
        count: Number of scenarios to produce.
        id_prefix: Prefix for scenario identifiers (e.g. 'dev', 'heldout').

    Returns:
        List of SimulatedScenario instances.
    """
    scenarios: list[SimulatedScenario] = []

    for i in range(count):
        seed = start_seed + i
        rng = random.Random(seed)

        category = rng.choice(CATEGORIES)
        divergence = rng.choice(DIVERGENCE_LEVELS)

        catalog = generate_catalog(seed=seed, category=category, sku_count=5)
        intent = generate_buyer_intent(seed=seed, category=category, divergence=divergence)
        utterance = generate_lossy_utterance(intent=intent, seed=seed)

        merchant_policy = MerchantPolicy(
            merchant_id=f"merch_{(seed % 10) + 1:03d}",
            margin_floor_pct=0.15,
            discount_cap_pct=0.20,
            promotion_budget_minor=50_000_00,
        )

        scenario = SimulatedScenario(
            scenario_id=f"{id_prefix}_{i:03d}",
            intent=intent,
            nl_utterance=utterance,
            available_catalog=catalog,
            merchant_policy=merchant_policy,
        )
        scenarios.append(scenario)

    return scenarios


def save_scenarios_jsonl(scenarios: list[SimulatedScenario], output_path: Path) -> None:
    """Serialize a list of SimulatedScenario objects to a JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for scenario in scenarios:
            f.write(scenario.model_dump_json() + "\n")


def main() -> None:
    """Pre-computation entrypoint generating dev and held-out evaluation datasets."""
    parser = argparse.ArgumentParser(description="Generate synthetic evaluation scenarios.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Target directory for output JSONL scenario files.",
    )
    args = parser.parse_args()

    data_dir: Path = args.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating scenarios into: {data_dir}")

    # Generate 100 Dev scenarios with seeds 1000..1099
    dev_scenarios = generate_scenario_set(
        start_seed=1000,
        count=100,
        id_prefix="dev",
    )
    dev_output = data_dir / "dev_scenarios.jsonl"
    save_scenarios_jsonl(dev_scenarios, dev_output)
    print(f"Saved {len(dev_scenarios)} dev scenarios -> {dev_output}")

    # Generate 50 Held-out scenarios with seeds 5000..5049
    heldout_scenarios = generate_scenario_set(
        start_seed=5000,
        count=50,
        id_prefix="heldout",
    )
    heldout_output = data_dir / "heldout_scenarios.jsonl"
    save_scenarios_jsonl(heldout_scenarios, heldout_output)
    print(f"Saved {len(heldout_scenarios)} heldout scenarios -> {heldout_output}")


if __name__ == "__main__":
    main()
