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

    Extracts budget, category, and catalog details deterministically from the
    prompt and generates a compliant LLMOutput. Supports overrides for testing
    adversarial or out-of-bounds LLM responses.
    """

    def __init__(
        self,
        override_output: LLMOutput | None = None,
        override_fn: Callable[[str, str], LLMOutput] | None = None,
    ) -> None:
        self.override_output = override_output
        self.override_fn = override_fn

    def generate_offer_proposal(self, system_prompt: str, user_prompt: str) -> LLMOutput:
        """Generate deterministic LLMOutput from prompts."""
        if self.override_output is not None:
            return self.override_output

        if self.override_fn is not None:
            return self.override_fn(system_prompt, user_prompt)

        # 1. Parse catalog items from user prompt
        # Line format: "- SKU: <sku_id> | Name: <name> | Category: <cat> | Base Price: ₹... (<base_minor> paise) | Cost: ₹... (<cost_minor> paise) | Stock: <count>"
        catalog_pattern = re.compile(
            r"- SKU:\s*([\w\-]+)\s*\|\s*Name:\s*([^|]+)\|\s*Category:\s*([\w\-]+)\s*\|\s*"
            r"Base Price:\s*₹[0-9\.,]+\s*\((\d+)\s*paise\)\s*\|\s*Cost:\s*₹[0-9\.,]+\s*\((\d+)\s*paise\)"
        )
        catalog_matches = catalog_pattern.findall(user_prompt)

        # 2. Parse policy from user prompt
        # "Margin Floor: 15.0%\nDiscount Cap: 20.0%"
        margin_floor_pct = 0.15
        discount_cap_pct = 0.20
        mf_match = re.search(r"Margin Floor:\s*(\d+(?:\.\d+)?)%", user_prompt)
        if mf_match:
            margin_floor_pct = float(mf_match.group(1)) / 100.0
        dc_match = re.search(r"Discount Cap:\s*(\d+(?:\.\d+)?)%", user_prompt)
        if dc_match:
            discount_cap_pct = float(dc_match.group(1)) / 100.0

        # 3. Parse buyer budget from user prompt
        # Look in BUYER UTTERANCE section
        utterance_match = re.search(r'BUYER UTTERANCE:\s*\n"([^"]+)"', user_prompt)
        utterance = utterance_match.group(1) if utterance_match else user_prompt

        budget_minor = None
        k_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", utterance, re.IGNORECASE)
        if k_match:
            budget_minor = int(round(float(k_match.group(1)) * 1000 * 100))
        else:
            lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b", utterance, re.IGNORECASE)
            if lakh_match:
                budget_minor = int(round(float(lakh_match.group(1)) * 100000 * 100))
            else:
                curr_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+)", utterance, re.IGNORECASE)
                if curr_match:
                    budget_minor = int(round(float(curr_match.group(1).replace(",", "")) * 100))
                else:
                    ctx_match = re.search(
                        r"(?:under|around|budget|below|less than|within|approx|max(?:imum)?|upto|up to|in the)\s*(?:of\s*)?(\d{1,3}(?:,\d{2,3})+|\d{4,})",
                        utterance,
                        re.IGNORECASE,
                    )
                    if ctx_match:
                        budget_minor = int(round(float(ctx_match.group(1).replace(",", "")) * 100))

        # 4. Parse category preference
        cat_match = None
        for cat in ["laptop", "smartphone", "audio", "tablet", "smartwatch", "accessor"]:
            if cat in utterance.lower():
                cat_match = cat
                break

        # 5. Parse urgency
        is_urgent = bool(re.search(r"\b(?:urgent|urgently|fast|faster|tomorrow|express|asap|expedited|immediately|quick|quickly)\b", utterance, re.IGNORECASE))
        shipping_tier: Literal["standard", "express"] = "express" if is_urgent else "standard"

        # Select catalog product
        if catalog_matches:
            # item: (sku_id, name, category, base_price_minor, cost_minor)
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

            if matching_items:
                selected = min(matching_items, key=lambda x: (x["base_price_minor"], x["sku_id"]))
            else:
                selected = min(parsed_items, key=lambda x: (x["base_price_minor"], x["sku_id"]))
        else:
            # Fallback if catalog not parseable from prompt text
            selected = {
                "sku_id": "SKU-DEFAULT",
                "name": "Default Product",
                "category": "general",
                "base_price_minor": 5000000,
                "cost_minor": 3500000,
            }

        base_price_minor = selected["base_price_minor"]
        cost_minor = selected["cost_minor"]

        # Calculate bounds
        max_discount_cap_minor = int(base_price_minor * discount_cap_pct)
        min_price_margin_minor = int(cost_minor * (1.0 + margin_floor_pct))
        min_price_cap_minor = base_price_minor - max_discount_cap_minor
        min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)
        max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)

        if budget_minor is not None and budget_minor < base_price_minor:
            desired_discount = base_price_minor - budget_minor
            discount_minor = min(desired_discount, max_allowed_discount_minor)
        else:
            discount_minor = 0

        proposed_price_minor = base_price_minor - discount_minor
        rationale = (
            f"Mock LLM selected {selected['sku_id']} ({selected['name']}) with price "
            f"₹{proposed_price_minor / 100:.2f} (discount ₹{discount_minor / 100:.2f}) "
            f"and {shipping_tier} shipping."
        )

        return LLMOutput(
            selected_sku_id=selected["sku_id"],
            proposed_price_minor=proposed_price_minor,
            discount_minor=discount_minor,
            shipping_tier=shipping_tier,
            rationale=rationale,
        )
