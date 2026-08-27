"""Integration tests for the /webhooks/razorpay endpoint."""

import json

from fastapi.testclient import TestClient
from pydantic import SecretStr

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_razorpay.adapter import MockRazorpayAdapter
from merchantos_razorpay.webhook import compute_webhook_signature


def test_webhook_endpoint_rejects_missing_signature() -> None:
    """Missing X-Razorpay-Signature header returns HTTP 400."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)

    raw_body = b'{"event":"payment.captured"}'

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"
    assert "Invalid or missing" in data["message"]


def test_webhook_endpoint_rejects_invalid_signature() -> None:
    """Invalid signature header returns HTTP 400."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)

    raw_body = b'{"event":"payment.captured"}'

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": "invalid_signature_hex_12345",
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"


def test_webhook_endpoint_rejects_tampered_body() -> None:
    """Tampered body returns HTTP 400 even if signature was valid for original body."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)
    secret = settings.get_effective_webhook_secret()

    original_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_1"}}}}'
    signature = compute_webhook_signature(original_body, secret)

    tampered_body = b'{"event":"payment.captured","payload":{"payment":{"entity":{"id":"pay_2"}}}}'

    response = client.post(
        "/webhooks/razorpay",
        content=tampered_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "rejected"


def test_webhook_endpoint_accepts_valid_signed_payment_captured() -> None:
    """Validly signed payment.captured returns HTTP 200 with status=processed."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)
    adapter = MockRazorpayAdapter(settings=settings)

    raw_body, signature = adapter.generate_mock_signed_payment_captured(
        order_id="order_mock_captured_1",
        amount_minor=85000,
        payment_id="pay_mock_cap_99",
    )

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.captured"
    assert "processed successfully" in data["message"]


def test_webhook_endpoint_accepts_valid_signed_payment_failed() -> None:
    """Validly signed payment.failed returns HTTP 200 with status=processed."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)
    adapter = MockRazorpayAdapter(settings=settings)

    raw_body, signature = adapter.generate_mock_signed_payment_failed(
        order_id="order_mock_failed_1",
        amount_minor=85000,
        payment_id="pay_mock_fail_99",
        error_code="BAD_REQUEST_ERROR",
        error_description="Card declined",
    )

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["event_type"] == "payment.failed"
    assert "processed successfully" in data["message"]


def test_webhook_endpoint_accepts_unknown_event_gracefully() -> None:
    """Validly signed unknown event returns HTTP 200 with status=ignored."""
    secret = SecretStr("custom_webhook_secret_for_tests")
    settings = Settings(
        razorpay_use_mock=True,
        razorpay_webhook_secret=secret,
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    payload = {
        "entity": "event",
        "event": "refund.created",
        "payload": {
            "refund": {
                "entity": {
                    "id": "rfnd_12345",
                    "amount": 2000,
                }
            }
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")
    signature = compute_webhook_signature(raw_body, secret)

    response = client.post(
        "/webhooks/razorpay",
        content=raw_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ignored"
    assert data["event_type"] == "refund.created"
    assert "accepted but ignored" in data["message"]


def test_webhook_endpoint_rejects_malformed_known_event() -> None:
    """Validly signed event with malformed known schema returns HTTP 400 invalid_payload."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)
    secret = settings.get_effective_webhook_secret()

    # payment.captured missing required payload structure
    malformed_body = b'{"event":"payment.captured","payload":{"invalid_structure":true}}'
    signature = compute_webhook_signature(malformed_body, secret)

    response = client.post(
        "/webhooks/razorpay",
        content=malformed_body,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert data["status"] == "invalid_payload"
