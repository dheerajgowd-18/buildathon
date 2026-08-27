"""Unit tests for HMAC SHA256 webhook signature verification."""

from pydantic import SecretStr

from merchantos_razorpay.webhook import (
    compute_webhook_signature,
    verify_webhook_signature,
)


def test_valid_signature_passes() -> None:
    """Valid HMAC signature over payload must pass verification."""
    secret = SecretStr("top_secret_key_12345")
    raw_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_123"}}}}'
    signature = compute_webhook_signature(raw_body, secret)

    assert verify_webhook_signature(raw_body, signature, secret) is True


def test_invalid_signature_fails() -> None:
    """Tampered or invalid signature hex string must fail."""
    secret = SecretStr("top_secret_key_12345")
    raw_body = b'{"event":"payment.captured"}'
    invalid_signature = "bad_signature_hex_1234567890abcdef"

    assert verify_webhook_signature(raw_body, invalid_signature, secret) is False


def test_missing_signature_fails() -> None:
    """None or empty signature header must fail."""
    secret = SecretStr("top_secret_key_12345")
    raw_body = b'{"event":"payment.captured"}'

    assert verify_webhook_signature(raw_body, None, secret) is False
    assert verify_webhook_signature(raw_body, "", secret) is False
    assert verify_webhook_signature(raw_body, "   ", secret) is False


def test_wrong_secret_fails() -> None:
    """Signature computed with one secret must fail verification against another secret."""
    secret_a = SecretStr("secret_a_123")
    secret_b = SecretStr("secret_b_456")
    raw_body = b'{"event":"payment.captured"}'

    sig_a = compute_webhook_signature(raw_body, secret_a)
    assert verify_webhook_signature(raw_body, sig_a, secret_b) is False


def test_tampered_body_fails() -> None:
    """Signature over original body must fail if raw body is tampered even by 1 byte."""
    secret = SecretStr("top_secret_key_12345")
    original_body = b'{"amount":50000,"status":"captured"}'
    tampered_body = b'{"amount":50001,"status":"captured"}'

    sig_original = compute_webhook_signature(original_body, secret)
    assert verify_webhook_signature(tampered_body, sig_original, secret) is False
