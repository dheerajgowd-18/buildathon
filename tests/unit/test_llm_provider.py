"""Unit tests for LLM provider abstraction and MockLLMProvider."""

from __future__ import annotations

import pytest
from merchantos_core.contracts import (
    AgentInput,
    LLMOutput,
    MerchantPolicy,
    Product,
)
from merchantos_core.llm.prompts import build_merchant_prompt
from merchantos_core.llm.provider import AbstractLLMProvider, MockLLMProvider


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


def test_mock_llm_deterministic(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify that MockLLMProvider produces identical LLMOutput for identical inputs."""
    agent_input = AgentInput(
        session_id="sess_det_101",
        nl_utterance="I want a laptop under 35k urgently tomorrow",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )
    system_prompt, user_prompt = build_merchant_prompt(agent_input)

    provider = MockLLMProvider()
    output_1 = provider.generate_offer_proposal(system_prompt, user_prompt)
    output_2 = provider.generate_offer_proposal(system_prompt, user_prompt)

    assert isinstance(output_1, LLMOutput)
    assert output_1 == output_2
    assert output_1.selected_sku_id == "SKU-LAP-001"
    assert output_1.shipping_tier == "express"


def test_mock_llm_respects_bounds(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
) -> None:
    """Verify that default MockLLMProvider generates offers within merchant policy bounds."""
    # Buyer asks for ₹10,000 (well below cost of ₹30,000 and base price ₹40,000)
    agent_input = AgentInput(
        session_id="sess_bounds_102",
        nl_utterance="I want a laptop for ₹10,000",
        available_catalog=sample_catalog,
        merchant_policy=sample_policy,
    )
    system_prompt, user_prompt = build_merchant_prompt(agent_input)

    provider = MockLLMProvider()
    output = provider.generate_offer_proposal(system_prompt, user_prompt)

    product = next(p for p in sample_catalog if p.sku_id == output.selected_sku_id)
    max_discount_cap = int(product.base_price_minor * sample_policy.discount_cap_pct)
    min_margin_price = int(product.cost_minor * (1.0 + sample_policy.margin_floor_pct))

    assert output.discount_minor <= max_discount_cap
    assert output.proposed_price_minor >= min_margin_price
    assert output.proposed_price_minor + output.discount_minor == product.base_price_minor


def test_mock_llm_override_hook() -> None:
    """Verify that MockLLMProvider supports custom override outputs for testing."""
    canned = LLMOutput(
        selected_sku_id="SKU-CUSTOM",
        proposed_price_minor=2000000,
        discount_minor=2000000,
        shipping_tier="standard",
        rationale="Canned testing response",
    )
    provider = MockLLMProvider(override_output=canned)
    result = provider.generate_offer_proposal("sys", "user")
    assert result == canned
