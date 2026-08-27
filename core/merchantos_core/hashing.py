"""Canonical hashing utilities for MerchantOS AI."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from merchantos_core.contracts import CheckoutSnapshot


def sha256_hex(data: bytes) -> str:
    """Compute deterministic SHA256 hex digest for given bytes."""
    return hashlib.sha256(data).hexdigest()


def canonical_checkout_hash(snapshot: CheckoutSnapshot) -> str:
    """
    Compute a deterministic canonical SHA256 hex digest of a CheckoutSnapshot.

    Rules enforced:
    - Stable key ordering
    - Compact JSON separators (no extraneous whitespace)
    - All monetary amounts as minor integer units (paise)
    - Sensitive to amount, session_id, merchant_id, and line_items.
    """
    canonical_dict = {
        "amount_minor": snapshot.amount_minor,
        "currency": snapshot.currency,
        "line_items": [
            {
                "line_total_minor": item.line_total_minor,
                "name": item.name,
                "quantity": item.quantity,
                "sku_id": item.sku_id,
                "unit_amount_minor": item.unit_amount_minor,
            }
            for item in snapshot.line_items
        ],
        "merchant_id": snapshot.merchant_id,
        "session_id": snapshot.session_id,
    }
    raw_json = json.dumps(
        canonical_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return sha256_hex(raw_json.encode("utf-8"))
