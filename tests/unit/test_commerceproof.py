"""Unit tests for CommerceProof Deterministic Control Layer."""

from __future__ import annotations

import pytest

from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.contracts import (
    CheckoutLineItem,
    CheckoutSnapshot,
    CumulativeLedger,
    InventoryRecord,
    InventoryState,
    MerchantPolicy,
    PolicyCheck,
    Product,
    ProposedOffer,
)


@pytest.fixture
def sample_catalog() -> list[Product]:
    return [
        Product(
            sku_id="SKU-HEADPHONES-001",
            name="Noise-Canceling Wireless Headphones",
            category="Audio",
            cost_minor=100000,  # ₹1000.00
            base_price_minor=150000,  # ₹1500.00
            inventory_count=20,
        ),
        Product(
            sku_id="SKU-WATCH-002",
            name="Smart Fitness Watch",
            category="Wearables",
            cost_minor=200000,  # ₹2000.00
            base_price_minor=300000,  # ₹3000.00
            inventory_count=5,
        ),
    ]


@pytest.fixture
def sample_policy() -> MerchantPolicy:
    return MerchantPolicy(
        merchant_id="merchant_test_01",
        margin_floor_pct=0.20,  # 20% margin floor above cost
        discount_cap_pct=0.20,  # 20% max discount off base price
        promotion_budget_minor=500000,  # ₹5000.00
    )


@pytest.fixture
def sample_inventory() -> InventoryState:
    return InventoryState(
        records=[
            InventoryRecord(sku_id="SKU-HEADPHONES-001", available_count=15),
            InventoryRecord(sku_id="SKU-WATCH-002", available_count=5),
        ]
    )


@pytest.fixture
def sample_ledger() -> CumulativeLedger:
    return CumulativeLedger(
        merchant_id="merchant_test_01",
        total_promotion_budget_minor=500000,
        total_discount_minor_used=100000,  # Remaining budget: 400000 (₹4000)
    )


def test_commerceproof_executes_valid_offer(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
    sample_ledger: CumulativeLedger,
) -> None:
    """A perfectly valid offer passes all checks, returns EXECUTE, and generates a valid final_state_hash."""
    engine = CommerceProof()
    # Cost = 100000 -> Min allowed price = 120000
    # Base price = 150000 -> Max discount = 30000 -> Min price = 120000
    # Offer: price = 135000 (discount = 15000)
    offer = ProposedOffer(
        offer_id="off_valid_001",
        session_id="sess_001",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=135000,
        discount_minor=15000,
        shipping_tier="standard",
        rationale="Standard 10% discount offered.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "EXECUTE"
    assert len(decision.violations) == 0
    assert len(decision.repairs) == 0
    assert decision.original_offer_id == "off_valid_001"
    assert decision.final_offer is not None
    assert decision.final_offer.proposed_price_minor == 135000
    assert decision.final_offer.discount_minor == 15000
    assert decision.final_state_hash is not None
    assert len(decision.final_state_hash) == 64  # SHA256 hex string

    # Verify all checks passed
    assert len(decision.checks) == 5
    for check in decision.checks:
        assert check.status == "pass"


def test_commerceproof_repairs_margin_violation(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
    sample_ledger: CumulativeLedger,
) -> None:
    """Force an offer below the margin floor. Assert action is REPAIR, the price is clamped exactly to the margin floor, and the hash is generated."""
    engine = CommerceProof()
    # Cost = 100000 -> Min allowed price = 120000 (100000 * 1.20)
    # Offer proposes price 110000 (violation: below margin floor 120000)
    offer = ProposedOffer(
        offer_id="off_margin_viol_001",
        session_id="sess_002",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=110000,
        discount_minor=40000,
        shipping_tier="express",
        rationale="Aggressive deal proposed by agent.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "REPAIR"
    assert len(decision.violations) >= 1
    assert len(decision.repairs) >= 1
    assert decision.final_offer is not None
    assert decision.final_offer.proposed_price_minor == 120000
    assert decision.final_offer.discount_minor == 30000
    assert "[CommerceProof Repaired:" in decision.final_offer.rationale
    assert decision.final_state_hash is not None
    assert len(decision.final_state_hash) == 64


def test_commerceproof_repairs_discount_cap_violation(
    sample_catalog: list[Product],
    sample_inventory: InventoryState,
    sample_ledger: CumulativeLedger,
) -> None:
    """Force an offer above the discount cap. Assert action is REPAIR and discount is clamped."""
    engine = CommerceProof()
    # Base price = 150000, policy discount cap = 10% (max discount = 15000)
    strict_policy = MerchantPolicy(
        merchant_id="merchant_test_01",
        margin_floor_pct=0.10,
        discount_cap_pct=0.10,
        promotion_budget_minor=500000,
    )
    # Offer proposes discount 25000 (exceeds cap 15000)
    offer = ProposedOffer(
        offer_id="off_disc_viol_001",
        session_id="sess_003",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=125000,
        discount_minor=25000,
        shipping_tier="standard",
        rationale="High discount offered.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=strict_policy,
        inventory=sample_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "REPAIR"
    assert len(decision.violations) >= 1
    assert any("discount cap" in r.lower() for r in decision.repairs)
    assert decision.final_offer is not None
    assert decision.final_offer.discount_minor == 15000
    assert decision.final_offer.proposed_price_minor == 135000
    assert decision.final_state_hash is not None


def test_commerceproof_blocks_out_of_stock(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_ledger: CumulativeLedger,
) -> None:
    """Set inventory to 0. Assert action is BLOCK, final_offer is None, and final_state_hash is None."""
    engine = CommerceProof()
    empty_inventory = InventoryState(
        records=[
            InventoryRecord(sku_id="SKU-HEADPHONES-001", available_count=0),
            InventoryRecord(sku_id="SKU-WATCH-002", available_count=5),
        ]
    )
    offer = ProposedOffer(
        offer_id="off_oos_001",
        session_id="sess_004",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=135000,
        discount_minor=15000,
        shipping_tier="standard",
        rationale="Offer on out of stock item.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=empty_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "BLOCK"
    assert decision.final_offer is None
    assert decision.final_state_hash is None
    assert any("out of stock" in v.lower() for v in decision.violations)
    assert any(c.check_name == "inventory_availability" and c.status == "fail" for c in decision.checks)


def test_commerceproof_blocks_cumulative_budget_exceeded(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
) -> None:
    """Set total_discount_minor_used equal to total_promotion_budget_minor. Assert action is BLOCK."""
    engine = CommerceProof()
    exhausted_ledger = CumulativeLedger(
        merchant_id="merchant_test_01",
        total_promotion_budget_minor=50000,
        total_discount_minor_used=50000,  # 0 remaining
    )
    offer = ProposedOffer(
        offer_id="off_budget_exhaust_001",
        session_id="sess_005",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=135000,
        discount_minor=15000,
        shipping_tier="standard",
        rationale="Discount when budget exhausted.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=exhausted_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "BLOCK"
    assert decision.final_offer is None
    assert decision.final_state_hash is None
    assert any("budget" in v.lower() for v in decision.violations)
    assert any(c.check_name == "promotion_budget" and c.status == "fail" for c in decision.checks)


def test_commerceproof_repairs_partial_budget_remaining(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
) -> None:
    """Set remaining budget to less than the offered discount. Assert action is REPAIR and discount is clamped to the exact remaining budget."""
    engine = CommerceProof()
    # Total budget = 50000, used = 42000 -> Remaining = 8000
    tight_ledger = CumulativeLedger(
        merchant_id="merchant_test_01",
        total_promotion_budget_minor=50000,
        total_discount_minor_used=42000,
    )
    # Offer proposes discount 15000 (exceeds remaining budget 8000)
    offer = ProposedOffer(
        offer_id="off_partial_budget_001",
        session_id="sess_006",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=135000,
        discount_minor=15000,
        shipping_tier="standard",
        rationale="Discount exceeding remaining budget.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=tight_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "REPAIR"
    assert decision.final_offer is not None
    assert decision.final_offer.discount_minor == 8000
    assert decision.final_offer.proposed_price_minor == 142000  # 150000 - 8000
    assert decision.final_state_hash is not None
    assert any("remaining budget" in r.lower() for r in decision.repairs)


def test_commerceproof_hash_mismatches_on_tampering(
    sample_catalog: list[Product],
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
    sample_ledger: CumulativeLedger,
) -> None:
    """Prove that if a single paise is changed in the final offer after the decision is made, the CheckoutSnapshot hash changes, proving cryptographic binding works."""
    engine = CommerceProof()
    offer = ProposedOffer(
        offer_id="off_tamper_001",
        session_id="sess_tamper_001",
        selected_sku_id="SKU-HEADPHONES-001",
        proposed_price_minor=135000,
        discount_minor=15000,
        shipping_tier="standard",
        rationale="Legitimate offer before tampering.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "EXECUTE"
    original_hash = decision.final_state_hash
    assert original_hash is not None

    # Construct tampered snapshot by 1 paise (135001 instead of 135000)
    tampered_snapshot = CheckoutSnapshot(
        session_id=offer.session_id,
        merchant_id=sample_policy.merchant_id,
        currency="INR",
        amount_minor=135001,
        line_items=[
            CheckoutLineItem(
                sku_id="SKU-HEADPHONES-001",
                name="Noise-Canceling Wireless Headphones",
                quantity=1,
                unit_amount_minor=135001,
                line_total_minor=135001,
            )
        ],
    )
    tampered_hash = tampered_snapshot.compute_content_hash()

    assert tampered_hash != original_hash


def test_commerceproof_blocks_unlisted_sku(
    sample_policy: MerchantPolicy,
    sample_inventory: InventoryState,
    sample_ledger: CumulativeLedger,
    sample_catalog: list[Product],
) -> None:
    """Offer referencing non-existent SKU is immediately blocked."""
    engine = CommerceProof()
    offer = ProposedOffer(
        offer_id="off_ghost_001",
        session_id="sess_ghost",
        selected_sku_id="NON-EXISTENT-SKU",
        proposed_price_minor=50000,
        discount_minor=10000,
        shipping_tier="standard",
        rationale="Ghost SKU offer.",
    )

    decision = engine.evaluate(
        offer=offer,
        policy=sample_policy,
        inventory=sample_inventory,
        ledger=sample_ledger,
        catalog=sample_catalog,
    )

    assert decision.action == "BLOCK"
    assert decision.final_offer is None
    assert decision.final_state_hash is None
    assert any("does not exist" in v.lower() for v in decision.violations)


def test_commerceproof_contract_invariants() -> None:
    """Ensure strict validation and extra=forbid on new contracts."""
    check = PolicyCheck(check_name="margin_check", status="pass", message="OK")
    assert check.status == "pass"

    with pytest.raises(Exception):
        PolicyCheck(check_name="test", status="invalid_status", message="fail")  # type: ignore[arg-type]

    with pytest.raises(Exception):
        InventoryRecord(sku_id="SKU1", available_count=-1)

    with pytest.raises(Exception):
        CumulativeLedger(
            merchant_id="M1",
            total_promotion_budget_minor=-10,
            total_discount_minor_used=0,
        )
