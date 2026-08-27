"""Razorpay adapter implementation with Mock and Live variants."""

from __future__ import annotations

from abc import ABC, abstractmethod
import hashlib
import json

import httpx

from merchantos_core.config import Settings
from merchantos_core.contracts import (
    CurrencyINR,
    RazorpayOrder,
    RazorpayOrderRequest,
)
from merchantos_razorpay.webhook import compute_webhook_signature


class RazorpayAdapterError(Exception):
    """Base exception for Razorpay adapter operations."""


class RazorpayTransportError(RazorpayAdapterError):
    """Raised when transport/network communication fails."""


class RazorpayApiError(RazorpayAdapterError):
    """Raised when Razorpay API returns an error response."""

    def __init__(
        self,
        message: str,
        status_code: int,
        error_code: str | None = None,
        error_description: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error_description = error_description


class RazorpayAdapterBase(ABC):
    """Abstract base class for Razorpay adapters."""

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        """Indicates if the adapter is running in mock mode."""

    @abstractmethod
    def create_order(self, request: RazorpayOrderRequest) -> RazorpayOrder:
        """Create a new payment order."""


class MockRazorpayAdapter(RazorpayAdapterBase):
    """Deterministic, offline mock Razorpay adapter for tests and local development."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(razorpay_use_mock=True)

    @property
    def is_mock(self) -> bool:
        return True

    def create_order(self, request: RazorpayOrderRequest) -> RazorpayOrder:
        """Deterministically create a mock Razorpay order."""
        seed_str = f"{request.receipt}:{request.notes.session_id}:{request.amount_minor}:{request.currency}"
        deterministic_hash = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()[:16]
        order_id = f"order_mock_{deterministic_hash}"

        return RazorpayOrder(
            id=order_id,
            amount_minor=request.amount_minor,
            currency=request.currency,
            status="created",
            receipt=request.receipt,
            created_at_unix=1700000000,
        )

    def generate_mock_signed_payment_captured(
        self,
        order_id: str,
        amount_minor: int,
        currency: CurrencyINR = "INR",
        payment_id: str = "pay_mock_1234567890",
    ) -> tuple[bytes, str]:
        """Generate signed raw webhook body and signature header for payment.captured."""
        payload_dict = {
            "entity": "event",
            "account_id": "acc_mock_001",
            "event": "payment.captured",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order_id,
                        "amount": amount_minor,
                        "currency": currency,
                        "status": "captured",
                        "error_code": None,
                        "error_description": None,
                    }
                }
            },
            "created_at": 1700000000,
        }
        raw_body = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        secret = self._settings.get_effective_webhook_secret()
        signature = compute_webhook_signature(raw_body, secret)
        return raw_body, signature

    def generate_mock_signed_payment_failed(
        self,
        order_id: str,
        amount_minor: int,
        currency: CurrencyINR = "INR",
        payment_id: str = "pay_mock_1234567890",
        error_code: str = "BAD_REQUEST_ERROR",
        error_description: str = "Payment failed at bank gateway",
    ) -> tuple[bytes, str]:
        """Generate signed raw webhook body and signature header for payment.failed."""
        payload_dict = {
            "entity": "event",
            "account_id": "acc_mock_001",
            "event": "payment.failed",
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order_id,
                        "amount": amount_minor,
                        "currency": currency,
                        "status": "failed",
                        "error_code": error_code,
                        "error_description": error_description,
                    }
                }
            },
            "created_at": 1700000000,
        }
        raw_body = json.dumps(payload_dict, separators=(",", ":")).encode("utf-8")
        secret = self._settings.get_effective_webhook_secret()
        signature = compute_webhook_signature(raw_body, secret)
        return raw_body, signature


class LiveRazorpayAdapter(RazorpayAdapterBase):
    """Live Razorpay adapter targeting test/live API using httpx."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        if settings.razorpay_use_mock:
            raise ValueError("LiveRazorpayAdapter cannot be instantiated when razorpay_use_mock is True")
        if not settings.razorpay_key_id or not settings.razorpay_key_secret:
            raise ValueError("LiveRazorpayAdapter requires razorpay_key_id and razorpay_key_secret")

        self._settings = settings
        auth = (
            settings.razorpay_key_id.get_secret_value(),
            settings.razorpay_key_secret.get_secret_value(),
        )
        self._client = http_client or httpx.Client(
            base_url=settings.razorpay_base_url,
            timeout=settings.razorpay_request_timeout_seconds,
            auth=auth,
        )

    @property
    def is_mock(self) -> bool:
        return False

    def create_order(self, request: RazorpayOrderRequest) -> RazorpayOrder:
        """Create order via Razorpay REST API."""
        request_body = request.model_dump(by_alias=True, mode="json")
        try:
            response = self._client.post("/v1/orders", json=request_body)
        except httpx.RequestError as err:
            raise RazorpayTransportError(f"HTTP transport failure calling Razorpay API: {err}") from err

        if response.status_code >= 400:
            error_code: str | None = None
            error_desc: str | None = None
            try:
                err_data = response.json()
                if isinstance(err_data, dict) and "error" in err_data and isinstance(err_data["error"], dict):
                    error_code = err_data["error"].get("code")
                    error_desc = err_data["error"].get("description")
            except Exception:
                pass
            raise RazorpayApiError(
                message=f"Razorpay API returned HTTP {response.status_code}",
                status_code=response.status_code,
                error_code=error_code,
                error_description=error_desc,
            )

        try:
            data = response.json()
        except Exception as err:
            raise RazorpayApiError(
                message="Razorpay API returned non-JSON response",
                status_code=response.status_code,
            ) from err

        return RazorpayOrder.model_validate(data)


def build_razorpay_adapter(
    settings: Settings,
    http_client: httpx.Client | None = None,
) -> RazorpayAdapterBase:
    """Factory to construct either Mock or Live Razorpay adapter based on settings."""
    if settings.razorpay_use_mock:
        return MockRazorpayAdapter(settings=settings)
    return LiveRazorpayAdapter(settings=settings, http_client=http_client)
