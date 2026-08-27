"""Evaluation Harness for paired benchmark execution across baseline and growth agents."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
import uuid

from merchantos_core.agents.growth_agent import MerchantGrowthAgent
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.contracts import (
    ArmResult,
    CumulativeLedger,
    DivergenceBucket,
    EvaluationReport,
    InventoryRecord,
    InventoryState,
    SimulatedScenario,
)
from merchantos_core.evaluation.metrics import compute_evaluation_metrics
from merchantos_core.llm.provider import AbstractLLMProvider, MockLLMProvider
from merchantos_core.negotiation.engine import NegotiationEngine


class EvaluationHarness:
    """Paired evaluation engine running scenarios across rules and growth agents.

    Enforces the master plan paired design: each scenario in the benchmark dataset
    is run under identical starting conditions for both arms (rules_baseline and
    growth_agent), guaranteeing high statistical validity and hermetic isolation.
    """

    def __init__(
        self,
        rules_agent: RulesBaselineAgent | None = None,
        growth_agent: MerchantGrowthAgent | None = None,
        negotiation_engine: NegotiationEngine | None = None,
        commerce_proof: CommerceProof | None = None,
        llm_provider: AbstractLLMProvider | None = None,
    ) -> None:
        self.rules_agent: RulesBaselineAgent = rules_agent or RulesBaselineAgent()
        self.growth_agent: MerchantGrowthAgent = growth_agent or MerchantGrowthAgent(
            llm_provider=llm_provider or MockLLMProvider()
        )
        self.negotiation_engine: NegotiationEngine = negotiation_engine or NegotiationEngine()
        self.commerce_proof: CommerceProof = commerce_proof or CommerceProof()

    def _evaluate_arm(
        self,
        arm_name: Literal["rules_baseline", "growth_agent"],
        scenario: SimulatedScenario,
        agent: RulesBaselineAgent | MerchantGrowthAgent,
    ) -> ArmResult:
        """Run a single scenario through an agent arm, negotiation engine, and CommerceProof gate."""
        inventory = InventoryState(
            records=[
                InventoryRecord(sku_id=p.sku_id, available_count=p.inventory_count)
                for p in scenario.available_catalog
            ]
        )
        ledger = CumulativeLedger(
            merchant_id=scenario.merchant_policy.merchant_id,
            total_promotion_budget_minor=scenario.merchant_policy.promotion_budget_minor,
            total_discount_minor_used=0,
        )

        session_state = self.negotiation_engine.run_session(
            scenario=scenario,
            merchant_agent=agent,
        )
        rounds = session_state.current_round

        if session_state.final_offer is None:
            return ArmResult(
                arm_name=arm_name,
                scenario_id=scenario.scenario_id,
                status="rejected",
                final_price_minor=None,
                final_discount_minor=None,
                negotiation_rounds=rounds,
                gate_rejections=0,
                gate_repairs=0,
                contribution_margin_minor=None,
            )

        decision = self.commerce_proof.evaluate(
            offer=session_state.final_offer,
            policy=scenario.merchant_policy,
            inventory=inventory,
            ledger=ledger,
            catalog=scenario.available_catalog,
        )

        gate_rejections = 1 if decision.action == "BLOCK" else 0
        gate_repairs = 1 if decision.action == "REPAIR" else 0

        if decision.action == "BLOCK":
            return ArmResult(
                arm_name=arm_name,
                scenario_id=scenario.scenario_id,
                status="blocked_by_gate",
                final_price_minor=None,
                final_discount_minor=None,
                negotiation_rounds=rounds,
                gate_rejections=gate_rejections,
                gate_repairs=gate_repairs,
                contribution_margin_minor=None,
            )

        # Decision is EXECUTE or REPAIR
        if session_state.status == "accepted":
            final_offer = decision.final_offer or session_state.final_offer
            final_price = final_offer.proposed_price_minor
            final_discount = final_offer.discount_minor
            product = next(
                (p for p in scenario.available_catalog if p.sku_id == final_offer.selected_sku_id),
                None,
            )
            cost = product.cost_minor if product else 0
            margin = final_price - cost

            return ArmResult(
                arm_name=arm_name,
                scenario_id=scenario.scenario_id,
                status="converted",
                final_price_minor=final_price,
                final_discount_minor=final_discount,
                negotiation_rounds=rounds,
                gate_rejections=gate_rejections,
                gate_repairs=gate_repairs,
                contribution_margin_minor=margin,
            )
        elif session_state.status == "rejected":
            return ArmResult(
                arm_name=arm_name,
                scenario_id=scenario.scenario_id,
                status="rejected",
                final_price_minor=None,
                final_discount_minor=None,
                negotiation_rounds=rounds,
                gate_rejections=gate_rejections,
                gate_repairs=gate_repairs,
                contribution_margin_minor=None,
            )
        else:  # max_rounds_reached
            return ArmResult(
                arm_name=arm_name,
                scenario_id=scenario.scenario_id,
                status="max_rounds_reached",
                final_price_minor=None,
                final_discount_minor=None,
                negotiation_rounds=rounds,
                gate_rejections=gate_rejections,
                gate_repairs=gate_repairs,
                contribution_margin_minor=None,
            )

    def run_paired_evaluation(
        self,
        scenarios: list[SimulatedScenario],
        dataset: Literal["dev", "heldout"] = "dev",
    ) -> EvaluationReport:
        """Execute paired evaluation across all scenarios and generate the EvaluationReport.

        Args:
            scenarios: List of simulated buyer scenarios.
            dataset: Dataset split identifier ("dev" or "heldout").

        Returns:
            Fully populated EvaluationReport model.
        """
        rules_results: list[ArmResult] = []
        growth_results: list[ArmResult] = []

        # 1. Paired Execution
        for scenario in scenarios:
            # Arm A: Rules Baseline
            rules_res = self._evaluate_arm(
                arm_name="rules_baseline",
                scenario=scenario,
                agent=self.rules_agent,
            )
            rules_results.append(rules_res)

            # Arm B: Growth Agent (Identical Scenario)
            growth_res = self._evaluate_arm(
                arm_name="growth_agent",
                scenario=scenario,
                agent=self.growth_agent,
            )
            growth_results.append(growth_res)

        # 2. Overall Metrics
        overall_rules_metrics = compute_evaluation_metrics(rules_results)
        overall_growth_metrics = compute_evaluation_metrics(growth_results)

        # 3. Divergence Bucketing
        low_ids = {s.scenario_id for s in scenarios if s.intent.stated_vs_true_divergence < 0.3}
        med_ids = {
            s.scenario_id
            for s in scenarios
            if 0.3 <= s.intent.stated_vs_true_divergence < 0.6
        }
        high_ids = {s.scenario_id for s in scenarios if s.intent.stated_vs_true_divergence >= 0.6}

        # Low Bucket (<0.3)
        low_rules = [r for r in rules_results if r.scenario_id in low_ids]
        low_growth = [r for r in growth_results if r.scenario_id in low_ids]
        low_rules_m = compute_evaluation_metrics(low_rules)
        low_growth_m = compute_evaluation_metrics(low_growth)
        low_bucket = DivergenceBucket(
            bucket_name="low",
            divergence_range="<0.3",
            rules_metrics=low_rules_m,
            growth_metrics=low_growth_m,
            conversion_delta=low_growth_m.conversion_rate - low_rules_m.conversion_rate,
            margin_delta_minor=low_growth_m.avg_contribution_margin_minor - low_rules_m.avg_contribution_margin_minor,
        )

        # Medium Bucket (0.3 <= div < 0.6)
        med_rules = [r for r in rules_results if r.scenario_id in med_ids]
        med_growth = [r for r in growth_results if r.scenario_id in med_ids]
        med_rules_m = compute_evaluation_metrics(med_rules)
        med_growth_m = compute_evaluation_metrics(med_growth)
        med_bucket = DivergenceBucket(
            bucket_name="medium",
            divergence_range="0.3-0.6",
            rules_metrics=med_rules_m,
            growth_metrics=med_growth_m,
            conversion_delta=med_growth_m.conversion_rate - med_rules_m.conversion_rate,
            margin_delta_minor=med_growth_m.avg_contribution_margin_minor - med_rules_m.avg_contribution_margin_minor,
        )

        # High Bucket (>= 0.6)
        high_rules = [r for r in rules_results if r.scenario_id in high_ids]
        high_growth = [r for r in growth_results if r.scenario_id in high_ids]
        high_rules_m = compute_evaluation_metrics(high_rules)
        high_growth_m = compute_evaluation_metrics(high_growth)
        high_bucket = DivergenceBucket(
            bucket_name="high",
            divergence_range=">=0.6",
            rules_metrics=high_rules_m,
            growth_metrics=high_growth_m,
            conversion_delta=high_growth_m.conversion_rate - high_rules_m.conversion_rate,
            margin_delta_minor=high_growth_m.avg_contribution_margin_minor - high_rules_m.avg_contribution_margin_minor,
        )

        report_id = f"eval_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        return EvaluationReport(
            report_id=report_id,
            timestamp=timestamp,
            dataset=dataset,
            overall_rules_metrics=overall_rules_metrics,
            overall_growth_metrics=overall_growth_metrics,
            divergence_buckets=[low_bucket, med_bucket, high_bucket],
        )
