"""Deterministic rules-based baseline decision agent for MerchantOS AI."""

from __future__ import annotations

import re
from typing import Literal

from merchantos_core.contracts import (
    AgentInput,
    ExtractedSignals,
    Product,
    ProposedOffer,
)

# Canonical mapping from singular/plural/synonym terms to catalog categories
_CATEGORY_MAPPING: dict[str, str] = {
    "laptop": "laptops",
    "laptops": "laptops",
    "ultrabook": "laptops",
    "notebook": "laptops",
    "macbook": "laptops",
    "smartphone": "smartphones",
    "smartphones": "smartphones",
    "phone": "smartphones",
    "phones": "smartphones",
    "mobile": "smartphones",
    "audio device": "audio",
    "audio": "audio",
    "earbuds": "audio",
    "earphone": "audio",
    "earphones": "audio",
    "headphones": "audio",
    "headphone": "audio",
    "speaker": "audio",
    "speakers": "audio",
    "soundbar": "audio",
    "tablet": "tablets",
    "tablets": "tablets",
    "ipad": "tablets",
    "smartwatch": "smartwatches",
    "smartwatches": "smartwatches",
    "smartband": "smartwatches",
    "watch": "smartwatches",
    "watches": "smartwatches",
    "tech accessory": "accessories",
    "accessory": "accessories",
    "accessories": "accessories",
    "charger": "accessories",
    "mouse": "accessories",
    "keyboard": "accessories",
    "sleeve": "accessories",
    "dock": "accessories",
}

_HIGH_URGENCY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:urgent|urgently|fast|faster|tomorrow|express|asap|expedited|immediately|quick|quickly)\b", re.IGNORECASE),
    re.compile(r"\b(?:within\s+(?:1|2)\s+days?)\b", re.IGNORECASE),
    re.compile(r"\b(?:1|2)\s*[- ]day\s+delivery\b", re.IGNORECASE),
]

_LOW_URGENCY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:flexible|no\s+hurry|relaxed|no\s+rush|can\s+wait|not\s+urgent|take\s+your\s+time)\b", re.IGNORECASE),
    re.compile(r"\b(?:within\s+[5-9]\s+days?|week\s+or\s+more)\b", re.IGNORECASE),
]

_STOPWORDS: set[str] = {
    "i", "im", "me", "my", "looking", "look", "for", "a", "an", "the", "in", "and", "is", "to",
    "with", "under", "around", "budget", "need", "want", "of", "on", "at", "also", "note",
    "preferences", "strictly", "range", "works", "fine", "okay", "be", "are", "it", "by",
    "within", "prefer", "preferred", "seeking", "interested", "buy", "getting", "where",
    "main", "focus", "requirement", "consideration", "top", "good", "best", "available",
    "entry-level", "entry", "level", "something", "delivered", "shipping", "delivery",
    "timing", "days", "day", "costs", "cost", "minimal", "tight", "stretch", "normal",
    "beyond", "open", "issue", "savings", "friendly", "great", "decent", "quality",
    "affordability", "price", "speed", "performance", "high", "low", "medium", "more",
}


def _extract_budget_minor(text: str) -> int | None:
    """Deterministically extract buyer budget in paise (integer minor units)."""
    # 1. Look for 'k' notation: e.g. "60k", "89k", "₹50k", "under 60k", "budget 50k", "around 41k"
    k_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*k\b", text, re.IGNORECASE)
    if k_match:
        val = float(k_match.group(1))
        return int(round(val * 1000 * 100))

    # 2. Look for 'lakh' / 'lac' notation: e.g. "1.5 lakh", "2 lakhs", "1 lac"
    lakh_match = re.search(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:lakh|lac|lakhs|lacs)\b", text, re.IGNORECASE)
    if lakh_match:
        val = float(lakh_match.group(1))
        return int(round(val * 100000 * 100))

    # 3. Look for explicit currency symbol: e.g. "₹85,000", "₹50,000", "Rs. 60,000", "INR 45000", "₹50000"
    curr_match = re.search(r"(?:₹|rs\.?|inr)\s*(\d{1,3}(?:,\d{2,3})*(?:\.\d+)?|\d+)", text, re.IGNORECASE)
    if curr_match:
        clean_num = curr_match.group(1).replace(",", "")
        val = float(clean_num)
        return int(round(val * 100))

    # 4. Look for context phrases with raw numbers: e.g. "under 60000", "budget 50000", "around 45,000"
    ctx_match = re.search(
        r"(?:under|around|budget|below|less than|within|approx|max(?:imum)?|upto|up to|in the)\s*(?:of\s*)?(\d{1,3}(?:,\d{2,3})+|\d{4,})",
        text,
        re.IGNORECASE,
    )
    if ctx_match:
        clean_num = ctx_match.group(1).replace(",", "")
        val = float(clean_num)
        return int(round(val * 100))

    return None


def _extract_category(text: str) -> str | None:
    """Deterministically identify product category from utterance."""
    text_lower = text.lower()
    # Sort phrases by length descending to match multi-word phrases first (e.g. "tech accessory", "audio device")
    for phrase, cat in sorted(_CATEGORY_MAPPING.items(), key=lambda x: len(x[0]), reverse=True):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        if re.search(pattern, text_lower):
            return cat
    return None


def _extract_urgency(text: str) -> Literal["low", "medium", "high"]:
    """Deterministically determine urgency level from utterance."""
    for pat in _HIGH_URGENCY_PATTERNS:
        if pat.search(text):
            return "high"

    for pat in _LOW_URGENCY_PATTERNS:
        if pat.search(text):
            return "low"

    return "medium"


def _extract_keywords(text: str) -> list[str]:
    """Extract relevant nouns/adjectives from utterance, filtering stop words and extracted tokens."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = cleaned.split()
    keywords: list[str] = []
    seen: set[str] = set()

    category_terms = set(_CATEGORY_MAPPING.keys())

    for token in tokens:
        if token.isdigit():
            continue
        if re.match(r"^\d+k$", token):
            continue
        if token in _STOPWORDS:
            continue
        if token in category_terms:
            continue
        if len(token) <= 2:
            continue
        if token not in seen:
            seen.add(token)
            keywords.append(token)

    return keywords


class RulesBaselineAgent:
    """Deterministic rules-based baseline decision agent.

    This agent strictly enforces the AgentInput boundary, extracts signals
    deterministically using standard library regular expressions, and produces
    commercial offers mathematically guaranteed to respect merchant policy bounds.
    """

    def extract_signals(self, utterance: str) -> ExtractedSignals:
        """Deterministically extract structured signals from natural language utterance.

        Args:
            utterance: Raw buyer natural language string.

        Returns:
            ExtractedSignals model containing estimated budget, category, urgency, and keywords.
        """
        budget_minor = _extract_budget_minor(utterance)
        category = _extract_category(utterance)
        urgency = _extract_urgency(utterance)
        keywords = _extract_keywords(utterance)

        return ExtractedSignals(
            estimated_budget_minor=budget_minor,
            estimated_category=category,
            keywords=keywords,
            urgency_level=urgency,
        )

    def score_and_propose(self, agent_input: AgentInput) -> ProposedOffer:
        """Evaluate agent input and propose a deterministic commercial offer.

        Strict Input Enforcement:
            Must accept AgentInput and ONLY AgentInput. Rejects SimulatedScenario,
            BuyerIntent, or any payload with extra ground-truth fields.

        Pricing & Discount Logic:
            - Caps discount at merchant_policy.discount_cap_pct * base_price_minor.
            - Guarantees proposed price never falls below cost_minor * (1 + margin_floor_pct).
            - Applies minimum required discount to meet buyer's estimated budget up to cap.

        Shipping Logic:
            - Proposes 'express' if urgency_level is 'high', else 'standard'.

        Args:
            agent_input: Validated AgentInput model.

        Returns:
            Deterministic ProposedOffer model.
        """
        # Strict boundary enforcement
        if not isinstance(agent_input, AgentInput):
            if hasattr(agent_input, "model_dump"):
                agent_input = AgentInput.model_validate(agent_input.model_dump())
            elif isinstance(agent_input, dict):
                agent_input = AgentInput.model_validate(agent_input)
            else:
                raise TypeError(f"Expected AgentInput instance, got {type(agent_input).__name__}")

        if not agent_input.available_catalog:
            raise ValueError("available_catalog must not be empty")

        # Non-adaptive behavior: if prior merchant offers exist in history, repeat the round 1 offer
        if agent_input.negotiation_history:
            for event in agent_input.negotiation_history:
                if event.actor == "merchant_agent" and event.proposed_offer is not None:
                    return event.proposed_offer

        # 1. Signal extraction (from initial utterance)
        signals = self.extract_signals(agent_input.nl_utterance)


        # 2. Product selection
        # Filter available catalog by estimated category
        matching_products: list[Product] = []
        if signals.estimated_category:
            target_cat = signals.estimated_category.lower().rstrip("s")
            matching_products = [
                p for p in agent_input.available_catalog
                if p.category.lower().rstrip("s") == target_cat
            ]

        fallback_used = False
        if matching_products:
            # Select cheapest item in the category (tie-break with sku_id for strict determinism)
            selected_item = min(matching_products, key=lambda p: (p.base_price_minor, p.sku_id))
        else:
            # Fall back to cheapest item across entire available catalog
            fallback_used = True
            selected_item = min(agent_input.available_catalog, key=lambda p: (p.base_price_minor, p.sku_id))

        # 3. Pricing and discount calculation
        base_price_minor = selected_item.base_price_minor
        cost_minor = selected_item.cost_minor
        policy = agent_input.merchant_policy

        # Calculate maximum allowed discount based on discount cap
        max_discount_cap_minor = int(base_price_minor * policy.discount_cap_pct)

        # Calculate minimum allowed price based on margin floor
        min_price_margin_minor = int(cost_minor * (1.0 + policy.margin_floor_pct))
        min_price_cap_minor = base_price_minor - max_discount_cap_minor

        # Effective minimum allowable price and maximum allowable discount
        min_allowed_price_minor = max(min_price_cap_minor, min_price_margin_minor)
        max_allowed_discount_minor = max(0, base_price_minor - min_allowed_price_minor)

        discount_reason = "none"
        if signals.estimated_budget_minor is not None and signals.estimated_budget_minor < base_price_minor:
            desired_discount_minor = base_price_minor - signals.estimated_budget_minor
            if desired_discount_minor > max_allowed_discount_minor:
                discount_minor = max_allowed_discount_minor
                if min_allowed_price_minor == min_price_margin_minor and min_price_margin_minor > min_price_cap_minor:
                    discount_reason = "margin_floor_cap"
                else:
                    discount_reason = "discount_cap"
            else:
                discount_minor = desired_discount_minor
                discount_reason = "budget_met"
        else:
            discount_minor = 0

        proposed_price_minor = base_price_minor - discount_minor

        # 4. Shipping tier selection
        shipping_tier: Literal["standard", "express"] = (
            "express" if signals.urgency_level == "high" else "standard"
        )

        # 5. Deterministic rationale generation
        item_cat_name = selected_item.category.rstrip("s")
        if fallback_used:
            cat_desc = f"No category match for '{signals.estimated_category}'; selected cheapest catalog item {selected_item.name} ({selected_item.sku_id})"
        else:
            cat_desc = f"Selected cheapest {item_cat_name} {selected_item.name} ({selected_item.sku_id})"

        if discount_minor > 0:
            pct = (discount_minor / base_price_minor) * 100
            disc_inr = discount_minor // 100
            if discount_reason == "discount_cap":
                price_desc = f"Applied {pct:.1f}% discount (₹{disc_inr:,}) capped by {policy.discount_cap_pct * 100:.0f}% policy limit to approach budget"
            elif discount_reason == "margin_floor_cap":
                price_desc = f"Applied {pct:.1f}% discount (₹{disc_inr:,}) constrained by {policy.margin_floor_pct * 100:.0f}% margin floor requirement"
            else:
                price_desc = f"Applied {pct:.1f}% discount (₹{disc_inr:,}) to meet buyer budget"
        else:
            price_desc = f"Offered at base price ₹{base_price_minor // 100:,} (no discount required)"

        ship_desc = f"{shipping_tier.capitalize()} shipping selected based on {signals.urgency_level} urgency."
        rationale = f"{cat_desc}. {price_desc}. {ship_desc}"

        offer_id = f"off_{agent_input.session_id}_{selected_item.sku_id}"

        return ProposedOffer(
            offer_id=offer_id,
            session_id=agent_input.session_id,
            selected_sku_id=selected_item.sku_id,
            proposed_price_minor=proposed_price_minor,
            discount_minor=discount_minor,
            shipping_tier=shipping_tier,
            rationale=rationale,
        )
