"""Unit tests for BuyerSimulator utility evaluation."""

from __future__ import annotations

import pytest
from merchantos_core.contracts import (
    BuyerIntent,
    Product,
    ProposedOffer,
)
from merchantos_core.negotiation.buyer_simulator import BuyerSimulator


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
    ]


@pytest.fixture
def base_intent() -> BuyerIntent:
    return BuyerIntent(
        session_id="sess_sim_01",
        category="laptops",
        budget_max_minor=4000000,     # ₹40,000 budget
        delivery_days_max=2,
        priority=["performance"],
        hard_exclusions=[],
        price_sensitivity=0.5,
        delivery_sensitivity=0.3,
        acceptance_threshold=0.75,
        stated_vs_true_divergence=0.0,
    )


def test_buyer_accepts_high_utility(
    sample_catalog: list[Product],
    base_intent: BuyerIntent,
) -> None:
    """Offer well within budget and matching shipping/category yields high utility -> ACCEPT."""
    # Proposed price ₹35,000 (well within budget ₹40,000), express shipping, matching category
    offer = ProposedOffer(
        offer_id="off_high_01",
        session_id="sess_sim_01",
        selected_sku_id="SKU-LAP-001",
        proposed_price_minor=3500000,
        discount_minor=500000,
        shipping_tier="express",
        rationale="Great deal on laptop",
    )

    simulator = BuyerSimulator()
    response = simulator.evaluate_offer(offer, base_intent, sample_catalog)

    # Price score = 1.0 (since 35k <= 40k)
    # Delivery score = 0.8 (since delivery_sensitivity = 0.3 <= 0.5)
    # Category fit = 1.0 (laptops == laptops)
    # w_price = 0.5, w_delivery = 0.3, w_prod = 0.2
    # utility = 0.5*1.0 + 0.3*0.8 + 0.2*1.0 = 0.5 + 0.24 + 0.2 = 0.94 >= 0.75 -> accept
    assert response.action == "accept"
    assert response.counter_utterance is None
    assert "meets acceptance threshold" in response.reason


def test_buyer_rejects_low_utility(
    sample_catalog: list[Product],
    base_intent: BuyerIntent,
) -> None:
    """Offer 2x budget and wrong attributes yields very low utility (< 0.5 * threshold) -> REJECT."""
    # Proposed price ₹80,000 (2x budget ₹40,000)
    offer = ProposedOffer(
        offer_id="off_low_02",
        session_id="sess_sim_01",
        selected_sku_id="SKU-LAP-001",
        proposed_price_minor=8000000,
        discount_minor=0,
        shipping_tier="standard",
        rationale="Full price offer",
    )

    # Acceptance threshold is 0.75 -> rejection floor is 0.375
    # Price score = 0.0 (at 2x budget)
    # Delivery score = 0.8
    # Category fit = 1.0
    # utility = 0.5*0.0 + 0.3*0.8 + 0.2*1.0 = 0.0 + 0.24 + 0.20 = 0.44 -> wait, 0.44 > 0.375!
    # Let's make price sensitivity higher (e.g. 0.8) or price 2.5x budget:
    price_sensitive_intent = base_intent.model_copy(
        update={"price_sensitivity": 0.8, "delivery_sensitivity": 0.1, "acceptance_threshold": 0.80}
    )
    # utility = 0.8*0.0 + 0.1*0.8 + 0.1*1.0 = 0.18 < 0.40 -> REJECT
    simulator = BuyerSimulator()
    response = simulator.evaluate_offer(offer, price_sensitive_intent, sample_catalog)

    assert response.action == "reject"
    assert response.counter_utterance is None
    assert "below rejection floor" in response.reason


def test_buyer_counters_medium_utility(
    sample_catalog: list[Product],
    base_intent: BuyerIntent,
) -> None:
    """Offer slightly above budget yields medium utility -> COUNTER."""
    # Budget is ₹40,000. Offer is ₹46,000 (1.15x budget).
    offer = ProposedOffer(
        offer_id="off_med_03",
        session_id="sess_sim_01",
        selected_sku_id="SKU-LAP-001",
        proposed_price_minor=4600000,
        discount_minor=0,
        shipping_tier="standard",
        rationale="Slightly over budget offer",
    )

    # Price score: 1.0 - (6,000 / 40,000) = 1.0 - 0.15 = 0.85
    # Delivery score: 0.8
    # Product fit: 1.0
    # Utility: 0.5*0.85 + 0.3*0.8 + 0.2*1.0 = 0.425 + 0.24 + 0.2 = 0.865
    # Let's adjust acceptance threshold to 0.90 (rejection floor 0.45):
    high_threshold_intent = base_intent.model_copy(
        update={"acceptance_threshold": 0.90}
    )
    # Utility 0.865 is between 0.45 and 0.90 -> COUNTER!
    simulator = BuyerSimulator()
    response = simulator.evaluate_offer(offer, high_threshold_intent, sample_catalog)

    assert response.action == "counter"
    assert response.counter_utterance is not None
    assert len(response.counter_utterance) > 0


def test_buyer_rejects_missing_product(
    base_intent: BuyerIntent,
) -> None:
    """Offer referencing a product not in the catalog is rejected."""
    offer = ProposedOffer(
        offer_id="off_none",
        session_id="sess_sim_01",
        selected_sku_id="SKU-UNKNOWN",
        proposed_price_minor=1000000,
        discount_minor=0,
        shipping_tier="standard",
        rationale="Unknown SKU",
    )
    simulator = BuyerSimulator()
    response = simulator.evaluate_offer(offer, base_intent, [])
    assert response.action == "reject"
