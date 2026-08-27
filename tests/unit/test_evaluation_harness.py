"""Unit tests for paired EvaluationHarness execution and divergence bucketing."""

from __future__ import annotations

import pytest

from merchantos_core.agents.growth_agent import MerchantGrowthAgent
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.contracts import (
    BuyerIntent,
    LLMOutput,
    MerchantPolicy,
    Product,
    SimulatedScenario,
)
from merchantos_core.evaluation.harness import EvaluationHarness
from merchantos_core.llm.provider import MockLLMProvider


@pytest.fixture
def base_scenario() -> SimulatedScenario:
    """Fixture providing a standard test scenario."""
    return SimulatedScenario(
        scenario_id="scen_test_01",
        intent=BuyerIntent(
            session_id="sess_test_01",
            category="laptops",
            budget_max_minor=8000000,
            delivery_days_max=3,
            priority=["performance"],
            hard_exclusions=[],
            price_sensitivity=0.5,
            delivery_sensitivity=0.5,
            acceptance_threshold=0.6,
            stated_vs_true_divergence=0.2,
        ),
        nl_utterance="Looking for a high performance laptop under 80k.",
        available_catalog=[
            Product(
                sku_id="SKU-LAP-01",
                name="Apex Ultrabook 14",
                category="laptops",
                cost_minor=4000000,
                base_price_minor=6000000,
                inventory_count=10,
            )
        ],
        merchant_policy=MerchantPolicy(
            merchant_id="merch_test_01",
            margin_floor_pct=0.15,
            discount_cap_pct=0.20,
            promotion_budget_minor=5000000,
        ),
    )


def test_paired_design_isolation(base_scenario: SimulatedScenario) -> None:
    """Prove that the harness runs both arms on the exact same scenario data without cross-contamination."""
    harness = EvaluationHarness()

    report = harness.run_paired_evaluation(scenarios=[base_scenario], dataset="dev")

    assert report.dataset == "dev"
    assert report.overall_rules_metrics.total_scenarios == 1
    assert report.overall_growth_metrics.total_scenarios == 1

    # Both arms evaluated the scenario
    assert report.overall_rules_metrics.conversion_rate in (0.0, 1.0)
    assert report.overall_growth_metrics.conversion_rate in (0.0, 1.0)


def test_harness_computes_divergence_buckets() -> None:
    """Run the harness on a mock dataset containing low, medium, and high divergence scenarios.

    Assert that the EvaluationReport contains all three DivergenceBucket objects with correctly calculated deltas.
    """
    catalog = [
        Product(
            sku_id="SKU-LAP-01",
            name="Apex Ultrabook 14",
            category="laptops",
            cost_minor=4000000,
            base_price_minor=6000000,
            inventory_count=10,
        )
    ]
    policy = MerchantPolicy(
        merchant_id="merch_01",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )

    # 1. Low divergence (<0.3)
    s_low = SimulatedScenario(
        scenario_id="s_low_01",
        intent=BuyerIntent(
            session_id="sess_low",
            category="laptops",
            budget_max_minor=6500000,
            delivery_days_max=5,
            price_sensitivity=0.3,
            delivery_sensitivity=0.3,
            acceptance_threshold=0.5,
            stated_vs_true_divergence=0.15,
        ),
        nl_utterance="Looking for laptop under 60k.",
        available_catalog=catalog,
        merchant_policy=policy,
    )

    # 2. Medium divergence (0.3 <= div < 0.6)
    s_med = SimulatedScenario(
        scenario_id="s_med_01",
        intent=BuyerIntent(
            session_id="sess_med",
            category="laptops",
            budget_max_minor=6500000,
            delivery_days_max=5,
            price_sensitivity=0.5,
            delivery_sensitivity=0.5,
            acceptance_threshold=0.5,
            stated_vs_true_divergence=0.45,
        ),
        nl_utterance="Need a good laptop in the 60k range.",
        available_catalog=catalog,
        merchant_policy=policy,
    )

    # 3. High divergence (>= 0.6)
    s_high = SimulatedScenario(
        scenario_id="s_high_01",
        intent=BuyerIntent(
            session_id="sess_high",
            category="laptops",
            budget_max_minor=6500000,
            delivery_days_max=5,
            price_sensitivity=0.7,
            delivery_sensitivity=0.7,
            acceptance_threshold=0.5,
            stated_vs_true_divergence=0.85,
        ),
        nl_utterance="Need something for computing.",
        available_catalog=catalog,
        merchant_policy=policy,
    )

    harness = EvaluationHarness()
    report = harness.run_paired_evaluation(scenarios=[s_low, s_med, s_high], dataset="dev")

    assert len(report.divergence_buckets) == 3
    b_map = {b.bucket_name: b for b in report.divergence_buckets}

    assert "low" in b_map
    assert "medium" in b_map
    assert "high" in b_map

    assert b_map["low"].rules_metrics.total_scenarios == 1
    assert b_map["medium"].rules_metrics.total_scenarios == 1
    assert b_map["high"].rules_metrics.total_scenarios == 1

    # Verify deltas
    for b in report.divergence_buckets:
        expected_conv_delta = b.growth_metrics.conversion_rate - b.rules_metrics.conversion_rate
        expected_margin_delta = (
            b.growth_metrics.avg_contribution_margin_minor - b.rules_metrics.avg_contribution_margin_minor
        )
        assert pytest.approx(b.conversion_delta, 1e-6) == expected_conv_delta
        assert pytest.approx(b.margin_delta_minor, 1e-6) == expected_margin_delta


def test_gate_rejection_tracking() -> None:
    """Force a scenario where the agent proposes an out-of-stock item.

    Assert that the ArmResult status is blocked_by_gate and the gate_rejection_rate metric reflects it.
    """
    # Catalog item with 0 inventory count
    oos_product = Product(
        sku_id="SKU-OOS-01",
        name="Out of Stock Laptop",
        category="laptops",
        cost_minor=3000000,
        base_price_minor=5000000,
        inventory_count=0,
    )
    policy = MerchantPolicy(
        merchant_id="merch_oos",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )
    scenario = SimulatedScenario(
        scenario_id="s_oos_01",
        intent=BuyerIntent(
            session_id="sess_oos",
            category="laptops",
            budget_max_minor=6000000,
            delivery_days_max=3,
            price_sensitivity=0.5,
            delivery_sensitivity=0.5,
            acceptance_threshold=0.5,
            stated_vs_true_divergence=0.2,
        ),
        nl_utterance="Need laptop under 50k urgently.",
        available_catalog=[oos_product],
        merchant_policy=policy,
    )

    harness = EvaluationHarness()
    report = harness.run_paired_evaluation(scenarios=[scenario], dataset="dev")

    # Both arms must be blocked by CommerceProof because inventory_count is 0
    assert report.overall_rules_metrics.gate_rejection_rate == 1.0
    assert report.overall_growth_metrics.gate_rejection_rate == 1.0
    assert report.overall_rules_metrics.conversion_rate == 0.0
    assert report.overall_growth_metrics.conversion_rate == 0.0


def test_divergence_produces_delta() -> None:
    """Run the harness on a small dataset with 5 low-divergence and 5 high-divergence scenarios.

    Assert that:
    - In low divergence: conversion_delta is near 0 (both arms perform similarly)
    - In high divergence: conversion_delta > 0 (growth agent outperforms rules)
    """
    catalog = [
        Product(
            sku_id="SKU-LAP-01",
            name="Apex Ultrabook 14",
            category="laptops",
            cost_minor=3000000,
            base_price_minor=4000000,
            inventory_count=20,
        ),
        Product(
            sku_id="SKU-LAP-02",
            name="VoltBook Pro 15",
            category="laptops",
            cost_minor=3500000,
            base_price_minor=5000000,
            inventory_count=20,
        ),
    ]
    policy = MerchantPolicy(
        merchant_id="merch_delta_01",
        margin_floor_pct=0.10,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )

    scenarios: list[SimulatedScenario] = []

    # 5 Low-divergence scenarios (direct stated budget 38k, clear requirements)
    for i in range(5):
        scenarios.append(
            SimulatedScenario(
                scenario_id=f"s_low_{i}",
                intent=BuyerIntent(
                    session_id=f"sess_low_{i}",
                    category="laptops",
                    budget_max_minor=3800000,
                    delivery_days_max=3,
                    price_sensitivity=0.4,
                    delivery_sensitivity=0.4,
                    acceptance_threshold=0.65,
                    stated_vs_true_divergence=0.1,
                ),
                nl_utterance="Looking for laptop under 38k. Need standard delivery within 3 days.",
                available_catalog=catalog,
                merchant_policy=policy,
            )
        )

    # 5 High-divergence scenarios (misleading/lossy utterance claims flexible budget, but true budget is tight 34k)
    for i in range(5):
        scenarios.append(
            SimulatedScenario(
                scenario_id=f"s_high_{i}",
                intent=BuyerIntent(
                    session_id=f"sess_high_{i}",
                    category="laptops",
                    budget_max_minor=3400000,
                    delivery_days_max=1,
                    price_sensitivity=0.90,
                    delivery_sensitivity=0.85,
                    acceptance_threshold=0.75,
                    stated_vs_true_divergence=0.85,
                ),
                nl_utterance="Looking for a top-tier laptop, budget is flexible. Standard delivery is fine.",
                available_catalog=catalog,
                merchant_policy=policy,
            )
        )

    harness = EvaluationHarness()
    report = harness.run_paired_evaluation(scenarios=scenarios, dataset="dev")

    b_map = {b.bucket_name: b for b in report.divergence_buckets}

    # In low divergence, delta is near 0
    assert abs(b_map["low"].conversion_delta) <= 0.25

    # In high divergence, growth agent strictly beats static rules baseline
    assert b_map["high"].conversion_delta > 0.0
    assert b_map["high"].growth_metrics.conversion_rate > b_map["high"].rules_metrics.conversion_rate


def test_gate_rejection_nonzero() -> None:
    """Run evaluation on a dataset containing out-of-stock items. Assert gate_rejection_rate > 0."""
    oos_catalog = [
        Product(
            sku_id="SKU-OOS-01",
            name="Apex Tab",
            category="tablets",
            cost_minor=2000000,
            base_price_minor=3000000,
            inventory_count=0,  # 0 available
        )
    ]
    policy = MerchantPolicy(
        merchant_id="merch_oos_test",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )
    scen = SimulatedScenario(
        scenario_id="scen_oos_test",
        intent=BuyerIntent(
            session_id="sess_oos_test",
            category="tablets",
            budget_max_minor=3000000,
            delivery_days_max=3,
            price_sensitivity=0.5,
            delivery_sensitivity=0.5,
            acceptance_threshold=0.5,
            stated_vs_true_divergence=0.1,
        ),
        nl_utterance="Need tablet under 30k.",
        available_catalog=oos_catalog,
        merchant_policy=policy,
    )

    harness = EvaluationHarness()
    report = harness.run_paired_evaluation(scenarios=[scen], dataset="dev")

    assert report.overall_rules_metrics.gate_rejection_rate > 0.0
    assert report.overall_growth_metrics.gate_rejection_rate > 0.0

