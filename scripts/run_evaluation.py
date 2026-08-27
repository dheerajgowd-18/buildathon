"""CLI script to run paired evaluation benchmarks and report divergence metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure core directory is on sys.path for standalone script execution
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORE_PATH = _REPO_ROOT / "core"
if str(_CORE_PATH) not in sys.path:
    sys.path.insert(0, str(_CORE_PATH))

from merchantos_core.contracts import EvaluationReport, SimulatedScenario
from merchantos_core.evaluation.harness import EvaluationHarness



def load_scenarios(file_path: Path) -> list[SimulatedScenario]:
    """Load simulated scenarios from a JSONL dataset file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Scenario dataset not found: {file_path}")

    scenarios: list[SimulatedScenario] = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line_str = line.strip()
            if not line_str:
                continue
            try:
                data = json.loads(line_str)
                scenario = SimulatedScenario.model_validate(data)
                scenarios.append(scenario)
            except Exception as e:
                raise ValueError(f"Error parsing scenario at line {line_num} in {file_path}: {e}") from e

    return scenarios


def render_ascii_report(report: EvaluationReport) -> str:
    """Render a clean, beautifully formatted ASCII report with divergence deltas."""
    lines: list[str] = []
    sep = "=" * 90
    sub_sep = "-" * 90

    lines.append(sep)
    lines.append(f"  MERCHANTOS AI EVALUATION HARNESS - PAIRED BENCHMARK REPORT")
    lines.append(f"  Report ID: {report.report_id} | Timestamp: {report.timestamp} | Dataset: {report.dataset.upper()}")
    lines.append(sep)
    lines.append("")

    # Overall Summary Table
    lines.append("1. OVERALL AGENT PERFORMANCE (Paired Design)")
    lines.append(sub_sep)
    lines.append(
        f"{'Metric':<32} | {'Rules Baseline':<20} | {'Merchant Growth Agent':<22} | {'Delta (Growth - Rules)':<15}"
    )
    lines.append(sub_sep)

    rules_o = report.overall_rules_metrics
    growth_o = report.overall_growth_metrics

    conv_delta_pct = (growth_o.conversion_rate - rules_o.conversion_rate) * 100
    conv_delta_str = f"{conv_delta_pct:+.1f}%"

    margin_delta_inr = (growth_o.avg_contribution_margin_minor - rules_o.avg_contribution_margin_minor) / 100.0
    margin_delta_str = f"Rs.{margin_delta_inr:+,.2f}"

    rounds_delta = growth_o.avg_negotiation_rounds - rules_o.avg_negotiation_rounds
    rounds_delta_str = f"{rounds_delta:+.2f}"

    lines.append(
        f"{'Total Scenarios':<32} | {rules_o.total_scenarios:<20} | {growth_o.total_scenarios:<22} | {'--':<15}"
    )
    lines.append(
        f"{'Conversion Rate':<32} | {rules_o.conversion_rate * 100:6.1f}%{'':<13} | {growth_o.conversion_rate * 100:6.1f}%{'':<15} | {conv_delta_str:<15}"
    )
    lines.append(
        f"{'Avg Contribution Margin':<32} | Rs.{rules_o.avg_contribution_margin_minor / 100:10,.2f}{'':<7} | Rs.{growth_o.avg_contribution_margin_minor / 100:10,.2f}{'':<9} | {margin_delta_str:<15}"
    )
    lines.append(
        f"{'Avg Negotiation Rounds':<32} | {rules_o.avg_negotiation_rounds:6.2f}{'':<14} | {growth_o.avg_negotiation_rounds:6.2f}{'':<16} | {rounds_delta_str:<15}"
    )
    lines.append(
        f"{'Gate Rejection Rate (BLOCK)':<32} | {rules_o.gate_rejection_rate * 100:6.1f}%{'':<13} | {growth_o.gate_rejection_rate * 100:6.1f}%{'':<15} | {'--':<15}"
    )
    lines.append(
        f"{'CommerceProof Repair Rate':<32} | {rules_o.repair_rate * 100:6.1f}%{'':<13} | {growth_o.repair_rate * 100:6.1f}%{'':<15} | {'--':<15}"
    )
    lines.append(sub_sep)
    lines.append("")

    # Divergence Analysis Table
    lines.append("2. THE DIVERGENCE THESIS: PERFORMANCE BREAKDOWN BY STATED-VS-TRUE INTENT DIVERGENCE")
    lines.append("   (Proving AI pulls ahead as buyer intent ambiguity increases)")
    lines.append(sub_sep)
    lines.append(
        f"{'Divergence Bucket':<20} | {'Scenarios':<10} | {'Rules Conv':<12} | {'Growth Conv':<12} | {'Conv Delta':<12} | {'Margin Delta':<14}"
    )
    lines.append(sub_sep)

    for bucket in report.divergence_buckets:
        b_name = f"{bucket.bucket_name.upper()} ({bucket.divergence_range})"
        scen_count = bucket.rules_metrics.total_scenarios
        r_conv = f"{bucket.rules_metrics.conversion_rate * 100:.1f}%"
        g_conv = f"{bucket.growth_metrics.conversion_rate * 100:.1f}%"
        c_delta = f"{bucket.conversion_delta * 100:+.1f}%"
        m_delta = f"Rs.{bucket.margin_delta_minor / 100:+,.2f}"


        lines.append(
            f"{b_name:<20} | {scen_count:<10} | {r_conv:<12} | {g_conv:<12} | {c_delta:<12} | {m_delta:<14}"
        )

    lines.append(sub_sep)
    lines.append(sep)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paired evaluation benchmark for MerchantOS AI.")
    parser.add_argument(
        "--dataset",
        choices=["dev", "heldout"],
        default="dev",
        help="Dataset split to evaluate (default: dev)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to directory containing dataset jsonl files (default: data)",
    )
    args = parser.parse_args()

    data_file = args.data_dir / f"{args.dataset}_scenarios.jsonl"
    print(f"[Evaluation] Loading scenarios from: {data_file}")
    scenarios = load_scenarios(data_file)
    print(f"[Evaluation] Loaded {len(scenarios)} scenarios.")

    print(f"[Evaluation] Executing paired evaluation across rules_baseline and growth_agent...")
    harness = EvaluationHarness()
    report = harness.run_paired_evaluation(scenarios=scenarios, dataset=args.dataset)

    # Print ASCII summary
    print("\n" + render_ascii_report(report) + "\n")

    # Save JSON report
    output_file = args.data_dir / f"evaluation_report_{args.dataset}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))
    print(f"[Evaluation] Saved full raw report JSON to: {output_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
