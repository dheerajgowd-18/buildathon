"""Tests verifying the strict fairness boundary of AgentInput and agent execution."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.contracts import (
    AgentInput,
    BuyerIntent,
    MerchantPolicy,
    Product,
    SimulatedScenario,
)


@pytest.fixture
def sample_catalog() -> list[Product]:
    return [
        Product(
            sku_id="SKU-LAP-001",
            name="Apex Ultrabook 14",
            category="laptops",
            cost_minor=3000000,
            base_price_minor=4000000,
            inventory_count=10,
        ),
        Product(
            sku_id="SKU-LAP-002",
            name="VoltBook Pro 15",
            category="laptops",
            cost_minor=4000000,
            base_price_minor=5500000,
            inventory_count=5,
        ),
    ]


@pytest.fixture
def sample_policy() -> MerchantPolicy:
    return MerchantPolicy(
        merchant_id="merch_001",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )


@pytest.fixture
def sample_intent() -> BuyerIntent:
    return BuyerIntent(
        session_id="sess_1001",
        category="laptops",
        budget_max_minor=4500000,
        delivery_days_max=2,
        priority=["performance"],
        hard_exclusions=["heavy"],
        price_sensitivity=0.6,
        delivery_sensitivity=0.8,
        acceptance_threshold=0.75,
        stated_vs_true_divergence=0.4,
    )


@pytest.fixture
def sample_scenario(
    sample_intent: BuyerIntent,
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> SimulatedScenario:
    return SimulatedScenario(
        scenario_id="dev_001",
        intent=sample_intent,
        nl_utterance="Looking for a laptop with budget around 45k.",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )


def test_agent_input_rejects_ground_truth(
    sample_scenario: SimulatedScenario,
    sample_intent: BuyerIntent,
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Prove that attempting to instantiate AgentInput with BuyerIntent or SimulatedScenario raises ValidationError."""
    # 1. Reject passing full SimulatedScenario dictionary (contains 'scenario_id' and 'intent')
    with pytest.raises(ValidationError) as exc_info:
        AgentInput.model_validate(sample_scenario.model_dump())
    errors = exc_info.value.errors()
    extra_field_errors = [e for e in errors if e.get("type") == "extra_forbidden"]
    assert len(extra_field_errors) >= 1
    assert any("intent" in str(e.get("loc")) for e in extra_field_errors)

    # 2. Reject passing BuyerIntent dictionary (contains 'budget_max_minor', 'price_sensitivity', etc.)
    with pytest.raises(ValidationError):
        AgentInput.model_validate(sample_intent.model_dump())

    # 3. Reject keyword argument injection of ground truth fields
    with pytest.raises(ValidationError):
        AgentInput(
            session_id="sess_1001",
            nl_utterance="Need a laptop under 45k",
            available_catalog=sample_catalog,
            merchant_policy=sample_policy,
            intent=sample_intent,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        AgentInput(
            session_id="sess_1001",
            nl_utterance="Need a laptop under 45k",
            available_catalog=sample_catalog,
            merchant_policy=sample_policy,
            price_sensitivity=0.9,  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        AgentInput(
            session_id="sess_1001",
            nl_utterance="Need a laptop under 45k",
            available_catalog=sample_catalog,
            merchant_policy=sample_policy,
            budget_max_minor=4500000,  # type: ignore[call-arg]
        )


def test_agent_input_valid_instantiation(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify valid instantiation of AgentInput without any ground-truth fields."""
    agent_input = AgentInput(
        session_id="sess_1001",
        nl_utterance="Looking for a laptop under ₹45,000.",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )
    assert agent_input.session_id == "sess_1001"
    assert agent_input.nl_utterance == "Looking for a laptop under ₹45,000."
    assert len(agent_input.available_catalog) == 2
    assert agent_input.merchant_policy.merchant_id == "merch_001"

    # Verify model fields schema strictly excludes ground truth
    forbidden_field_names = {
        "intent",
        "buyer_intent",
        "budget_max_minor",
        "price_sensitivity",
        "delivery_sensitivity",
        "acceptance_threshold",
        "priority",
        "hard_exclusions",
        "stated_vs_true_divergence",
    }
    assert forbidden_field_names.isdisjoint(set(AgentInput.model_fields.keys()))


def test_rules_agent_rejects_simulated_scenario_direct_input(
    sample_scenario: SimulatedScenario,
) -> None:
    """Verify that score_and_propose physically rejects SimulatedScenario instances."""
    agent = RulesBaselineAgent()
    with pytest.raises((ValidationError, TypeError)):
        agent.score_and_propose(sample_scenario)  # type: ignore[arg-type]
