"""Pure Python metrics calculation functions for MerchantOS AI evaluation."""

from __future__ import annotations

from merchantos_core.contracts import ArmResult, EvaluationMetrics


def calculate_conversion_rate(results: list[ArmResult]) -> float:
    """Calculate conversion rate (ratio of converted transactions to total scenarios)."""
    if not results:
        return 0.0
    converted_count = sum(1 for r in results if r.status == "converted")
    return converted_count / len(results)


def calculate_avg_margin(results: list[ArmResult]) -> float:
    """Calculate average contribution margin in minor units (paise) for converted transactions.

    Returns 0.0 if no transactions converted or results is empty.
    """
    margins = [r.contribution_margin_minor for r in results if r.contribution_margin_minor is not None]
    if not margins:
        return 0.0
    return float(sum(margins) / len(margins))


def calculate_gate_rejection_rate(results: list[ArmResult]) -> float:
    """Calculate gate rejection rate (ratio of scenarios blocked by CommerceProof to total scenarios)."""
    if not results:
        return 0.0
    rejection_count = sum(1 for r in results if r.status == "blocked_by_gate")
    return rejection_count / len(results)


def calculate_repair_rate(results: list[ArmResult]) -> float:
    """Calculate repair rate (ratio of scenarios where CommerceProof performed repairs to total scenarios)."""
    if not results:
        return 0.0
    repair_count = sum(1 for r in results if r.gate_repairs > 0)
    return repair_count / len(results)


def calculate_avg_rounds(results: list[ArmResult]) -> float:
    """Calculate average negotiation rounds executed per scenario."""
    if not results:
        return 0.0
    return float(sum(r.negotiation_rounds for r in results) / len(results))


def compute_evaluation_metrics(results: list[ArmResult]) -> EvaluationMetrics:
    """Compute aggregated EvaluationMetrics model from a list of ArmResult records."""
    return EvaluationMetrics(
        total_scenarios=len(results),
        conversion_rate=calculate_conversion_rate(results),
        avg_contribution_margin_minor=calculate_avg_margin(results),
        avg_negotiation_rounds=calculate_avg_rounds(results),
        gate_rejection_rate=calculate_gate_rejection_rate(results),
        repair_rate=calculate_repair_rate(results),
    )
