"""Buyer utility evaluator and simulator for multi-round negotiation."""

from __future__ import annotations

import hashlib
import random

from merchantos_core.contracts import (
    BuyerIntent,
    BuyerResponse,
    Product,
    ProposedOffer,
)


def _format_budget_k(budget_minor: int) -> str:
    """Format budget in thousands (k) notation, e.g. 4500000 paise -> '45k'."""
    budget_inr = budget_minor // 100
    if budget_inr >= 1000:
        return f"{budget_inr // 1000}k"
    return f"{budget_inr} INR"


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
            - Price Score: 1.0 if price <= budget. If price > budget, drops steeply:
                excess_ratio = (proposed_price - budget) / budget
                price_score = max(0.0, 1.0 - (excess_ratio * 2.0))
            - Delivery Score: 1.0 if express & delivery_sensitivity > 0.5;
                0.4 if standard & delivery_sensitivity > 0.5; else 0.8.
            - Product Fit: 1.0 if category matches intent, else 0.2.
            - Total Utility: (w_price * price_score) + (w_delivery * delivery_score) + (w_product * product_fit)
                where w_product = max(0.0, 1.0 - w_price - w_delivery).

        Decision Logic:
            - Bounded-rationality boundary: when utility is within 0.05 of acceptance threshold,
              a seeded deterministic RNG decides accept vs counter.
            - utility >= threshold + 0.05 -> accept
            - utility < threshold * 0.45 -> reject
            - otherwise -> counter with an informative counter-utterance.

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

        # 2. Calculate price score: steep decay when over budget
        if intent.budget_max_minor <= 0:
            price_score = 1.0 if offer.proposed_price_minor == 0 else 0.0
        elif offer.proposed_price_minor <= intent.budget_max_minor:
            price_score = 1.0
        else:
            excess_ratio = (offer.proposed_price_minor - intent.budget_max_minor) / intent.budget_max_minor
            price_score = max(0.0, 1.0 - (excess_ratio * 2.0))

        # 3. Calculate delivery score (penalizes standard shipping when delivery_sensitivity > 0.5)
        if intent.delivery_sensitivity > 0.5:
            delivery_score = 1.0 if offer.shipping_tier == "express" else 0.4
        else:
            delivery_score = 0.8

        # 4. Calculate product category fit (penalizes category mismatch to 0.2)
        prod_cat = product.category.strip().lower().rstrip("s")
        intent_cat = intent.category.strip().lower().rstrip("s")
        product_fit = 1.0 if (prod_cat == intent_cat or prod_cat in intent_cat or intent_cat in prod_cat) else 0.2

        # 5. Compute normalized weighted utility
        w_price = intent.price_sensitivity
        w_delivery = intent.delivery_sensitivity
        w_product = max(0.0, 1.0 - w_price - w_delivery)
        total_w = max(1e-6, w_price + w_delivery + w_product)

        utility = ((w_price * price_score) + (w_delivery * delivery_score) + (w_product * product_fit)) / total_w


        # 6. Apply bounded rationality & decision logic
        threshold = intent.acceptance_threshold
        diff = utility - threshold

        # Seeded deterministic RNG per session and offer to eliminate test flakes while simulating bounded rationality
        seed_str = f"{intent.session_id}_{offer.offer_id}_{offer.proposed_price_minor}_{offer.shipping_tier}"
        seed_val = int(hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:8], 16)
        rng = random.Random(seed_val)

        if abs(diff) <= 0.05:
            prob_accept = (diff + 0.05) / 0.10
            is_accepted = rng.random() < prob_accept
        else:
            is_accepted = utility >= threshold

        if is_accepted:
            return BuyerResponse(
                action="accept",
                reason=f"Offer utility ({utility:.3f}) meets acceptance threshold ({threshold:.3f}).",
                counter_utterance=None,
            )
        elif utility < (threshold * 0.45):
            return BuyerResponse(
                action="reject",
                reason=f"Offer utility ({utility:.3f}) is below rejection floor ({threshold * 0.45:.3f}).",
                counter_utterance=None,
            )
        else:
            # Generate informative counter-utterance
            budget_k = _format_budget_k(intent.budget_max_minor)
            if price_score < 0.6:
                counter_msg = f"That's over my budget, I can do around {budget_k} max"
            elif delivery_score < 0.5:
                counter_msg = "I really need faster delivery, can you do express?"
            elif product_fit < 0.5:
                counter_msg = f"That's not quite what I'm looking for, I need a {intent.category} specifically"
            else:
                counter_msg = "Can you sharpen the offer a bit?"

            return BuyerResponse(
                action="counter",
                reason=f"Offer utility ({utility:.3f}) is within negotiation range (threshold: {threshold:.3f}).",
                counter_utterance=counter_msg,
            )
