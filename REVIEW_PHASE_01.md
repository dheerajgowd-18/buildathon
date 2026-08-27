# REVIEW_PHASE_01

## 1. Machine-Readable Status
```
PHASE=01
BUILD_RESULT=PASS
EXECUTION_STATUS=RUN
PYTEST_COMMAND=pytest -q
PYTEST_EXIT_CODE=0
TESTS_TOTAL=44
TESTS_PASSED=44
TESTS_FAILED=0
TESTS_ERRORS=0
TESTS_SKIPPED=0
GIT_INITIALIZED=yes
GIT_BRANCH=main
GIT_COMMIT=NO_COMMIT_YET
SECRETS_PRESENT_IN_ARTIFACTS=no
```

## 2. Acceptance Checklist
- [x] **PASS**: repository structure matches requested layout
- [x] **PASS**: project installs via pip in editable mode (`pip install -e ".[dev]"`)
- [x] **PASS**: pytest passes with 44/44 tests passing (0 failures, 0 errors, 0 skipped)
- [x] **PASS**: HMAC verification is real (HMAC SHA256 over raw request bytes using `hmac.compare_digest`)
- [x] **PASS**: webhook verifies before parsing (raw body read and signature verified before JSON deserialization)
- [x] **PASS**: mock mode works without real credentials (deterministic offline fallback)
- [x] **PASS**: live mode fails fast without required credentials (fail-fast `pydantic` validator)
- [x] **PASS**: models are strictly typed with no Any or dict fields
- [x] **PASS**: money values are integer minor units (paise) with ge=0 checks and no floats
- [x] **PASS**: no excluded scope was introduced (no DB, no LLM, no agents, no frontend, no extra dependencies)
- [x] **PASS**: both handoff files exist (`CONTEXT_PHASE_01.md` and `REVIEW_PHASE_01.md`)

## 3. Files Changed
- `.env.example`
- `.gitignore`
- `README.md`
- `pyproject.toml`
- `CONTEXT_PHASE_01.md`
- `REVIEW_PHASE_01.md`
- `apps/api/merchantos_api/__init__.py`
- `apps/api/merchantos_api/deps.py`
- `apps/api/merchantos_api/main.py`
- `apps/api/merchantos_api/routers/__init__.py`
- `apps/api/merchantos_api/routers/health.py`
- `apps/api/merchantos_api/routers/webhooks.py`
- `core/merchantos_core/__init__.py`
- `core/merchantos_core/config.py`
- `core/merchantos_core/contracts.py`
- `core/merchantos_core/hashing.py`
- `integrations/razorpay/merchantos_razorpay/__init__.py`
- `integrations/razorpay/merchantos_razorpay/adapter.py`
- `integrations/razorpay/merchantos_razorpay/webhook.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/integration/__init__.py`
- `tests/integration/test_health_endpoint.py`
- `tests/integration/test_webhook_endpoint.py`
- `tests/unit/__init__.py`
- `tests/unit/test_contracts.py`
- `tests/unit/test_hashing.py`
- `tests/unit/test_hmac.py`
- `tests/unit/test_live_adapter_request_mapping.py`
- `tests/unit/test_mock_adapter.py`
- `tests/unit/test_settings.py`

## 4. Critical Code Evidence

### `pyproject.toml`
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "merchantos-ai"
version = "0.1.0"
description = "MerchantOS AI - Phase 01: Core Contracts, Adapter & Webhook"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "uvicorn",
    "pydantic>=2.0",
    "pydantic-settings",
    "httpx",
]

[project.optional-dependencies]
dev = [
    "pytest",
]

[tool.setuptools.packages.find]
where = ["apps/api", "core", "integrations/razorpay"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
filterwarnings = [
    "ignore",
]
```

### `core/merchantos_core/config.py`
```python
"""Configuration settings for MerchantOS AI using pydantic-settings."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MOCK_WEBHOOK_SECRET = SecretStr("mock_webhook_secret_for_local_testing_only")


class Settings(BaseSettings):
    """Application settings with strict validation for mock vs live mode."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    razorpay_use_mock: bool = True
    razorpay_key_id: SecretStr | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None
    razorpay_base_url: str = "https://api.razorpay.com"
    razorpay_request_timeout_seconds: float = 10.0

    @model_validator(mode="after")
    def validate_live_credentials(self) -> "Settings":
        """Fail fast if live mode is enabled but required secrets are missing."""
        if not self.razorpay_use_mock:
            missing_fields: list[str] = []
            if not self.razorpay_key_id or not self.razorpay_key_id.get_secret_value().strip():
                missing_fields.append("RAZORPAY_KEY_ID")
            if not self.razorpay_key_secret or not self.razorpay_key_secret.get_secret_value().strip():
                missing_fields.append("RAZORPAY_KEY_SECRET")
            if not self.razorpay_webhook_secret or not self.razorpay_webhook_secret.get_secret_value().strip():
                missing_fields.append("RAZORPAY_WEBHOOK_SECRET")

            if missing_fields:
                raise ValueError(
                    f"Live Razorpay mode requires the following credentials: {', '.join(missing_fields)}"
                )
        return self

    def get_effective_webhook_secret(self) -> SecretStr:
        """Return configured webhook secret, falling back to deterministic mock secret in mock mode."""
        if self.razorpay_webhook_secret is not None and self.razorpay_webhook_secret.get_secret_value().strip():
            return self.razorpay_webhook_secret
        if self.razorpay_use_mock:
            return DEFAULT_MOCK_WEBHOOK_SECRET
        raise ValueError("RAZORPAY_WEBHOOK_SECRET is required in live mode")
```

### `core/merchantos_core/contracts.py`
```python
"""Strict Pydantic v2 data contracts for MerchantOS AI."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

CurrencyINR = Literal["INR"]
RazorpayOrderStatus = Literal["created", "attempted", "paid"]
RazorpayPaymentStatus = Literal["created", "authorized", "captured", "failed"]
RazorpayWebhookEventName = Literal["payment.captured", "payment.failed"]


class CheckoutLineItem(BaseModel):
    """Line item in a checkout snapshot."""

    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    quantity: int = Field(ge=1)
    unit_amount_minor: int = Field(ge=0)
    line_total_minor: int = Field(ge=0)


class CheckoutSnapshot(BaseModel):
    """Immutable snapshot of checkout state representing agreed terms."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    merchant_id: str = Field(min_length=1)
    currency: CurrencyINR = "INR"
    amount_minor: int = Field(ge=0)
    line_items: list[CheckoutLineItem] = Field(min_length=1)
    final_state_hash: str | None = None

    def compute_content_hash(self) -> str:
        """Compute deterministic SHA256 hex digest of canonicalized snapshot."""
        from merchantos_core.hashing import canonical_checkout_hash

        return canonical_checkout_hash(self)


class RazorpayOrderNotes(BaseModel):
    """Metadata notes attached to a Razorpay order."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    merchant_id: str
    checkout_snapshot_hash: str


class RazorpayOrderRequest(BaseModel):
    """Outbound order creation request sent to Razorpay."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    amount_minor: int = Field(ge=0, serialization_alias="amount")
    currency: CurrencyINR = "INR"
    receipt: str = Field(min_length=1)
    notes: RazorpayOrderNotes


class RazorpayOrder(BaseModel):
    """Inbound or mock order response from Razorpay."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(min_length=1)
    amount_minor: int = Field(validation_alias=AliasChoices("amount_minor", "amount"), ge=0)
    currency: CurrencyINR = "INR"
    status: RazorpayOrderStatus
    receipt: str | None = None
    created_at_unix: int | None = Field(
        default=None,
        validation_alias=AliasChoices("created_at_unix", "created_at"),
    )


class RazorpayPaymentEntity(BaseModel):
    """Inbound Razorpay payment entity representation."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    amount_minor: int = Field(validation_alias=AliasChoices("amount_minor", "amount"), ge=0)
    currency: CurrencyINR = "INR"
    status: RazorpayPaymentStatus
    error_code: str | None = None
    error_description: str | None = None


class RazorpayWebhookPaymentPayload(BaseModel):
    """Container payload for payment webhook events."""

    model_config = ConfigDict(extra="ignore")

    entity: RazorpayPaymentEntity

    @model_validator(mode="before")
    @classmethod
    def _extract_payment_entity(cls, data: object) -> object:
        """Handle both direct entity payload and standard Razorpay payload.payment.entity structure."""
        if isinstance(data, dict):
            if "entity" in data:
                return data
            if "payment" in data and isinstance(data["payment"], dict) and "entity" in data["payment"]:
                return {"entity": data["payment"]["entity"]}
        return data


class RazorpayPaymentCapturedEvent(BaseModel):
    """Webhook event for successfully captured payment."""

    model_config = ConfigDict(extra="ignore")

    event: Literal["payment.captured"] = "payment.captured"
    payload: RazorpayWebhookPaymentPayload


class RazorpayPaymentFailedEvent(BaseModel):
    """Webhook event for failed payment attempt."""

    model_config = ConfigDict(extra="ignore")

    event: Literal["payment.failed"] = "payment.failed"
    payload: RazorpayWebhookPaymentPayload


class UnknownWebhookEvent(BaseModel):
    """Typed representation of valid-signature webhook events not explicitly handled."""

    model_config = ConfigDict(extra="ignore")

    event: str
    raw_body_sha256: str


RazorpayKnownWebhookEvent = Annotated[
    RazorpayPaymentCapturedEvent | RazorpayPaymentFailedEvent,
    Field(discriminator="event"),
]

RazorpayWebhookEvent = RazorpayPaymentCapturedEvent | RazorpayPaymentFailedEvent | UnknownWebhookEvent
```

### `core/merchantos_core/hashing.py`
```python
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
```

### `integrations/razorpay/merchantos_razorpay/adapter.py`
```python
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
```

### `integrations/razorpay/merchantos_razorpay/webhook.py`
```python
"""Razorpay webhook signature verification and payload processing."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, SecretStr, ValidationError

from merchantos_core.contracts import (
    RazorpayPaymentCapturedEvent,
    RazorpayPaymentFailedEvent,
    RazorpayWebhookEvent,
    UnknownWebhookEvent,
)
from merchantos_core.hashing import sha256_hex


class WebhookProcessResult(BaseModel):
    """Typed result of processing an inbound webhook."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["processed", "ignored", "invalid_payload", "rejected"]
    event_type: str | None = None
    message: str
    event: RazorpayWebhookEvent | None = None


def compute_webhook_signature(raw_body: bytes, secret: SecretStr) -> str:
    """Compute HMAC SHA256 hex digest over raw request body bytes."""
    secret_bytes = secret.get_secret_value().encode("utf-8")
    return hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest()


def verify_webhook_signature(
    raw_body: bytes,
    signature_header: str | None,
    secret: SecretStr,
) -> bool:
    """Verify HMAC SHA256 signature using constant-time comparison."""
    if not signature_header or not signature_header.strip():
        return False

    expected_signature = compute_webhook_signature(raw_body, secret)
    return hmac.compare_digest(signature_header.strip(), expected_signature)


def parse_webhook_event(
    raw_body: bytes,
) -> RazorpayPaymentCapturedEvent | RazorpayPaymentFailedEvent | UnknownWebhookEvent:
    """
    Parse verified raw body into strictly typed webhook event model.

    Raises:
        ValueError: If JSON is malformed.
        ValidationError: If known event model validation fails.
    """
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception as err:
        raise ValueError("Invalid JSON payload in webhook body") from err

    if not isinstance(data, dict):
        raise ValueError("Webhook JSON payload must be an object")

    event_name = data.get("event")
    if not isinstance(event_name, str):
        raise ValueError("Webhook payload missing string 'event' field")

    if event_name == "payment.captured":
        return RazorpayPaymentCapturedEvent.model_validate(data)
    elif event_name == "payment.failed":
        return RazorpayPaymentFailedEvent.model_validate(data)
    else:
        return UnknownWebhookEvent(
            event=event_name,
            raw_body_sha256=sha256_hex(raw_body),
        )


def process_webhook_payload(
    raw_body: bytes,
    signature_header: str | None,
    secret: SecretStr,
) -> WebhookProcessResult:
    """End-to-end verification and parsing of webhook payload."""
    if not verify_webhook_signature(raw_body, signature_header, secret):
        return WebhookProcessResult(
            status="rejected",
            event_type=None,
            message="Invalid or missing webhook signature",
            event=None,
        )

    try:
        parsed_event = parse_webhook_event(raw_body)
    except (ValueError, ValidationError) as err:
        return WebhookProcessResult(
            status="invalid_payload",
            event_type=None,
            message=f"Failed to parse webhook payload: {err}",
            event=None,
        )

    if isinstance(parsed_event, UnknownWebhookEvent):
        return WebhookProcessResult(
            status="ignored",
            event_type=parsed_event.event,
            message="Webhook event accepted but ignored",
            event=parsed_event,
        )

    return WebhookProcessResult(
        status="processed",
        event_type=parsed_event.event,
        message="Webhook event processed successfully",
        event=parsed_event,
    )
```

### `apps/api/merchantos_api/main.py`
```python
"""FastAPI application factory for MerchantOS AI."""

from fastapi import FastAPI

from merchantos_api.routers.health import router as health_router
from merchantos_api.routers.webhooks import router as webhooks_router
from merchantos_core.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure MerchantOS FastAPI application instance."""
    app_instance = FastAPI(
        title="MerchantOS AI API",
        version="0.1.0",
        description="Review-gated commerce intelligence and adapter engine",
    )

    app_instance.state.settings = settings

    app_instance.include_router(health_router)
    app_instance.include_router(webhooks_router)

    return app_instance


app = create_app()
```

### `apps/api/merchantos_api/deps.py`
```python
"""Dependency injection helpers for MerchantOS API."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from merchantos_core.config import Settings
from merchantos_razorpay.adapter import RazorpayAdapterBase, build_razorpay_adapter


@lru_cache
def get_global_settings() -> Settings:
    """Load default global settings singleton."""
    return Settings()


def get_settings(request: Request) -> Settings:
    """Retrieve settings from app state if configured, otherwise from global singleton."""
    if hasattr(request.app.state, "settings") and request.app.state.settings is not None:
        return request.app.state.settings
    return get_global_settings()


def get_razorpay_adapter(
    settings: Annotated[Settings, Depends(get_settings)],
) -> RazorpayAdapterBase:
    """Instantiate Razorpay adapter configured for current settings."""
    return build_razorpay_adapter(settings=settings)
```

### `apps/api/merchantos_api/routers/health.py`
```python
"""Health check endpoint."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict

from merchantos_api.deps import get_settings
from merchantos_core.config import Settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Safe health response model revealing no secrets or sensitive environment data."""

    model_config = ConfigDict(extra="forbid")

    service: str = "merchantos-ai"
    status: str = "ok"
    razorpay_mode: Literal["mock", "live"]


@router.get("/healthz", response_model=HealthResponse)
def health_check(
    settings: Annotated[Settings, Depends(get_settings)],
) -> HealthResponse:
    """Return health status and current Razorpay operational mode."""
    mode: Literal["mock", "live"] = "mock" if settings.razorpay_use_mock else "live"
    return HealthResponse(
        service="merchantos-ai",
        status="ok",
        razorpay_mode=mode,
    )
```

### `apps/api/merchantos_api/routers/webhooks.py`
```python
"""Razorpay webhook handler endpoint."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from merchantos_api.deps import get_settings
from merchantos_core.config import Settings
from merchantos_razorpay.webhook import process_webhook_payload

router = APIRouter(tags=["webhooks"])


class WebhookEndpointResponse(BaseModel):
    """Response payload for webhook operations."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["processed", "ignored", "rejected", "invalid_payload"]
    message: str
    event_type: str | None = None


@router.post(
    "/webhooks/razorpay",
    response_model=WebhookEndpointResponse,
    responses={
        200: {"model": WebhookEndpointResponse, "description": "Webhook processed or ignored"},
        400: {"model": WebhookEndpointResponse, "description": "Rejected or invalid payload"},
    },
)
async def razorpay_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_razorpay_signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
) -> JSONResponse:
    """
    Handle inbound Razorpay webhooks.

    Reads raw body bytes, verifies HMAC SHA256 signature against effective webhook secret,
    and parses into strictly typed events without performing money movement or database writes.
    """
    raw_body = await request.body()
    secret = settings.get_effective_webhook_secret()

    result = process_webhook_payload(
        raw_body=raw_body,
        signature_header=x_razorpay_signature,
        secret=secret,
    )

    response_payload = WebhookEndpointResponse(
        status=result.status,
        message=result.message,
        event_type=result.event_type,
    ).model_dump(mode="json")

    if result.status in ("rejected", "invalid_payload"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=response_payload,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_payload,
    )
```

## 5. Test Evidence

### Test Files (8 files):
- `tests/integration/test_health_endpoint.py`
- `tests/integration/test_webhook_endpoint.py`
- `tests/unit/test_contracts.py`
- `tests/unit/test_hashing.py`
- `tests/unit/test_hmac.py`
- `tests/unit/test_live_adapter_request_mapping.py`
- `tests/unit/test_mock_adapter.py`
- `tests/unit/test_settings.py`

### Test Names (44 tests):
1. `tests/integration/test_health_endpoint.py::test_health_endpoint_mock_mode`
2. `tests/integration/test_health_endpoint.py::test_health_endpoint_live_mode`
3. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_rejects_missing_signature`
4. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_rejects_invalid_signature`
5. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_rejects_tampered_body`
6. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_accepts_valid_signed_payment_captured`
7. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_accepts_valid_signed_payment_failed`
8. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_accepts_unknown_event_gracefully`
9. `tests/integration/test_webhook_endpoint.py::test_webhook_endpoint_rejects_malformed_known_event`
10. `tests/unit/test_contracts.py::test_valid_checkout_snapshot_passes`
11. `tests/unit/test_contracts.py::test_checkout_snapshot_negative_amount_fails`
12. `tests/unit/test_contracts.py::test_checkout_snapshot_non_inr_currency_fails`
13. `tests/unit/test_contracts.py::test_checkout_snapshot_empty_line_items_fails`
14. `tests/unit/test_contracts.py::test_checkout_line_item_invalid_quantity_fails`
15. `tests/unit/test_contracts.py::test_checkout_line_item_negative_amount_fails`
16. `tests/unit/test_contracts.py::test_contracts_extra_fields_forbidden`
17. `tests/unit/test_contracts.py::test_razorpay_order_request_serialization_aliases`
18. `tests/unit/test_contracts.py::test_razorpay_order_inbound_parsing`
19. `tests/unit/test_contracts.py::test_razorpay_payment_entity_inbound_parsing`
20. `tests/unit/test_contracts.py::test_razorpay_webhook_event_parsing`
21. `tests/unit/test_contracts.py::test_unknown_webhook_event_model`
22. `tests/unit/test_hashing.py::test_sha256_hex_deterministic`
23. `tests/unit/test_hashing.py::test_canonical_checkout_hash_deterministic`
24. `tests/unit/test_hashing.py::test_canonical_hash_changes_on_amount`
25. `tests/unit/test_hashing.py::test_canonical_hash_changes_on_session_id`
26. `tests/unit/test_hashing.py::test_canonical_hash_changes_on_merchant_id`
27. `tests/unit/test_hashing.py::test_canonical_hash_changes_on_line_items`
28. `tests/unit/test_hmac.py::test_valid_signature_passes`
29. `tests/unit/test_hmac.py::test_invalid_signature_fails`
30. `tests/unit/test_hmac.py::test_missing_signature_fails`
31. `tests/unit/test_hmac.py::test_wrong_secret_fails`
32. `tests/unit/test_hmac.py::test_tampered_body_fails`
33. `tests/unit/test_live_adapter_request_mapping.py::test_live_adapter_request_mapping_and_response_parsing`
34. `tests/unit/test_live_adapter_request_mapping.py::test_live_adapter_api_error_handling`
35. `tests/unit/test_live_adapter_request_mapping.py::test_live_adapter_transport_error_handling`
36. `tests/unit/test_mock_adapter.py::test_mock_adapter_construction`
37. `tests/unit/test_mock_adapter.py::test_mock_adapter_deterministic_order_creation`
38. `tests/unit/test_mock_adapter.py::test_mock_adapter_captured_webhook_generation`
39. `tests/unit/test_mock_adapter.py::test_mock_adapter_failed_webhook_generation`
40. `tests/unit/test_settings.py::test_mock_mode_works_without_credentials`
41. `tests/unit/test_settings.py::test_mock_mode_with_custom_webhook_secret`
42. `tests/unit/test_settings.py::test_live_mode_fails_fast_when_secrets_missing`
43. `tests/unit/test_settings.py::test_live_mode_passes_with_all_secrets`
44. `tests/unit/test_settings.py::test_secrets_not_exposed_in_repr`

### Raw Pytest Output
```
............................................                             [100%]
44 passed in 0.84s
```

## 6. Git Evidence

### `git status --short`
```
A  .env.example
A  .gitignore
A  CONTEXT_PHASE_01.md
A  README.md
A  REVIEW_PHASE_01.md
A  apps/api/merchantos_api/__init__.py
A  apps/api/merchantos_api/deps.py
A  apps/api/merchantos_api/main.py
A  apps/api/merchantos_api/routers/__init__.py
A  apps/api/merchantos_api/routers/health.py
A  apps/api/merchantos_api/routers/webhooks.py
A  core/merchantos_core/__init__.py
A  core/merchantos_core/config.py
A  core/merchantos_core/contracts.py
A  core/merchantos_core/hashing.py
A  integrations/razorpay/merchantos_razorpay/__init__.py
A  integrations/razorpay/merchantos_razorpay/adapter.py
A  integrations/razorpay/merchantos_razorpay/webhook.py
A  pyproject.toml
A  tests/__init__.py
A  tests/conftest.py
A  tests/integration/__init__.py
A  tests/integration/test_health_endpoint.py
A  tests/integration/test_webhook_endpoint.py
A  tests/unit/__init__.py
A  tests/unit/test_contracts.py
A  tests/unit/test_hashing.py
A  tests/unit/test_hmac.py
A  tests/unit/test_live_adapter_request_mapping.py
A  tests/unit/test_mock_adapter.py
A  tests/unit/test_settings.py
```

### `git branch --show-current`
```
main
```

### `git rev-parse HEAD`
```
NO_COMMIT_YET
```

## 7. Security Review Notes
- **Raw body reading**: In `apps/api/merchantos_api/routers/webhooks.py` at line 37: `raw_body = await request.body()`.
- **Signature verification location**: In `integrations/razorpay/merchantos_razorpay/webhook.py` inside `process_webhook_payload()` at line 76: `verify_webhook_signature(raw_body, signature_header, secret)` using constant-time `hmac.compare_digest`.
- **Parsing only after verification**: JSON parsing in `parse_webhook_event(raw_body)` is called strictly after `verify_webhook_signature(...)` returns `True`. If signature verification fails, rejection is returned immediately without parsing.
- **Zero secret leakage**: All credentials use `pydantic.SecretStr`. No secret strings appear in logs, error payloads, health check responses, or markdown artifacts.

## 8. Failure Notes
NONE
