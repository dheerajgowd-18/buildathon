"""Marketplace catalog and inventory generation for MerchantOS AI."""

from __future__ import annotations

import random
from merchantos_core.contracts import Product

_CATEGORY_TEMPLATES: dict[str, list[str]] = {
    "laptops": [
        "Apex Ultrabook 14",
        "VoltBook Pro 15",
        "NovaBook Gaming 16",
        "Zenith Air 13",
        "TitanWork Station 17",
        "StreamLite 14",
        "Horizon Slim 15.6",
        "AeroBook Studio 14",
        "OmniBook Max 16",
        "ProMax Book 13",
    ],
    "smartphones": [
        "NovaPhone 12 5G",
        "Apex Pixel 8 Pro",
        "Volt Mobile Pro",
        "Zenith Prime 5G",
        "Horizon Ultra 256GB",
        "LitePhone Max",
        "AeroPhone SE",
        "OmniGrip 5G",
        "TitanCell Pro",
        "Proxima X 128GB",
    ],
    "audio": [
        "AeroPods Pro Wireless Earbuds",
        "VoltSound Active ANC Headphones",
        "Zenith Studio Monitor Headphones",
        "Apex Boom Portable Speaker",
        "NovaBeat True Wireless",
        "TitanBass Dolby Soundbar",
        "Horizon Hi-Fi Desk Monitors",
        "StreamSound Neckband Earphones",
    ],
    "tablets": [
        "ApexPad 11 WiFi",
        "VoltPad Pro 12.9",
        "NovaTab 10 FHD",
        "Zenith Slate 10.5",
        "Horizon Mini Tab 8",
        "TitanDraw Studio 13",
    ],
    "smartwatches": [
        "VoltWatch Chrono 4",
        "ApexFit Smartband Pro",
        "Zenith Pulse Pro GPS",
        "NovaTrack Active Watch",
        "Horizon Time Elite",
    ],
    "accessories": [
        "VoltFast 65W GaN Fast Charger",
        "Apex Ergonomic Wireless Mouse",
        "NovaKey RGB Mechanical Keyboard",
        "Zenith USB-C 8-in-1 Multiport Dock",
        "TitanShield Waterproof Laptop Sleeve",
    ],
}

_PRICE_RANGES_INR: dict[str, tuple[int, int]] = {
    "laptops": (30_000, 100_000),
    "smartphones": (12_000, 85_000),
    "audio": (1_500, 25_000),
    "tablets": (15_000, 70_000),
    "smartwatches": (3_000, 35_000),
    "accessories": (800, 8_000),
}


def generate_catalog(seed: int, category: str, sku_count: int = 5) -> list[Product]:
    """Deterministically generate a product catalog for a given category and seed.

    Args:
        seed: Random seed for deterministic generation.
        category: Product category (e.g. 'laptops', 'smartphones', 'audio').
        sku_count: Number of unique SKUs to generate in the catalog.

    Returns:
        List of Product models with valid baseline margins (base_price_minor > cost_minor).
    """
    rng = random.Random(seed)
    cat_key = category.lower().strip()
    templates = _CATEGORY_TEMPLATES.get(
        cat_key,
        [f"{category.capitalize()} Pro Model-{i + 1}" for i in range(max(20, sku_count))],
    )
    price_min, price_max = _PRICE_RANGES_INR.get(cat_key, (5_000, 50_000))

    products: list[Product] = []
    for i in range(sku_count):
        base_name = templates[i % len(templates)]
        if i >= len(templates):
            name = f"{base_name} (Gen {i // len(templates) + 1})"
        else:
            name = base_name

        # Price in INR rounded to hundreds, converted to minor units (paise)
        price_inr = rng.randint(price_min // 100, price_max // 100) * 100
        base_price_minor = price_inr * 100

        # Margin between 15% and 35%
        margin_pct = rng.uniform(0.15, 0.35)
        cost_minor = int(base_price_minor * (1.0 - margin_pct))

        # Strictly enforce base_price_minor > cost_minor
        if cost_minor >= base_price_minor:
            cost_minor = max(0, base_price_minor - 1000)

        # Inventory count between 5 and 50 units
        inventory_count = rng.randint(5, 50)

        cat_prefix = (cat_key[:3] if len(cat_key) >= 3 else "GEN").upper()
        sku_id = f"SKU-{cat_prefix}-{seed % 10000:04d}-{i + 1:02d}"

        products.append(
            Product(
                sku_id=sku_id,
                name=name,
                category=category,
                cost_minor=cost_minor,
                base_price_minor=base_price_minor,
                inventory_count=inventory_count,
            )
        )

    return products
