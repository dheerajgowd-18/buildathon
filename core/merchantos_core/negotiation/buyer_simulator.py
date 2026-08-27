"""Buyer utility evaluator and simulator for multi-round negotiation."""

from __future__ import annotations

from merchantos_core.contracts import (
    BuyerIntent,
    BuyerResponse,
    Product,
    ProposedOffer,
)


class BuyerSimulator:
    """Simulates buyer evaluation using a weighted multi-attribute utility model.

    Evaluates proposed offers against ground-truth buyer intent (budget, category,
    delivery sensitivity, and price sensitivity).
    """

    def evaluate_offer(
        self,
        offer: ProposedOffer,
        intent: BuyerIntent,
        catalog: list[Product],
    ) -> BuyerResponse:
        """Evaluate a merchant offer against buyer preferences and produce an action.

        Utility Computation:
            - Price Score: 1.0 if price <= budget, decays linearly to 0.0 at 2x budget.
            - Delivery Score: 1.0 if express & delivery_sensitivity > 0.5, else 0.8.
            - Product Fit: 1.0 if category matches intent, else 0.5.
            - Total Utility: w_price * price_score + w_delivery * delivery_score + w_product * product_fit
              where w_product = max(0.0, 1.0 - w_price - w_delivery).

        Decision Thresholds:
            - utility >= intent.acceptance_threshold -> accept
            - utility < intent.acceptance_threshold * 0.5 -> reject
            - otherwise -> counter

        Args:
            offer: Merchant's proposed commercial offer.
            intent: Ground truth buyer intent.
            catalog: Available product catalog.

        Returns:
            BuyerResponse with action ("accept" | "reject" | "counter") and rationale.
        """
        # 1. Locate selected product in catalog
        matching_products = [p for p in catalog if p.sku_id == offer.selected_sku_id]
        if not matching_products:
            return BuyerResponse(
                action="reject",
                reason=f"Offered SKU {offer.selected_sku_id} was not found in the catalog.",
                counter_utterance=None,
            )
        product = matching_products[0]

        # 2. Calculate price score: 1.0 at or below budget, 0.0 at 2x budget
        if intent.budget_max_minor <= 0:
            price_score = 1.0 if offer.proposed_price_minor == 0 else 0.0
        elif offer.proposed_price_minor <= intent.budget_max_minor:
            price_score = 1.0
        else:
            excess = offer.proposed_price_minor - intent.budget_max_minor
            price_score = max(0.0, 1.0 - (excess / intent.budget_max_minor))

        # 3. Calculate delivery score
        if offer.shipping_tier == "express" and intent.delivery_sensitivity > 0.5:
            delivery_score = 1.0
        else:
            delivery_score = 0.8

        # 4. Calculate product category fit
        prod_cat = product.category.strip().lower().rstrip("s")
        intent_cat = intent.category.strip().lower().rstrip("s")
        product_fit = 1.0 if (prod_cat == intent_cat or prod_cat in intent_cat or intent_cat in prod_cat) else 0.5

        # 5. Compute weighted utility
        w_price = intent.price_sensitivity
        w_delivery = intent.delivery_sensitivity
        w_product = max(0.0, 1.0 - w_price - w_delivery)

        utility = (w_price * price_score) + (w_delivery * delivery_score) + (w_product * product_fit)

        # 6. Apply decision logic
        if utility >= intent.acceptance_threshold:
            return BuyerResponse(
                action="accept",
                reason=f"Offer utility ({utility:.3f}) meets acceptance threshold ({intent.acceptance_threshold:.3f}).",
                counter_utterance=None,
            )
        elif utility < (intent.acceptance_threshold * 0.5):
            return BuyerResponse(
                action="reject",
                reason=f"Offer utility ({utility:.3f}) is below rejection floor ({intent.acceptance_threshold * 0.5:.3f}).",
                counter_utterance=None,
            )
        else:
            # Construct a deterministic counter utterance
            if price_score < 0.8:
                counter_msg = "That price is still too high, I need it closer to my budget."
            elif delivery_score < 1.0 and intent.delivery_sensitivity > 0.5:
                counter_msg = "Can you offer faster express delivery for this order?"
            else:
                counter_msg = "I am interested, but could you improve the discount slightly?"

            return BuyerResponse(
                action="counter",
                reason=f"Offer utility ({utility:.3f}) is within negotiation range (threshold: {intent.acceptance_threshold:.3f}).",
                counter_utterance=counter_msg,
            )
