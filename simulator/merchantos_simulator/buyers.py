"""Buyer profile and ground truth intent generation for MerchantOS AI."""

from __future__ import annotations

import random
from merchantos_core.contracts import BuyerIntent

_CATEGORY_PRIORITY_POOLS: dict[str, list[str]] = {
    "laptops": ["battery", "performance", "lightweight", "display", "gaming", "storage", "delivery", "price"],
    "smartphones": ["camera", "battery", "5g", "storage", "display", "delivery", "price"],
    "audio": ["noise_cancellation", "bass", "battery", "microphone", "waterproof", "delivery", "price"],
    "tablets": ["screen_size", "stylus_support", "battery", "performance", "portability", "delivery", "price"],
    "smartwatches": ["battery", "heart_rate", "gps", "waterproof", "design", "delivery", "price"],
    "accessories": ["durability", "fast_charging", "compatibility", "compact_size", "delivery", "price"],
}

_EXCLUSION_POOL: list[str] = [
    "refurbished",
    "heavy",
    "plastic_build",
    "slow_delivery",
    "no_warranty",
    "low_battery",
]

_BUDGET_RANGES_INR: dict[str, tuple[int, int]] = {
    "laptops": (35_000, 95_000),
    "smartphones": (15_000, 80_000),
    "audio": (2_000, 22_000),
    "tablets": (18_000, 65_000),
    "smartwatches": (4_000, 30_000),
    "accessories": (1_000, 7_500),
}


def generate_buyer_intent(seed: int, category: str, divergence: float) -> BuyerIntent:
    """Deterministically generate ground-truth buyer intent.

    Args:
        seed: Random seed for deterministic generation.
        category: Product category for the intent.
        divergence: Stated vs true divergence factor (0.0 to 1.0).

    Returns:
        BuyerIntent contract instance with ground truth parameters.
    """
    rng = random.Random(seed)
    cat_key = category.lower().strip()

    budget_min, budget_max = _BUDGET_RANGES_INR.get(cat_key, (5_000, 45_000))
    # Budget in INR rounded to thousands, converted to paise
    budget_inr = rng.randint(budget_min // 1000, budget_max // 1000) * 1000
    budget_max_minor = budget_inr * 100

    delivery_days_max = rng.choice([1, 2, 3, 5, 7])

    priority_pool = _CATEGORY_PRIORITY_POOLS.get(
        cat_key,
        ["quality", "durability", "delivery", "price", "performance"],
    )
    priority_count = rng.randint(1, min(3, len(priority_pool)))
    priorities = rng.sample(priority_pool, k=priority_count)

    exclusion_count = rng.randint(0, 2)
    hard_exclusions = rng.sample(_EXCLUSION_POOL, k=exclusion_count)

    price_sensitivity = round(rng.uniform(0.1, 0.95), 2)
    delivery_sensitivity = round(rng.uniform(0.1, 0.95), 2)
    acceptance_threshold = round(rng.uniform(0.5, 0.9), 2)
    divergence_val = round(float(divergence), 4)

    session_id = f"sess_{seed % 1000000:06d}"

    return BuyerIntent(
        session_id=session_id,
        category=category,
        budget_max_minor=budget_max_minor,
        delivery_days_max=delivery_days_max,
        priority=priorities,
        hard_exclusions=hard_exclusions,
        price_sensitivity=price_sensitivity,
        delivery_sensitivity=delivery_sensitivity,
        acceptance_threshold=acceptance_threshold,
        stated_vs_true_divergence=divergence_val,
    )
