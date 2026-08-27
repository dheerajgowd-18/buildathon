"""Deterministic CommerceProof Control Layer for MerchantOS AI."""

from __future__ import annotations

import uuid

from merchantos_core.contracts import (
    CheckoutLineItem,
    CheckoutSnapshot,
    CommerceDecision,
    CumulativeLedger,
    InventoryState,
    MerchantPolicy,
    PolicyCheck,
    Product,
    ProposedOffer,
)


class CommerceProof:
    """
    Deterministic CommerceProof Control Layer.

    Guarantees:
    - Zero LLM authority to move money or execute invalid commercial terms.
    - Deterministic catalog validation, margin floor protection, discount cap clamping,
      inventory availability verification, and cumulative promotion budget tracking.
    - Cryptographic state binding via SHA256 checkout snapshots.
    """

    def evaluate(
        self,
        offer: ProposedOffer,
        policy: MerchantPolicy,
        inventory: InventoryState,
        ledger: CumulativeLedger,
        catalog: list[Product],
    ) -> CommerceDecision:
        """
        Evaluate a proposed commercial offer against merchant policy, inventory, and cumulative ledger.

        Returns a deterministic CommerceDecision (EXECUTE, REPAIR, or BLOCK) with cryptographic state binding.
        """
        decision_id = f"dec_{uuid.uuid4().hex}"
        violations: list[str] = []
        repairs: list[str] = []
        checks: list[PolicyCheck] = []

        # 1. Catalog & Cost Lookup
        product = next((p for p in catalog if p.sku_id == offer.selected_sku_id), None)
        if product is None:
            violation_msg = f"SKU {offer.selected_sku_id} does not exist in available catalog"
            violations.append(violation_msg)
            checks.append(
                PolicyCheck(
                    check_name="catalog_lookup",
                    status="fail",
                    message=violation_msg,
                )
            )
            return CommerceDecision(
                decision_id=decision_id,
                session_id=offer.session_id,
                action="BLOCK",
                violations=violations,
                repairs=repairs,
                checks=checks,
                original_offer_id=offer.offer_id,
                final_offer=None,
                final_state_hash=None,
            )

        checks.append(
            PolicyCheck(
                check_name="catalog_lookup",
                status="pass",
                message=f"SKU {product.sku_id} found in catalog",
            )
        )

        base_price_minor = product.base_price_minor
        cost_minor = product.cost_minor

        current_proposed_price = offer.proposed_price_minor
        current_discount = offer.discount_minor

        # 2. Margin Floor Check
        min_allowed_price = int(cost_minor * (1.0 + policy.margin_floor_pct))
        if current_proposed_price < min_allowed_price:
            violation_msg = (
                f"Proposed price {current_proposed_price} is below margin floor {min_allowed_price}"
            )
            violations.append(violation_msg)
            repaired_price = min_allowed_price
            repaired_discount = max(0, base_price_minor - repaired_price)
            repair_msg = (
                f"Clamped proposed price from {current_proposed_price} to margin floor {min_allowed_price} "
                f"(discount adjusted to {repaired_discount})"
            )
            repairs.append(repair_msg)
            current_proposed_price = repaired_price
            current_discount = repaired_discount
            checks.append(
                PolicyCheck(
                    check_name="margin_floor",
                    status="repaired",
                    message=repair_msg,
                )
            )
        else:
            checks.append(
                PolicyCheck(
                    check_name="margin_floor",
                    status="pass",
                    message=f"Proposed price {current_proposed_price} satisfies margin floor {min_allowed_price}",
                )
            )

        # 3. Discount Cap Check
        max_allowed_discount = int(base_price_minor * policy.discount_cap_pct)
        if current_discount > max_allowed_discount:
            violation_msg = (
                f"Proposed discount {current_discount} exceeds discount cap {max_allowed_discount}"
            )
            violations.append(violation_msg)
            repaired_discount = max_allowed_discount
            repaired_price = base_price_minor - repaired_discount
            repair_msg = (
                f"Clamped discount from {current_discount} to discount cap {max_allowed_discount} "
                f"(price adjusted to {repaired_price})"
            )
            repairs.append(repair_msg)
            current_discount = repaired_discount
            current_proposed_price = repaired_price
            checks.append(
                PolicyCheck(
                    check_name="discount_cap",
                    status="repaired",
                    message=repair_msg,
                )
            )
        else:
            checks.append(
                PolicyCheck(
                    check_name="discount_cap",
                    status="pass",
                    message=f"Proposed discount {current_discount} satisfies discount cap {max_allowed_discount}",
                )
            )

        # 4. Inventory Check
        inv_record = next((r for r in inventory.records if r.sku_id == offer.selected_sku_id), None)
        if inv_record is None or inv_record.available_count <= 0:
            count = 0 if inv_record is None else inv_record.available_count
            violation_msg = f"SKU {offer.selected_sku_id} is out of stock (available: {count})"
            violations.append(violation_msg)
            checks.append(
                PolicyCheck(
                    check_name="inventory_availability",
                    status="fail",
                    message=violation_msg,
                )
            )
            return CommerceDecision(
                decision_id=decision_id,
                session_id=offer.session_id,
                action="BLOCK",
                violations=violations,
                repairs=repairs,
                checks=checks,
                original_offer_id=offer.offer_id,
                final_offer=None,
                final_state_hash=None,
            )

        checks.append(
            PolicyCheck(
                check_name="inventory_availability",
                status="pass",
                message=f"SKU {offer.selected_sku_id} in stock (available: {inv_record.available_count})",
            )
        )

        # 5. Cumulative Promotion Budget Check
        remaining_budget = ledger.total_promotion_budget_minor - ledger.total_discount_minor_used
        if current_discount > remaining_budget:
            violation_msg = (
                f"Proposed discount {current_discount} exceeds remaining cumulative promotion budget {remaining_budget}"
            )
            violations.append(violation_msg)
            if remaining_budget <= 0:
                checks.append(
                    PolicyCheck(
                        check_name="promotion_budget",
                        status="fail",
                        message=f"Cumulative promotion budget exhausted (remaining: {remaining_budget})",
                    )
                )
                return CommerceDecision(
                    decision_id=decision_id,
                    session_id=offer.session_id,
                    action="BLOCK",
                    violations=violations,
                    repairs=repairs,
                    checks=checks,
                    original_offer_id=offer.offer_id,
                    final_offer=None,
                    final_state_hash=None,
                )
            else:
                repaired_discount = remaining_budget
                repaired_price = base_price_minor - repaired_discount
                repair_msg = (
                    f"Clamped discount from {current_discount} to remaining budget {remaining_budget} "
                    f"(price adjusted to {repaired_price})"
                )
                repairs.append(repair_msg)
                current_discount = repaired_discount
                current_proposed_price = repaired_price
                checks.append(
                    PolicyCheck(
                        check_name="promotion_budget",
                        status="repaired",
                        message=repair_msg,
                    )
                )
        else:
            checks.append(
                PolicyCheck(
                    check_name="promotion_budget",
                    status="pass",
                    message=f"Proposed discount {current_discount} within remaining budget {remaining_budget}",
                )
            )

        # 6. Resolution
        if repairs:
            action = "REPAIR"
            final_rationale = f"{offer.rationale} [CommerceProof Repaired: {'; '.join(repairs)}]"
            final_offer = ProposedOffer(
                offer_id=offer.offer_id,
                session_id=offer.session_id,
                selected_sku_id=offer.selected_sku_id,
                proposed_price_minor=current_proposed_price,
                discount_minor=current_discount,
                shipping_tier=offer.shipping_tier,
                rationale=final_rationale,
            )
        else:
            action = "EXECUTE"
            final_offer = offer

        # 7. Final State Binding (Crucial P0 Step)
        line_item = CheckoutLineItem(
            sku_id=product.sku_id,
            name=product.name,
            quantity=1,
            unit_amount_minor=final_offer.proposed_price_minor,
            line_total_minor=final_offer.proposed_price_minor,
        )
        snapshot = CheckoutSnapshot(
            session_id=offer.session_id,
            merchant_id=policy.merchant_id,
            currency="INR",
            amount_minor=final_offer.proposed_price_minor,
            line_items=[line_item],
        )
        final_state_hash = snapshot.compute_content_hash()

        return CommerceDecision(
            decision_id=decision_id,
            session_id=offer.session_id,
            action=action,
            violations=violations,
            repairs=repairs,
            checks=checks,
            original_offer_id=offer.offer_id,
            final_offer=final_offer,
            final_state_hash=final_state_hash,
        )
