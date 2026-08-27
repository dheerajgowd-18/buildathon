"""Unit tests for simulator modules (marketplace, buyers, nlg)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from merchantos_core.contracts import (
    BuyerIntent,
    MerchantPolicy,
    Product,
    SimulatedScenario,
)
from merchantos_simulator.buyers import generate_buyer_intent
from merchantos_simulator.marketplace import generate_catalog
from merchantos_simulator.nlg import generate_lossy_utterance


def test_marketplace_deterministic() -> None:
    """Same seed and category must produce identical catalog of products."""
    catalog_1 = generate_catalog(seed=1042, category="laptops", sku_count=5)
    catalog_2 = generate_catalog(seed=1042, category="laptops", sku_count=5)

    assert len(catalog_1) == 5
    assert len(catalog_2) == 5
    for p1, p2 in zip(catalog_1, catalog_2):
        assert p1.sku_id == p2.sku_id
        assert p1.name == p2.name
        assert p1.cost_minor == p2.cost_minor
        assert p1.base_price_minor == p2.base_price_minor
        assert p1.inventory_count == p2.inventory_count


def test_marketplace_margins() -> None:
    """All products generated must satisfy base_price_minor > cost_minor."""
    categories = ["laptops", "smartphones", "audio", "tablets", "smartwatches", "accessories"]
    for cat in categories:
        for seed in [100, 250, 999, 12345]:
            catalog = generate_catalog(seed=seed, category=cat, sku_count=8)
            for product in catalog:
                assert product.base_price_minor > product.cost_minor
                assert product.cost_minor >= 0
                assert product.inventory_count >= 0


def test_product_price_validation() -> None:
    """Product model validator must reject base_price_minor < cost_minor."""
    with pytest.raises(ValidationError) as exc_info:
        Product(
            sku_id="SKU-TEST-01",
            name="Invalid Product",
            category="laptops",
            cost_minor=50000,
            base_price_minor=40000,
            inventory_count=10,
        )
    assert "base_price_minor" in str(exc_info.value)


def test_buyer_intent_deterministic() -> None:
    """Same seed and parameters must produce identical BuyerIntent."""
    intent_1 = generate_buyer_intent(seed=2048, category="smartphones", divergence=0.4)
    intent_2 = generate_buyer_intent(seed=2048, category="smartphones", divergence=0.4)

    assert intent_1.session_id == intent_2.session_id
    assert intent_1.budget_max_minor == intent_2.budget_max_minor
    assert intent_1.delivery_days_max == intent_2.delivery_days_max
    assert intent_1.priority == intent_2.priority
    assert intent_1.hard_exclusions == intent_2.hard_exclusions
    assert intent_1.price_sensitivity == intent_2.price_sensitivity
    assert intent_1.delivery_sensitivity == intent_2.delivery_sensitivity
    assert intent_1.acceptance_threshold == intent_2.acceptance_threshold
    assert intent_1.stated_vs_true_divergence == 0.4


def test_nlg_divergence_behavior() -> None:
    """High divergence produces text that obscures or contradicts underlying sensitivities."""
    # High price sensitivity with high divergence
    intent_high_price_sens = BuyerIntent(
        session_id="sess_test_high_div",
        category="laptops",
        budget_max_minor=6000000,
        delivery_days_max=1,
        priority=["battery"],
        hard_exclusions=[],
        price_sensitivity=0.95,
        delivery_sensitivity=0.90,
        acceptance_threshold=0.85,
        stated_vs_true_divergence=0.8,
    )
    utterance_high = generate_lossy_utterance(intent=intent_high_price_sens, seed=42)
    # The high divergence text should state budget is flexible or not an issue, contradicting 0.95 sensitivity
    assert any(
        phrase in utterance_high.lower()
        for phrase in ["flexible", "stretch", "price is not an issue", "open", "premium"]
    )
    # And delivery is relaxed, contradicting 0.90 delivery sensitivity
    assert any(
        phrase in utterance_high.lower()
        for phrase in ["fine", "wait", "flexible", "timing"]
    )

    # Low divergence reflects intent faithfully
    intent_low_div = BuyerIntent(
        session_id="sess_test_low_div",
        category="laptops",
        budget_max_minor=6000000,
        delivery_days_max=2,
        priority=["battery"],
        hard_exclusions=["refurbished"],
        price_sensitivity=0.95,
        delivery_sensitivity=0.90,
        acceptance_threshold=0.85,
        stated_vs_true_divergence=0.1,
    )
    utterance_low = generate_lossy_utterance(intent=intent_low_div, seed=42)
    assert "₹60,000" in utterance_low
    assert "battery" in utterance_low.lower()
    assert "2 days" in utterance_low.lower()
    assert "refurbished" in utterance_low.lower()


def test_extra_forbid_on_new_contracts() -> None:
    """All Phase 02 contracts must strictly forbid extra fields."""
    with pytest.raises(ValidationError):
        Product(
            sku_id="SKU-1",
            name="Test",
            category="audio",
            cost_minor=1000,
            base_price_minor=2000,
            inventory_count=5,
            extra_field="invalid",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        MerchantPolicy(
            merchant_id="merch_1",
            margin_floor_pct=0.15,
            discount_cap_pct=0.20,
            promotion_budget_minor=10000,
            extra_field="invalid",  # type: ignore[call-arg]
        )

    with pytest.raises(ValidationError):
        BuyerIntent(
            session_id="sess_1",
            category="laptops",
            budget_max_minor=5000000,
            delivery_days_max=3,
            price_sensitivity=0.5,
            delivery_sensitivity=0.5,
            acceptance_threshold=0.8,
            stated_vs_true_divergence=0.1,
            extra_field="invalid",  # type: ignore[call-arg]
        )


def test_simulated_scenario_roundtrip() -> None:
    """SimulatedScenario serializes to JSON and deserializes without loss."""
    catalog = generate_catalog(seed=777, category="audio", sku_count=3)
    intent = generate_buyer_intent(seed=777, category="audio", divergence=0.1)
    utterance = generate_lossy_utterance(intent=intent, seed=777)
    policy = MerchantPolicy(
        merchant_id="merch_001",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,
        promotion_budget_minor=5000000,
    )
    scenario = SimulatedScenario(
        scenario_id="test_001",
        intent=intent,
        nl_utterance=utterance,
        available_catalog=catalog,
        merchant_policy=policy,
    )
    serialized = scenario.model_dump_json()
    deserialized = SimulatedScenario.model_validate_json(serialized)
    assert deserialized.scenario_id == "test_001"
    assert deserialized.intent.session_id == intent.session_id
    assert len(deserialized.available_catalog) == 3
    assert deserialized.merchant_policy.merchant_id == "merch_001"
    assert deserialized.nl_utterance == utterance

