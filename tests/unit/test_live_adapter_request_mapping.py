"""Unit tests for LiveRazorpayAdapter using httpx.MockTransport."""

import json

import httpx
import pytest
from pydantic import SecretStr

from merchantos_core.config import Settings
from merchantos_core.contracts import RazorpayOrderNotes, RazorpayOrderRequest
from merchantos_razorpay.adapter import (
    LiveRazorpayAdapter,
    RazorpayApiError,
    RazorpayTransportError,
    build_razorpay_adapter,
)


def test_live_adapter_request_mapping_and_response_parsing() -> None:
    """Verify live adapter transforms request correctly and parses Razorpay response."""
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        response_body = {
            "id": "order_live_123456",
            "entity": "order",
            "amount": 75000,
            "amount_paid": 0,
            "amount_due": 75000,
            "currency": "INR",
            "receipt": "rcpt_live_001",
            "status": "created",
            "attempts": 0,
            "notes": {
                "session_id": "sess_live_1",
                "merchant_id": "merch_live_2",
                "checkout_snapshot_hash": "hash_live_3",
            },
            "created_at": 1700000050,
        }
        return httpx.Response(200, json=response_body)

    mock_transport = httpx.MockTransport(mock_handler)
    settings = Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_key_id"),
        razorpay_key_secret=SecretStr("rzp_test_key_secret"),
        razorpay_webhook_secret=SecretStr("rzp_test_whsec"),
        razorpay_base_url="https://api.razorpay.com",
    )

    client = httpx.Client(
        transport=mock_transport,
        base_url=settings.razorpay_base_url,
        auth=(settings.razorpay_key_id.get_secret_value(), settings.razorpay_key_secret.get_secret_value()),
    )
    adapter = build_razorpay_adapter(settings, http_client=client)

    assert isinstance(adapter, LiveRazorpayAdapter)
    assert adapter.is_mock is False

    req = RazorpayOrderRequest(
        amount_minor=75000,
        currency="INR",
        receipt="rcpt_live_001",
        notes=RazorpayOrderNotes(
            session_id="sess_live_1",
            merchant_id="merch_live_2",
            checkout_snapshot_hash="hash_live_3",
        ),
    )

    order = adapter.create_order(req)

    # Verify request mapping
    assert len(captured_requests) == 1
    sent_request = captured_requests[0]
    assert sent_request.method == "POST"
    assert sent_request.url.path == "/v1/orders"
    assert "authorization" in sent_request.headers

    sent_body = json.loads(sent_request.content.decode("utf-8"))
    assert sent_body["amount"] == 75000
    assert sent_body["currency"] == "INR"
    assert sent_body["receipt"] == "rcpt_live_001"
    assert sent_body["notes"]["session_id"] == "sess_live_1"
    assert sent_body["notes"]["merchant_id"] == "merch_live_2"

    # Verify response parsed into strict Pydantic model
    assert order.id == "order_live_123456"
    assert order.amount_minor == 75000
    assert order.currency == "INR"
    assert order.status == "created"
    assert order.receipt == "rcpt_live_001"
    assert order.created_at_unix == 1700000050


def test_live_adapter_api_error_handling() -> None:
    """Verify HTTP 400 from Razorpay triggers typed RazorpayApiError with details."""
    def mock_error_handler(request: httpx.Request) -> httpx.Response:
        error_body = {
            "error": {
                "code": "BAD_REQUEST_ERROR",
                "description": "amount must be at least 100",
                "field": "amount",
            }
        }
        return httpx.Response(400, json=error_body)

    mock_transport = httpx.MockTransport(mock_error_handler)
    settings = Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_key_id"),
        razorpay_key_secret=SecretStr("rzp_test_key_secret"),
        razorpay_webhook_secret=SecretStr("rzp_test_whsec"),
    )
    client = httpx.Client(transport=mock_transport, base_url=settings.razorpay_base_url)
    adapter = LiveRazorpayAdapter(settings, http_client=client)

    req = RazorpayOrderRequest(
        amount_minor=50,
        currency="INR",
        receipt="rcpt_err",
        notes=RazorpayOrderNotes(
            session_id="s1",
            merchant_id="m1",
            checkout_snapshot_hash="h1",
        ),
    )

    with pytest.raises(RazorpayApiError) as exc_info:
        adapter.create_order(req)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "BAD_REQUEST_ERROR"
    assert "amount must be at least 100" in str(exc_info.value.error_description)


def test_live_adapter_transport_error_handling() -> None:
    """Verify transport connectivity failure triggers RazorpayTransportError."""
    def mock_transport_failure(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Network unreachable")

    mock_transport = httpx.MockTransport(mock_transport_failure)
    settings = Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_key_id"),
        razorpay_key_secret=SecretStr("rzp_test_key_secret"),
        razorpay_webhook_secret=SecretStr("rzp_test_whsec"),
    )
    client = httpx.Client(transport=mock_transport, base_url=settings.razorpay_base_url)
    adapter = LiveRazorpayAdapter(settings, http_client=client)

    req = RazorpayOrderRequest(
        amount_minor=10000,
        currency="INR",
        receipt="rcpt_err",
        notes=RazorpayOrderNotes(
            session_id="s1",
            merchant_id="m1",
            checkout_snapshot_hash="h1",
        ),
    )

    with pytest.raises(RazorpayTransportError) as exc_info:
        adapter.create_order(req)

    assert "HTTP transport failure" in str(exc_info.value)
