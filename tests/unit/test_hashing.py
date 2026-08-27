"""Unit tests for canonical hashing."""

from merchantos_core.contracts import CheckoutLineItem, CheckoutSnapshot
from merchantos_core.hashing import canonical_checkout_hash, sha256_hex


def test_sha256_hex_deterministic() -> None:
    """sha256_hex must produce consistent output for same bytes."""
    data = b"merchantos_test_payload"
    hash1 = sha256_hex(data)
    hash2 = sha256_hex(data)
    assert hash1 == hash2
    assert len(hash1) == 64


def test_canonical_checkout_hash_deterministic(sample_snapshot: CheckoutSnapshot) -> None:
    """Same snapshot data must produce exact same canonical hash."""
    hash1 = canonical_checkout_hash(sample_snapshot)
    hash2 = sample_snapshot.compute_content_hash()
    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 64


def test_canonical_hash_changes_on_amount(sample_line_items: list[CheckoutLineItem]) -> None:
    """Changing amount_minor must change hash."""
    snap1 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=10000,
        line_items=sample_line_items,
    )
    snap2 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=10001,
        line_items=sample_line_items,
    )
    assert canonical_checkout_hash(snap1) != canonical_checkout_hash(snap2)


def test_canonical_hash_changes_on_session_id(sample_line_items: list[CheckoutLineItem]) -> None:
    """Changing session_id must change hash."""
    snap1 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=10000,
        line_items=sample_line_items,
    )
    snap2 = CheckoutSnapshot(
        session_id="sess_02",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=10000,
        line_items=sample_line_items,
    )
    assert canonical_checkout_hash(snap1) != canonical_checkout_hash(snap2)


def test_canonical_hash_changes_on_merchant_id(sample_line_items: list[CheckoutLineItem]) -> None:
    """Changing merchant_id must change hash."""
    snap1 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=10000,
        line_items=sample_line_items,
    )
    snap2 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_02",
        currency="INR",
        amount_minor=10000,
        line_items=sample_line_items,
    )
    assert canonical_checkout_hash(snap1) != canonical_checkout_hash(snap2)


def test_canonical_hash_changes_on_line_items() -> None:
    """Changing line items content must change hash."""
    item1 = CheckoutLineItem(
        sku_id="SKU-A",
        name="Product A",
        quantity=1,
        unit_amount_minor=5000,
        line_total_minor=5000,
    )
    item2 = CheckoutLineItem(
        sku_id="SKU-B",
        name="Product B",
        quantity=1,
        unit_amount_minor=5000,
        line_total_minor=5000,
    )

    snap1 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=5000,
        line_items=[item1],
    )
    snap2 = CheckoutSnapshot(
        session_id="sess_01",
        merchant_id="merch_01",
        currency="INR",
        amount_minor=5000,
        line_items=[item2],
    )
    assert canonical_checkout_hash(snap1) != canonical_checkout_hash(snap2)
