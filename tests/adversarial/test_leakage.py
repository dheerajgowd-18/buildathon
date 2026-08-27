"""P0 Ground-Truth Leakage Test Suite."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from merchantos_core.contracts import BuyerIntent, SimulatedScenario

INTERNAL_FIELD_NAMES = list(BuyerIntent.model_fields.keys())


def load_scenarios(file_path: Path) -> list[SimulatedScenario]:
    """Read and validate SimulatedScenario objects from a JSONL file."""
    assert file_path.exists(), f"Scenario file does not exist: {file_path}"
    scenarios: list[SimulatedScenario] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            scenario = SimulatedScenario.model_validate(data)
            scenarios.append(scenario)
    return scenarios


def test_no_ground_truth_leakage_in_utterances() -> None:
    """P0 Leakage Test: Ensure NLG engine never leaks ground-truth fields or raw values."""
    repo_root = Path(__file__).resolve().parents[2]
    data_dir = repo_root / "data"

    dev_file = data_dir / "dev_scenarios.jsonl"
    heldout_file = data_dir / "heldout_scenarios.jsonl"

    all_scenarios: list[SimulatedScenario] = []
    all_scenarios.extend(load_scenarios(dev_file))
    all_scenarios.extend(load_scenarios(heldout_file))

    assert len(all_scenarios) == 150, f"Expected 150 total scenarios, found {len(all_scenarios)}"

    leakage_failures: list[str] = []

    for scenario in all_scenarios:
        utterance_lower = scenario.nl_utterance.lower()
        scenario_id = scenario.scenario_id
        intent = scenario.intent

        # 1. Assert internal field names never appear in nl_utterance
        for field_name in INTERNAL_FIELD_NAMES:
            if field_name.lower() in utterance_lower:
                leakage_failures.append(
                    f"Scenario {scenario_id} leaked internal field name '{field_name}' in utterance: '{scenario.nl_utterance}'"
                )

        # 2. Check raw minor unit integer (paise)
        raw_minor_str = str(intent.budget_max_minor)
        if raw_minor_str in scenario.nl_utterance:
            leakage_failures.append(
                f"Scenario {scenario_id} leaked raw minor budget '{raw_minor_str}' in utterance: '{scenario.nl_utterance}'"
            )

        # 3. Assert raw integer value of budget (in INR or minor) does not appear as raw digits if divergence > 0.2
        if intent.stated_vs_true_divergence > 0.2:
            raw_inr_str = str(intent.budget_max_minor // 100)
            if raw_inr_str in scenario.nl_utterance:
                leakage_failures.append(
                    f"Scenario {scenario_id} leaked raw unformatted budget integer '{raw_inr_str}' (divergence={intent.stated_vs_true_divergence}) in utterance: '{scenario.nl_utterance}'"
                )

    if leakage_failures:
        error_msg = "\n".join(leakage_failures)
        pytest.fail(f"Ground truth leakage detected in {len(leakage_failures)} instances:\n{error_msg}")
