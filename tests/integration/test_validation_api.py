"""Integration tests for Validation Center API endpoints and runner execution."""

import asyncio
import json
import time

from fastapi.testclient import TestClient
import httpx
from pydantic import SecretStr
import pytest

from merchantos_api.main import create_app
from merchantos_core.config import Settings
from merchantos_core.validation.checks import check_live_llm, check_live_razorpay
from merchantos_core.validation.runner import ValidationRunner


def test_validation_page_renders_200() -> None:
    """GET /validation renders 200 with Validation Center title and controls."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/validation")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "System Validation Center" in res.text
    assert "Run hermetic suite" in res.text


def test_post_validation_run_hermetic_and_report_results() -> None:
    """POST /api/validation/run executes hermetic suite and populates report."""
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    runner = ValidationRunner()
    report = runner.run(scope="hermetic", settings=settings)

    assert report.overall_status == "pass"
    assert report.scope == "hermetic"
    assert len(report.results) == 6

    check_ids = [r.check_id for r in report.results]
    assert "hmac_webhook_roundtrip" in check_ids
    assert "canonical_hash_determinism" in check_ids
    assert "commerceproof_clamp" in check_ids
    assert "ground_truth_leakage_scan" in check_ids
    assert "negotiation_determinism" in check_ids
    assert "ledger_subscription_roundtrip" in check_ids


class StubRequest:
    """Stub request that simulates client connection state."""

    def __init__(self, disconnected: bool = False) -> None:
        self.disconnected = disconnected

    async def is_disconnected(self) -> bool:
        return self.disconnected


@pytest.mark.anyio
async def test_validation_sse_stream() -> None:
    """GET /api/validation/events connects and streams event check data."""
    from merchantos_api.routers.validation import sse_validation_events

    req = StubRequest()
    response = await sse_validation_events(request=req)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    iterator = response.body_iterator
    first_chunk = await asyncio.wait_for(anext(iterator), timeout=5.0)
    assert ": connected" in first_chunk
    await iterator.aclose()


def test_live_checks_skipped_when_mock() -> None:
    """Live checks return status 'skipped' when mock mode is enabled or keys missing."""
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)

    r_rzp = check_live_razorpay(settings)
    assert r_rzp.status == "skipped"
    assert "Skipped" in r_rzp.detail

    r_llm = check_live_llm(settings)
    assert r_llm.status == "skipped"
    assert "Skipped" in r_llm.detail


def test_live_razorpay_with_mock_transport() -> None:
    """check_live_razorpay creates order, fetches order, and verifies 100 paise amount."""
    settings = Settings(
        _env_file=None,
        razorpay_use_mock=False,
        razorpay_key_id="rzp_test_mock_123",
        razorpay_key_secret=SecretStr("secret_mock_xyz"),
        razorpay_webhook_secret=SecretStr("whsec_mock_123"),
    )

    def mock_handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and "/v1/orders" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"id": "order_mock_test_01", "amount": 100, "currency": "INR", "status": "created"},
            )
        elif request.method == "GET" and "/v1/orders/order_mock_test_01" in str(request.url):
            return httpx.Response(
                status_code=200,
                json={"id": "order_mock_test_01", "amount": 100, "currency": "INR", "status": "created"},
            )
        return httpx.Response(status_code=404, json={"error": "not found"})

    client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    result = check_live_razorpay(settings=settings, http_client=client)

    assert result.status == "pass"
    assert result.category == "live_razorpay"
    assert "order_mock_test_01" in result.evidence_json


def test_live_llm_with_stubbed_provider() -> None:
    """check_live_llm succeeds when provider ping returns content."""
    settings = Settings(
        _env_file=None,
        llm_use_mock=False,
        llm_api_key=SecretStr("sk-test-key-mock-12345"),
    )

    class StubbedLLMProvider:
        def ping(self) -> str:
            return "READY"

    result = check_live_llm(settings=settings, provider=StubbedLLMProvider())
    assert result.status == "pass"
    assert result.category == "live_llm"
    assert "READY" in result.evidence_json


def test_validation_report_contains_no_secrets() -> None:
    """Serialized validation report never contains substrings of secret keys."""
    raw_rzp_secret = "super_secret_rzp_private_key_999"
    raw_llm_secret = "super_secret_llm_private_key_888"

    settings = Settings(
        _env_file=None,
        razorpay_use_mock=False,
        razorpay_key_id="rzp_live_test_id",
        razorpay_key_secret=SecretStr(raw_rzp_secret),
        razorpay_webhook_secret=SecretStr("whsec_mock_private_999"),
        llm_use_mock=False,
        llm_api_key=SecretStr(raw_llm_secret),
    )

    runner = ValidationRunner()
    report = runner.run(scope="all", settings=settings)
    report_json = report.model_dump_json()

    assert raw_rzp_secret not in report_json
    assert raw_llm_secret not in report_json


def test_overview_renders_proof_strip() -> None:
    """GET / renders the validation proof strip under the KPI band."""
    app = create_app(settings=Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True))
    client = TestClient(app)

    res = client.get("/")
    assert res.status_code == 200
    assert "Hermetic suite:" in res.text
    assert "Last live Razorpay:" in res.text
    assert "Last live LLM:" in res.text
    assert "Open Validation" in res.text
