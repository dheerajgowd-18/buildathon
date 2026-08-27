"""Unit tests for RulesBaselineAgent deterministic signal extraction and commercial offer logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.contracts import (
    AgentInput,
    MerchantPolicy,
    Product,
    SimulatedScenario,
)


@pytest.fixture
def agent() -> RulesBaselineAgent:
    return RulesBaselineAgent()


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
            cost_minor=4500000,
            base_price_minor=6000000,
            inventory_count=5,
        ),
        Product(
            sku_id="SKU-SMA-001",
            name="NovaPhone 12 5G",
            category="smartphones",
            cost_minor=2000000,
            base_price_minor=2500000,
            inventory_count=15,
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


def test_signal_extraction_budget_parsing(agent: RulesBaselineAgent) -> None:
    """Verify deterministic budget parsing across 'k', currency symbols, and text patterns."""
    assert agent.extract_signals("Looking for a laptop under 60k.").estimated_budget_minor == 6000000
    assert agent.extract_signals("Need a phone under ₹50,000 now.").estimated_budget_minor == 5000000
    assert agent.extract_signals("Looking to buy a laptop with budget around 41k.").estimated_budget_minor == 4100000
    assert agent.extract_signals("Need a laptop with budget 50k.").estimated_budget_minor == 5000000
    assert agent.extract_signals("Interested in a device around ₹60,000.").estimated_budget_minor == 6000000
    assert agent.extract_signals("Looking for a laptop under 1 lakh.").estimated_budget_minor == 10000000
    assert agent.extract_signals("Looking for a premium laptop with great build, budget is open.").estimated_budget_minor is None


def test_signal_extraction_urgency(agent: RulesBaselineAgent) -> None:
    """Verify deterministic mapping of urgency keywords to low, medium, and high."""
    assert agent.extract_signals("Need a laptop, need it tomorrow.").urgency_level == "high"
    assert agent.extract_signals("urgent requirement, looking for fast shipping").urgency_level == "high"
    assert agent.extract_signals("need it delivered within 1 days").urgency_level == "high"
    assert agent.extract_signals("standard delivery is fine, no hurry").urgency_level == "low"
    assert agent.extract_signals("delivery timing is flexible").urgency_level == "low"
    assert agent.extract_signals("standard shipping is okay").urgency_level == "medium"
    assert agent.extract_signals("looking for a laptop in the ₹50,000 range").urgency_level == "medium"


def test_signal_extraction_category(agent: RulesBaselineAgent) -> None:
    """Verify deterministic category identification and synonym resolution."""
    assert agent.extract_signals("Looking for a laptop under 60k.").estimated_category == "laptops"
    assert agent.extract_signals("Need a fast smartphone for gaming.").estimated_category == "smartphones"
    assert agent.extract_signals("Looking for a good audio device with ANC.").estimated_category == "audio"
    assert agent.extract_signals("Need a tablet with pen support.").estimated_category == "tablets"
    assert agent.extract_signals("Looking for a smartwatch with heart rate sensor.").estimated_category == "smartwatches"
    assert agent.extract_signals("Need a tech accessory for my desk.").estimated_category == "accessories"
    assert agent.extract_signals("Looking for a drone under 20k.").estimated_category is None


def test_rules_agent_deterministic(
    agent: RulesBaselineAgent,
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify same AgentInput yields the exact same ProposedOffer across multiple runs."""
    agent_input = AgentInput(
        session_id="sess_det_01",
        nl_utterance="Looking for a laptop under ₹45,000 with express delivery.",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )

    offer_1 = agent.score_and_propose(agent_input)
    offer_2 = agent.score_and_propose(agent_input)

    assert offer_1.model_dump() == offer_2.model_dump()
    assert offer_1.selected_sku_id == "SKU-LAP-001"
    assert offer_1.shipping_tier == "express"


def test_rules_agent_respects_discount_cap(agent: RulesBaselineAgent) -> None:
    """Verify agent caps discount at merchant_policy.discount_cap_pct when buyer budget is 50% lower."""
    item = Product(
        sku_id="SKU-TEST-001",
        name="Test Item",
        category="laptops",
        cost_minor=4000000,
        base_price_minor=10000000,  # 1,00,000 INR
        inventory_count=10,
    )
    policy = MerchantPolicy(
        merchant_id="merch_test",
        margin_floor_pct=0.10,
        discount_cap_pct=0.10,  # Strict 10% discount cap
        promotion_budget_minor=5000000,
    )
    # Buyer budget requires 50% discount (50k INR vs 100k INR base price)
    agent_input = AgentInput(
        session_id="sess_cap_test",
        nl_utterance="Looking for a laptop under 50k.",
        available_catalog=[item],
        merchant_policy=policy,
    )

    offer = agent.score_and_propose(agent_input)

    expected_max_discount = int(10000000 * 0.10)  # 10,000 INR (1,000,000 paise)
    assert offer.discount_minor == expected_max_discount
    assert offer.proposed_price_minor == 10000000 - expected_max_discount
    assert offer.proposed_price_minor == 9000000


def test_rules_agent_respects_margin_floor(agent: RulesBaselineAgent) -> None:
    """Verify agent never proposes a price below cost_minor * (1 + margin_floor_pct) even with extremely low budget."""
    cost_minor = 8000000  # 80,000 INR
    base_price_minor = 10000000  # 100,000 INR
    item = Product(
        sku_id="SKU-MARGIN-001",
        name="High Cost Laptop",
        category="laptops",
        cost_minor=cost_minor,
        base_price_minor=base_price_minor,
        inventory_count=5,
    )
    policy = MerchantPolicy(
        merchant_id="merch_test",
        margin_floor_pct=0.15,  # Requires minimum price of 80,000 * 1.15 = 92,000 INR
        discount_cap_pct=0.30,  # Cap would allow up to 30,000 INR discount
        promotion_budget_minor=5000000,
    )
    # Buyer requests extremely low budget (e.g. 10k INR)
    agent_input = AgentInput(
        session_id="sess_margin_test",
        nl_utterance="Need a laptop under 10k.",
        available_catalog=[item],
        merchant_policy=policy,
    )

    offer = agent.score_and_propose(agent_input)

    min_required_price = int(cost_minor * (1.0 + policy.margin_floor_pct))  # 9,200,000 paise
    assert offer.proposed_price_minor >= min_required_price
    assert offer.proposed_price_minor == min_required_price
    assert offer.discount_minor == base_price_minor - min_required_price
    assert offer.discount_minor == 800000  # 8,000 INR discount, not 30,000


def test_rules_agent_fallback_selection(
    agent: RulesBaselineAgent,
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify agent falls back to cheapest item in catalog when utterance category is not found."""
    agent_input = AgentInput(
        session_id="sess_fallback_01",
        nl_utterance="Looking for a professional drone camera.",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )

    offer = agent.score_and_propose(agent_input)

    # Cheapest item in sample_catalog is NovaPhone 12 5G (base_price_minor=2,500,000)
    assert offer.selected_sku_id == "SKU-SMA-001"
    assert "No category match" in offer.rationale


def test_rules_agent_all_dev_scenarios(agent: RulesBaselineAgent) -> None:
    """Verify that RulesBaselineAgent successfully executes against all 100 dev scenarios without error or violation."""
    dev_path = Path(__file__).resolve().parent.parent.parent / "data" / "dev_scenarios.jsonl"
    if not dev_path.exists():
        pytest.skip("dev_scenarios.jsonl not found")

    with dev_path.open("r", encoding="utf-8") as f:
        scenarios = [SimulatedScenario.model_validate_json(line) for line in f if line.strip()]

    assert len(scenarios) == 100

    for sc in scenarios:
        # Create strict AgentInput (WITHOUT intent or scenario_id)
        agent_input = AgentInput(
            session_id=sc.intent.session_id,
            nl_utterance=sc.nl_utterance,
            available_catalog=sc.available_catalog,
            merchant_policy=sc.merchant_policy,
        )

        offer = agent.score_and_propose(agent_input)

        assert offer.session_id == sc.intent.session_id
        assert offer.selected_sku_id in [p.sku_id for p in sc.available_catalog]
        assert offer.proposed_price_minor >= 0
        assert offer.discount_minor >= 0
        assert offer.shipping_tier in ("standard", "express")

        selected_product = next(p for p in sc.available_catalog if p.sku_id == offer.selected_sku_id)
        assert offer.proposed_price_minor + offer.discount_minor == selected_product.base_price_minor

        # Mathematical policy compliance checks
        max_allowed_discount = int(selected_product.base_price_minor * sc.merchant_policy.discount_cap_pct)
        assert offer.discount_minor <= max_allowed_discount

        min_margin_price = int(selected_product.cost_minor * (1.0 + sc.merchant_policy.margin_floor_pct))
        assert offer.proposed_price_minor >= min_margin_price
