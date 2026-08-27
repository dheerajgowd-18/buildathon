"""Unit tests for MerchantGrowthAgent and 'LLM Proposes, Code Disposes' safety clamping."""

from __future__ import annotations

import inspect
import pytest
from pydantic import ValidationError

from merchantos_core.agents.growth_agent import MerchantGrowthAgent
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.contracts import (
    AgentInput,
    LLMOutput,
    MerchantPolicy,
    Product,
    ProposedOffer,
    SimulatedScenario,
)
from merchantos_core.llm.provider import MockLLMProvider


@pytest.fixture
def sample_catalog() -> list[Product]:
    return [
        Product(
            sku_id="SKU-LAP-001",
            name="Apex Ultrabook 14",
            category="laptops",
            cost_minor=3000000,       # ₹30,000 cost
            base_price_minor=4000000, # ₹40,000 base price
            inventory_count=10,
        ),
        Product(
            sku_id="SKU-LAP-002",
            name="VoltBook Pro 15",
            category="laptops",
            cost_minor=4000000,       # ₹40,000 cost
            base_price_minor=5500000, # ₹55,000 base price
            inventory_count=5,
        ),
    ]


@pytest.fixture
def sample_policy() -> MerchantPolicy:
    return MerchantPolicy(
        merchant_id="merch_001",
        margin_floor_pct=0.10,        # 10% margin floor: min price = cost * 1.10 = ₹33,000 for SKU-001
        discount_cap_pct=0.10,        # 10% discount cap: max discount = base * 0.10 = ₹4,000 (400,000 paise)
        promotion_budget_minor=5000000,
    )


def test_growth_agent_interface_compliance() -> None:
    """Prove MerchantGrowthAgent has the exact same score_and_propose signature as RulesBaselineAgent."""
    growth_sig = inspect.signature(MerchantGrowthAgent.score_and_propose)
    rules_sig = inspect.signature(RulesBaselineAgent.score_and_propose)

    assert growth_sig.parameters.keys() == rules_sig.parameters.keys()
    assert list(growth_sig.parameters.keys()) == ["self", "agent_input"]

    # Both return ProposedOffer
    assert growth_sig.return_annotation in (ProposedOffer, "ProposedOffer")
    assert rules_sig.return_annotation in (ProposedOffer, "ProposedOffer")


def test_growth_agent_clamps_llm_violations(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Force MockLLMProvider to return an illegal 50% discount and verify GrowthAgent clamps it to 10% cap.

    This proves the core architectural invariant: 'LLM proposes, code disposes'.
    """
    # SKU-LAP-001: base_price_minor = 4,000,000 paise (₹40,000)
    # Policy discount_cap_pct = 0.10 -> max allowed discount is 400,000 paise (₹4,000)
    # Illegal LLM proposal: 50% discount = 2,000,000 paise (₹20,000)
    illegal_llm_output = LLMOutput(
        selected_sku_id="SKU-LAP-001",
        proposed_price_minor=2000000, # ₹20,000 (illegal!)
        discount_minor=2000000,       # 50% discount (illegal!)
        shipping_tier="express",
        rationale="Giving buyer 50% off to close the deal!",
    )

    mock_provider = MockLLMProvider(override_output=illegal_llm_output)
    agent = MerchantGrowthAgent(llm_provider=mock_provider)

    agent_input = AgentInput(
        session_id="sess_clamp_001",
        nl_utterance="I want a huge discount on Apex Ultrabook 14",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )

    offer = agent_agent = agent.score_and_propose(agent_input)

    # Expected clamped values:
    # max discount = 4,000,000 * 0.10 = 400,000 paise (₹4,000)
    # proposed price = 4,000,000 - 400,000 = 3,600,000 paise (₹36,000)
    assert offer.selected_sku_id == "SKU-LAP-001"
    assert offer.discount_minor == 400000
    assert offer.proposed_price_minor == 3600000
    assert offer.proposed_price_minor + offer.discount_minor == 4000000
    assert "Guardrail Enforcement" in offer.rationale
    assert "Discount clamped" in offer.rationale


def test_growth_agent_sku_hallucination_defense(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify that hallucinated SKU IDs from LLM are safely intercepted and replaced with valid catalog SKUs."""
    hallucinated_output = LLMOutput(
        selected_sku_id="SKU-NON-EXISTENT-999",
        proposed_price_minor=3500000,
        discount_minor=500000,
        shipping_tier="standard",
        rationale="Recommending an imaginary product",
    )
    mock_provider = MockLLMProvider(override_output=hallucinated_output)
    agent = MerchantGrowthAgent(llm_provider=mock_provider)

    agent_input = AgentInput(
        session_id="sess_hallucinate_002",
        nl_utterance="Show me laptops",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )

    offer = agent.score_and_propose(agent_input)
    assert offer.selected_sku_id in [p.sku_id for p in sample_catalog]
    assert "Guardrail Enforcement" in offer.rationale


def test_growth_agent_margin_floor_clamping(
    sample_catalog: list[Product],
) -> None:
    """Verify that price is clamped up if LLM proposes a price breaching the margin floor."""
    # Policy with 30% discount cap but 20% margin floor
    # SKU-LAP-001: Cost = ₹30,000 (3,000,000), Base Price = ₹40,000 (4,000,000)
    # 20% margin floor requires min price = 3,000,000 * 1.20 = 3,600,000 paise (₹36,000)
    # Max discount allowed by margin floor is 400,000 paise (₹4,000), even if discount cap is 30% (₹12,000)
    policy = MerchantPolicy(
        merchant_id="merch_margin",
        margin_floor_pct=0.20,
        discount_cap_pct=0.30,
        promotion_budget_minor=5000000,
    )

    llm_output = LLMOutput(
        selected_sku_id="SKU-LAP-001",
        proposed_price_minor=3200000, # ₹32,000 (violates ₹36,000 margin floor!)
        discount_minor=800000,        # ₹8,000 discount (within 30% cap, but violates margin floor!)
        shipping_tier="standard",
        rationale="Discount within 30% cap",
    )

    mock_provider = MockLLMProvider(override_output=llm_output)
    agent = MerchantGrowthAgent(llm_provider=mock_provider)

    agent_input = AgentInput(
        session_id="sess_margin_003",
        nl_utterance="Looking for laptop",
        available_catalog=sample_catalog,
        merchant_policy=policy,
    )

    offer = agent.score_and_propose(agent_input)
    assert offer.proposed_price_minor == 3600000  # clamped to margin floor
    assert offer.discount_minor == 400000          # clamped to base - margin floor
    assert offer.proposed_price_minor + offer.discount_minor == 4000000
