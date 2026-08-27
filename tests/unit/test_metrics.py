"""Unit tests for pure Python evaluation metrics calculations."""

from __future__ import annotations

import pytest

from merchantos_core.contracts import ArmResult, EvaluationMetrics
from merchantos_core.evaluation.metrics import (
    calculate_avg_margin,
    calculate_avg_rounds,
    calculate_conversion_rate,
    calculate_gate_rejection_rate,
    calculate_repair_rate,
    compute_evaluation_metrics,
)


def test_metrics_empty_list() -> None:
    """Empty list returns safe zero defaults for all metric functions."""
    results: list[ArmResult] = []

    assert calculate_conversion_rate(results) == 0.0
    assert calculate_avg_margin(results) == 0.0
    assert calculate_gate_rejection_rate(results) == 0.0
    assert calculate_repair_rate(results) == 0.0
    assert calculate_avg_rounds(results) == 0.0

    metrics = compute_evaluation_metrics(results)
    assert metrics.total_scenarios == 0
    assert metrics.conversion_rate == 0.0
    assert metrics.avg_contribution_margin_minor == 0.0
    assert metrics.avg_negotiation_rounds == 0.0
    assert metrics.gate_rejection_rate == 0.0
    assert metrics.repair_rate == 0.0


def test_calculate_conversion_rate() -> None:
    """Accurately calculates conversion rate across various ArmResult statuses."""
    results = [
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s1",
            status="converted",
            final_price_minor=10000,
            final_discount_minor=2000,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=3000,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s2",
            status="rejected",
            final_price_minor=None,
            final_discount_minor=None,
            negotiation_rounds=2,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=None,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s3",
            status="blocked_by_gate",
            final_price_minor=None,
            final_discount_minor=None,
            negotiation_rounds=1,
            gate_rejections=1,
            gate_repairs=0,
            contribution_margin_minor=None,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s4",
            status="converted",
            final_price_minor=15000,
            final_discount_minor=1000,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=1,
            contribution_margin_minor=5000,
        ),
    ]

    # 2 converted out of 4 = 0.50 (50%)
    assert calculate_conversion_rate(results) == 0.50


def test_calculate_avg_margin() -> None:
    """Averages contribution margin across converted transactions only."""
    results = [
        ArmResult(
            arm_name="growth_agent",
            scenario_id="s1",
            status="converted",
            final_price_minor=100000,
            final_discount_minor=10000,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=25000,
        ),
        ArmResult(
            arm_name="growth_agent",
            scenario_id="s2",
            status="max_rounds_reached",
            final_price_minor=None,
            final_discount_minor=None,
            negotiation_rounds=3,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=None,
        ),
        ArmResult(
            arm_name="growth_agent",
            scenario_id="s3",
            status="converted",
            final_price_minor=120000,
            final_discount_minor=15000,
            negotiation_rounds=2,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=35000,
        ),
    ]

    # Converted margins: 25000 + 35000 = 60000 / 2 = 30000.0
    assert calculate_avg_margin(results) == 30000.0


def test_calculate_gate_rejection_and_repair_rates() -> None:
    """Accurately calculates gate rejection rate and CommerceProof repair rate."""
    results = [
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s1",
            status="converted",
            final_price_minor=100000,
            final_discount_minor=5000,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=1,  # Repaired and converted
            contribution_margin_minor=20000,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s2",
            status="blocked_by_gate",
            final_price_minor=None,
            final_discount_minor=None,
            negotiation_rounds=1,
            gate_rejections=1,  # Rejected by gate
            gate_repairs=0,
            contribution_margin_minor=None,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s3",
            status="converted",
            final_price_minor=90000,
            final_discount_minor=0,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=15000,
        ),
        ArmResult(
            arm_name="rules_baseline",
            scenario_id="s4",
            status="rejected",
            final_price_minor=None,
            final_discount_minor=None,
            negotiation_rounds=2,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=None,
        ),
    ]

    # Gate rejection rate: 1 blocked_by_gate / 4 = 0.25
    assert calculate_gate_rejection_rate(results) == 0.25

    # Repair rate: 1 scenario with gate_repairs > 0 / 4 = 0.25
    assert calculate_repair_rate(results) == 0.25

    # Avg rounds: (1 + 1 + 1 + 2) / 4 = 1.25
    assert calculate_avg_rounds(results) == 1.25


def test_compute_evaluation_metrics_complete() -> None:
    """compute_evaluation_metrics populates all required fields matching Pydantic contract."""
    results = [
        ArmResult(
            arm_name="growth_agent",
            scenario_id="s1",
            status="converted",
            final_price_minor=100000,
            final_discount_minor=10000,
            negotiation_rounds=1,
            gate_rejections=0,
            gate_repairs=0,
            contribution_margin_minor=30000,
        )
    ]
    metrics = compute_evaluation_metrics(results)
    assert isinstance(metrics, EvaluationMetrics)
    assert metrics.total_scenarios == 1
    assert metrics.conversion_rate == 1.0
    assert metrics.avg_contribution_margin_minor == 30000.0
    assert metrics.avg_negotiation_rounds == 1.0
    assert metrics.gate_rejection_rate == 0.0
    assert metrics.repair_rate == 0.0
