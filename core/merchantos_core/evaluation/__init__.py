"""Evaluation package for MerchantOS AI."""

from __future__ import annotations

from merchantos_core.evaluation.harness import EvaluationHarness
from merchantos_core.evaluation.metrics import (
    calculate_avg_margin,
    calculate_avg_rounds,
    calculate_conversion_rate,
    calculate_gate_rejection_rate,
    calculate_repair_rate,
    compute_evaluation_metrics,
)

__all__ = [
    "EvaluationHarness",
    "calculate_avg_margin",
    "calculate_avg_rounds",
    "calculate_conversion_rate",
    "calculate_gate_rejection_rate",
    "calculate_repair_rate",
    "compute_evaluation_metrics",
]
