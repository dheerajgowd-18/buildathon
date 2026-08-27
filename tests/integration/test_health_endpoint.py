"""Integration tests for the /healthz endpoint."""

from fastapi.testclient import TestClient
from pydantic import SecretStr

from merchantos_api.main import create_app
from merchantos_core.config import Settings


def test_health_endpoint_mock_mode() -> None:
    """Health check in mock mode returns ok status and mock razorpay_mode without leaking secrets."""
    settings = Settings(razorpay_use_mock=True)
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "merchantos-ai"
    assert data["razorpay_mode"] == "mock"
    # Ensure no secret keys leaked in response keys
    assert "key" not in data
    assert "secret" not in data


def test_health_endpoint_live_mode() -> None:
    """Health check in live mode returns live razorpay_mode."""
    settings = Settings(
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_k1"),
        razorpay_key_secret=SecretStr("rzp_test_s1"),
        razorpay_webhook_secret=SecretStr("rzp_test_w1"),
    )
    app = create_app(settings=settings)
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "merchantos-ai"
    assert data["razorpay_mode"] == "live"
    assert "key" not in data
    assert "secret" not in data
