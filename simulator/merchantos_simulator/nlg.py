"""Natural language utterance generator with lossy divergence mechanics."""

from __future__ import annotations

import random
from merchantos_core.contracts import BuyerIntent

_CATEGORY_SINGULAR: dict[str, str] = {
    "laptops": "laptop",
    "smartphones": "smartphone",
    "audio": "audio device",
    "tablets": "tablet",
    "smartwatches": "smartwatch",
    "accessories": "tech accessory",
}

_PRIORITY_LABELS: dict[str, str] = {
    "battery": "all-day battery life",
    "performance": "high performance and speed",
    "lightweight": "lightweight portable design",
    "display": "crisp display quality",
    "gaming": "smooth gaming performance",
    "storage": "large storage capacity",
    "delivery": "express shipping",
    "price": "budget affordability",
    "camera": "great camera quality",
    "5g": "fast 5G connectivity",
    "noise_cancellation": "active noise cancellation",
    "bass": "deep punchy bass",
    "microphone": "clear microphone for calls",
    "waterproof": "water resistance",
    "screen_size": "large screen size",
    "stylus_support": "stylus pen support",
    "portability": "easy portability",
    "heart_rate": "heart rate monitoring",
    "gps": "accurate standalone GPS",
    "design": "sleek modern design",
    "durability": "rugged durability",
    "fast_charging": "fast charging support",
    "compatibility": "broad device compatibility",
    "compact_size": "compact form factor",
    "quality": "premium build quality",
}

_EXCLUSION_LABELS: dict[str, str] = {
    "refurbished": "no refurbished units",
    "heavy": "nothing too heavy or bulky",
    "plastic_build": "avoid cheap plastic build",
    "slow_delivery": "no delayed shipping",
    "no_warranty": "must have brand warranty",
    "low_battery": "avoid poor battery backup",
}


def _format_budget_k(budget_minor: int) -> str:
    """Format budget in thousands (k) notation, e.g. 6000000 paise -> '60k'."""
    budget_inr = budget_minor // 100
    if budget_inr >= 1000:
        return f"{budget_inr // 1000}k"
    return f"{budget_inr} INR"


def _format_budget_inr(budget_minor: int) -> str:
    """Format budget in INR with currency symbol and commas, e.g. 6000000 paise -> '₹60,000'."""
    budget_inr = budget_minor // 100
    return f"₹{budget_inr:,}"


def generate_lossy_utterance(intent: BuyerIntent, seed: int) -> str:
    """Generate a natural language utterance reflecting stated buyer preferences.

    Applies lossy distortion based on intent.stated_vs_true_divergence:
    - High Divergence (>= 0.6): Stated text explicitly obscures or contradicts
      true underlying sensitivities and preferences.
    - Medium Divergence (0.3 <= div < 0.6): Ambiguous, partial, or approximate statements.
    - Low Divergence (< 0.3): Faithful natural language translation of intent.

    Hard Security / Fairness Constraints:
    - Never outputs internal Pydantic field names (e.g. 'priority', 'category', 'budget_max_minor').
    - Never leaks raw integer minor units (paise) into the utterance.
    """
    rng = random.Random(seed)
    cat_raw = intent.category.lower().strip()
    cat = _CATEGORY_SINGULAR.get(cat_raw, cat_raw.rstrip("s"))
    budget_k = _format_budget_k(intent.budget_max_minor)
    budget_inr = _format_budget_inr(intent.budget_max_minor)

    primary_pref = intent.priority[0] if intent.priority else "quality"
    pref_desc = _PRIORITY_LABELS.get(primary_pref, primary_pref.replace("_", " "))

    divergence = intent.stated_vs_true_divergence

    if divergence >= 0.6:
        # High Divergence: Contradict or obscure true sensitivities
        if intent.price_sensitivity >= 0.6:
            # True preference is very price sensitive; stated text claims budget is flexible
            lead_choices = [
                f"I'm looking for a top-tier {cat} and budget is flexible if {pref_desc} is exceptional",
                f"Need the highest quality {cat} available, willing to stretch beyond normal budget",
                f"Looking for a {cat} where {pref_desc} is the main consideration, price is not an issue",
                f"Seeking a premium {cat} with great build, budget is open",
            ]
        else:
            # True preference is price insensitive; stated text claims strict budget constraint
            lead_choices = [
                f"Looking for an entry-level {cat} strictly under {budget_k}",
                f"Need the most affordable {cat} on a tight budget",
                f"Searching for a discounted {cat} around {budget_k} with maximum savings",
                f"Need a budget-friendly {cat}, want to keep costs minimal",
            ]
        lead = rng.choice(lead_choices)

        if intent.delivery_sensitivity >= 0.6:
            # True preference is urgent; stated text claims relaxed delivery
            delivery_choices = [
                "standard delivery is fine, no hurry",
                "can wait a week or more for delivery",
                "delivery timing is flexible",
            ]
        else:
            # True preference is relaxed; stated text claims urgent need
            delivery_choices = [
                "need expedited delivery if possible",
                "urgent requirement, looking for fast shipping",
                "would prefer delivery by tomorrow",
            ]
        delivery_phrase = rng.choice(delivery_choices)

        utterance = f"{lead}. Also, {delivery_phrase}."

    elif divergence >= 0.3:
        # Medium Divergence: somewhat noisy or approximate
        lead_templates = [
            f"Looking to buy a {cat} with budget around {budget_k}.",
            f"Need a good {cat} in the {budget_inr} range.",
            f"Interested in a {cat} with decent {pref_desc} around {budget_k}.",
        ]
        lead = rng.choice(lead_templates)

        details: list[str] = []
        if rng.random() > 0.4:
            details.append(f"main requirement is {pref_desc}")

        if intent.delivery_days_max <= 2:
            details.append("faster delivery preferred")
        elif rng.random() > 0.5:
            details.append("standard shipping is okay")

        if intent.hard_exclusions and rng.random() > 0.4:
            excl = intent.hard_exclusions[0]
            excl_label = _EXCLUSION_LABELS.get(excl, f"avoid {excl.replace('_', ' ')}")
            details.append(excl_label)

        if details:
            utterance = f"{lead} Note: {', '.join(details)}."
        else:
            utterance = lead

    else:
        # Low Divergence: faithful representation
        lead = f"Looking for a {cat} under {budget_inr}."
        clauses: list[str] = []

        if intent.priority:
            clauses.append(f"Main focus is {pref_desc}")

        if intent.delivery_days_max <= 2:
            clauses.append(f"need it delivered within {intent.delivery_days_max} days")
        elif intent.delivery_days_max <= 5:
            clauses.append(f"delivery within {intent.delivery_days_max} days works")

        if intent.hard_exclusions:
            excl_text = ", ".join([_EXCLUSION_LABELS.get(e, e.replace("_", " ")) for e in intent.hard_exclusions])
            clauses.append(f"preferences: {excl_text}")

        if clauses:
            utterance = f"{lead} {'. '.join(clauses)}."
        else:
            utterance = lead

    return utterance
