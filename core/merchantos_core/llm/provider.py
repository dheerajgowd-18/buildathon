"""LLM Provider abstractions and deterministic Mock provider."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Callable, Literal

from merchantos_core.contracts import LLMOutput


class AbstractLLMProvider(ABC):
    """Abstract base class for LLM inference providers."""

    @abstractmethod
    def generate_offer_proposal(self, system_prompt: str, user_prompt: str) -> LLMOutput:
        """Generate a structured offer proposal matching the LLMOutput schema.

        Args:
            system_prompt: High-level instructions and output schema definition.
            user_prompt: Context including buyer utterance, catalog, and policy.

        Returns:
            Validated LLMOutput model.
        """
        ...


class MockLLMProvider(AbstractLLMProvider):
    """Deterministic Mock LLM provider for zero-cost, hermetic testing.

    Simulates an adaptive LLM agent that learns from multi-round negotiation
    dynamics: anchoring high on round 1, reading buyer counter-offers (budget reveals,
    delivery constraints, category corrections), and making calibrated concessions.
    """

    def __init__(
        self,
        override_output: LLMOutput | None = None,
        override_fn: Callable[[str, str], LLMOutput] | None = None,
    ) -> None:
        self.override_output = override_output
        self.override_fn = override_fn

    def generate_offer_proposal(self, system_prompt: str, user_prompt: str) -> LLMOutput:
        """Generate deterministic, adaptive LLMOutput from prompts."""
        if self.override_output is not None:
            return self.override_output

        if self.override_fn is not None:
            return self.override_fn(system_prompt, user_prompt)

        # 1. Parse catalog items from user prompt
        catalog_pattern = re.compile(
            r"- SKU:\s*([\w\-]+)\s*\|\s*Name:\s*([^|]+)\|\s*Category:\s*([\w\-]+)\s*\|\s*"
            r"Base Price:\s*₹[0-9\.,]+\s*\((\d+)\s*paise\)\s*\|\s*Cost:\s*₹[0-9\.,]+\s*\((\d+)\s*paise\)"
        )
        catalog_matches = catalog_pattern.findall(user_prompt)

        # 2. Parse policy from user prompt
        margin_floor_pct = 0.15
        discount_cap_pct = 0.20
        mf_match = re.search(r"Margin Floor:\s*(\d+(?:\.\d+)?)%", user_prompt)
        if mf_match:
            margin_floor_pct = float(mf_match.group(1)) / 100.0
        dc_match = re.search(r"Discount Cap:\s*(\d+(?:\.\d+)?)%", user_prompt)
        if dc_match:
            discount_cap_pct = float(dc_match.group(1)) / 100.0

        # 3. Parse buyer utterance and negotiation history
        utterance_match = re.search(r'BUYER UTTERANCE:\s*\n"([^"]+)"', user_prompt)
        initial_utterance = utterance_match.group(1) if utterance_match else user_prompt

        history_match = re.search(r'NEGOTIATION HISTORY:\s*\n(.*?)\n\nMERCHANT POLICY:', user_prompt, re.DOTALL)
        history_text = history_match.group(1) if history_match else ""

        # Determine current round number
        if "[Round 2]" in history_text:
            current_round = 3
        elif "[Round 1]" in history_text:
            current_round = 2
        else:
            current_round = 1

        # 4. Extract signals across all utterances (initial + counter history)
        combined_text = f"{initial_utterance} {history_text}"

        # Budget extraction
        budget_minor = None
        k_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", combined_text, re.IGNORECASE)
        if k_match:
            budget_minor = int(round(float(k_match.group(1)) * 1000 * 100))
        else:
            lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b", combined_text, re.IGNORECASE)
            if lakh_match:
                budget_minor = int(round(float(lakh_match.group(1)) * 100000 * 100))
            else:
                curr_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+)", combined_text, re.IGNORECASE)
                if curr_match:
                    budget_minor = int(round(float(curr_match.group(1).replace(",", "")) * 100))
                else:
                    ctx_match = re.search(
                        r"(?:under|around|budget|below|less than|within|approx|max(?:imum)?|upto|up to|in the|can do around|do around)\s*(?:of\s*)?(\d{1,3}(?:,\d{2,3})+|\d{4,})",
                        combined_text,
                        re.IGNORECASE,
                    )
                    if ctx_match:
                        budget_minor = int(round(float(ctx_match.group(1).replace(",", "")) * 100))

        # Counter signal detection
        has_price_counter = bool(re.search(r"\b(?:over my budget|price too high|too high|closer to my budget|sharpen the offer|discount|tight budget)\b", combined_text, re.IGNORECASE))
        has_delivery_counter = bool(re.search(r"\b(?:faster delivery|express|express delivery|urgent|urgently|tomorrow|fast shipping)\b", combined_text, re.IGNORECASE))
        has_category_counter = bool(re.search(r"\b(?:not quite what I'm looking for|need a|specifically)\b", combined_text, re.IGNORECASE))

        # Category extraction
        cat_match = None
        for cat in ["laptop", "smartphone", "audio", "tablet", "smartwatch", "accessor"]:
            if cat in combined_text.lower():
                cat_match = cat
                break

        # 5. Strategic SKU Selection
        if catalog_matches:
            parsed_items = [
                {
                    "sku_id": m[0],
                    "name": m[1].strip(),
                    "category": m[2].strip(),
                    "base_price_minor": int(m[3]),
                    "cost_minor": int(m[4]),
                }
                for m in catalog_matches
            ]

            matching_items = []
            if cat_match:
                matching_items = [p for p in parsed_items if cat_match in p["category"].lower()]
            if not matching_items:
                matching_items = parsed_items

            sorted_by_price = sorted(matching_items, key=lambda x: (x["base_price_minor"], x["sku_id"]))

            if current_round == 1:
                selected = sorted_by_price[0]
            elif current_round == 2:
                if has_category_counter and len(sorted_by_price) > 1:
                    selected = sorted_by_price[1]
                else:
                    selected = sorted_by_price[0]
            else:  # Round 3
                # Choose item with best contribution margin that still approaches budget
                best_margin_item = max(matching_items, key=lambda x: (x["base_price_minor"] - x["cost_minor"], -x["base_price_minor"]))
                selected = best_margin_item if best_margin_item else sorted_by_price[0]
        else:
            selected = {
                "sku_id": "SKU-DEFAULT",
                "name": "Default Product",
                "category": "general",
                "base_price_minor": 5000000,
                "cost_minor": 3500000,
            }

        base_price_minor = selected["base_price_minor"]
        cost_minor = selected["cost_minor"]

        # 6. Commercial Policy Boundaries
        max_discount_cap_minor = int(base_price_minor * discount_cap_pct)
        min_price_margin_minor = int(cost_minor * (1.0 + margin_floor_pct))
        min_price_cap_minor = base_price_minor - max_discount_cap_minor
        min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)
        max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)

        # 7. Multi-Round Concession Strategy
        target_budget = budget_minor if budget_minor is not None else int(base_price_minor * 0.85)
        gap = max(0, base_price_minor - target_budget)

        if current_round == 1:
            # Anchor high in round 1
            discount_minor = 0
        elif current_round == 2:
            # Round 2: 60% concession towards target budget / counter request
            if gap > 0:
                discount_minor = min(int(gap * 0.60), max_allowed_discount_minor)
            elif has_price_counter:
                discount_minor = min(int(base_price_minor * 0.08), max_allowed_discount_minor)
            else:
                discount_minor = min(int(base_price_minor * 0.05), max_allowed_discount_minor)
        else:
            # Round 3: 95% concession towards target budget or max policy discount to close deal
            if gap > 0:
                discount_minor = min(int(gap * 0.95), max_allowed_discount_minor)
            else:
                discount_minor = max_allowed_discount_minor

        # Ensure discount does not violate caps
        discount_minor = max(0, min(discount_minor, max_allowed_discount_minor))
        proposed_price_minor = base_price_minor - discount_minor

        # 8. Shipping Tier Selection
        shipping_tier: Literal["standard", "express"] = "express" if has_delivery_counter else "standard"

        rationale = (
            f"Adaptive Mock LLM (Round {current_round}) proposed {selected['sku_id']} "
            f"at ₹{proposed_price_minor / 100:.2f} (discount ₹{discount_minor / 100:.2f}) "
            f"with {shipping_tier} shipping based on buyer feedback."
        )

        return LLMOutput(
            selected_sku_id=selected["sku_id"],
            proposed_price_minor=proposed_price_minor,
            discount_minor=discount_minor,
            shipping_tier=shipping_tier,
            rationale=rationale,
        )
