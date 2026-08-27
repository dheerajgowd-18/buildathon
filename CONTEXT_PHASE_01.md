# CONTEXT_PHASE_01

## 1. Phase Identity
- **Phase Number**: 01
- **Phase Name**: Repository Scaffold, Core Contracts, Razorpay Adapter & Webhook Security
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-27
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 01 delivers the foundational repository architecture, strict Pydantic v2 data models, cryptographic state hashing, a dual-mode Razorpay adapter (offline mock and live test-mode client), raw-body HMAC SHA256 webhook signature verification, and a FastAPI application with health check and webhook ingest endpoints. All 44 unit and integration tests pass deterministically without network access or real credentials.

## 3. Repository State
- **Git Initialized**: Yes (`git init -b main`)
- **Branch Name**: `main`
- **Commit Hash**: `NO_COMMIT_YET`
- **Staging Status**: All phase 01 files staged (`git add -A`), ready for human reviewer commit upon approval.

## 4. Exact File Tree
```
merchantos-ai/
  .env.example
  .gitignore
  CONTEXT_PHASE_01.md
  pyproject.toml
  README.md
  REVIEW_PHASE_01.md
  apps/
    api/
      merchantos_api/
        __init__.py
        deps.py
        main.py
        routers/
          __init__.py
          health.py
          webhooks.py
  core/
    merchantos_core/
      __init__.py
      config.py
      contracts.py
      hashing.py
  integrations/
    razorpay/
      merchantos_razorpay/
        __init__.py
        adapter.py
        webhook.py
  tests/
    __init__.py
    conftest.py
    integration/
      __init__.py
      test_health_endpoint.py
      test_webhook_endpoint.py
    unit/
      __init__.py
      test_contracts.py
      test_hashing.py
      test_hmac.py
      test_live_adapter_request_mapping.py
      test_mock_adapter.py
      test_settings.py
```

## 5. Dependencies
### Declared Dependencies (`pyproject.toml`):
- `fastapi`
- `uvicorn`
- `pydantic>=2.0`
- `pydantic-settings`
- `httpx`

### Declared Dev Dependencies:
- `pytest`

### Installed Versions:
- `fastapi`: 0.141.1
- `uvicorn`: 0.52.4
- `pydantic`: 2.13.4
- `pydantic-core`: 2.46.4
- `pydantic-settings`: 2.15.0
- `httpx`: 0.28.1
- `pytest`: 9.1.1
- `python`: 3.13.5

## 6. Environment Variables
All variables are read via `pydantic-settings` in `merchantos_core.config.Settings`:
- `RAZORPAY_USE_MOCK` (`bool`, default: `True`): Toggles between deterministic offline mock adapter and live HTTP adapter.
- `RAZORPAY_KEY_ID` (`SecretStr | None`, default: `None`): Razorpay API key identifier. Mandatory when `RAZORPAY_USE_MOCK=False`.
- `RAZORPAY_KEY_SECRET` (`SecretStr | None`, default: `None`): Razorpay API key secret. Mandatory when `RAZORPAY_USE_MOCK=False`.
- `RAZORPAY_WEBHOOK_SECRET` (`SecretStr | None`, default: `None`): Secret used to compute and verify HMAC SHA256 webhook signatures. Mandatory when `RAZORPAY_USE_MOCK=False`.
- `RAZORPAY_BASE_URL` (`str`, default: `"https://api.razorpay.com"`): Base URL for Razorpay API requests.
- `RAZORPAY_REQUEST_TIMEOUT_SECONDS` (`float`, default: `10.0`): HTTP request timeout in seconds.

## 7. Public Interfaces Created

### 1. `Settings`
- **Import Path**: `merchantos_core.config.Settings` (or `merchantos_core.Settings`)
- **Purpose**: Type-safe configuration management reading environment variables with fail-fast credential validation for live mode.
- **Key Signatures**:
  - `Settings(razorpay_use_mock: bool = True, ...) -> Settings`
  - `validate_live_credentials() -> Settings` (model validator)
  - `get_effective_webhook_secret() -> SecretStr`

### 2. `CheckoutSnapshot` & `CheckoutLineItem`
- **Import Path**: `merchantos_core.contracts.CheckoutSnapshot`, `merchantos_core.contracts.CheckoutLineItem`
- **Purpose**: Immutable representations of checkout session terms and items with integer paise amounts.
- **Key Signatures**:
  - `CheckoutLineItem(sku_id: str, name: str, quantity: int, unit_amount_minor: int, line_total_minor: int)`
  - `CheckoutSnapshot(session_id: str, merchant_id: str, currency: CurrencyINR, amount_minor: int, line_items: list[CheckoutLineItem], final_state_hash: str | None = None)`
  - `CheckoutSnapshot.compute_content_hash() -> str`

### 3. `RazorpayOrderRequest` & `RazorpayOrder`
- **Import Path**: `merchantos_core.contracts.RazorpayOrderRequest`, `merchantos_core.contracts.RazorpayOrder`, `merchantos_core.contracts.RazorpayOrderNotes`
- **Purpose**: Strictly typed request and response contracts for Razorpay order lifecycle.
- **Key Signatures**:
  - `RazorpayOrderRequest(amount_minor: int, currency: CurrencyINR, receipt: str, notes: RazorpayOrderNotes)`
  - `RazorpayOrder(id: str, amount_minor: int, currency: CurrencyINR, status: RazorpayOrderStatus, receipt: str | None, created_at_unix: int | None)`

### 4. `RazorpayPaymentEntity` & Webhook Events
- **Import Path**: `merchantos_core.contracts.RazorpayPaymentEntity`, `RazorpayPaymentCapturedEvent`, `RazorpayPaymentFailedEvent`, `UnknownWebhookEvent`
- **Purpose**: Strictly typed representations of incoming Razorpay payment entities and discriminated webhook payloads.
- **Key Signatures**:
  - `RazorpayPaymentEntity(id: str, order_id: str, amount_minor: int, currency: CurrencyINR, status: RazorpayPaymentStatus, error_code: str | None, error_description: str | None)`
  - `RazorpayPaymentCapturedEvent(event: Literal["payment.captured"], payload: RazorpayWebhookPaymentPayload)`
  - `RazorpayPaymentFailedEvent(event: Literal["payment.failed"], payload: RazorpayWebhookPaymentPayload)`
  - `UnknownWebhookEvent(event: str, raw_body_sha256: str)`

### 5. Hashing Utilities
- **Import Path**: `merchantos_core.hashing.sha256_hex`, `merchantos_core.hashing.canonical_checkout_hash`
- **Purpose**: Deterministic SHA256 hex digest computation over raw bytes and canonical checkout snapshots.
- **Key Signatures**:
  - `sha256_hex(data: bytes) -> str`
  - `canonical_checkout_hash(snapshot: CheckoutSnapshot) -> str`

### 6. Razorpay Adapters & Factory
- **Import Path**: `merchantos_razorpay.adapter.build_razorpay_adapter`, `MockRazorpayAdapter`, `LiveRazorpayAdapter`, `RazorpayAdapterBase`
- **Purpose**: Interface abstraction for order creation with deterministic offline simulation and live httpx transport.
- **Key Signatures**:
  - `build_razorpay_adapter(settings: Settings, http_client: httpx.Client | None = None) -> RazorpayAdapterBase`
  - `RazorpayAdapterBase.create_order(request: RazorpayOrderRequest) -> RazorpayOrder`
  - `MockRazorpayAdapter.generate_mock_signed_payment_captured(...) -> tuple[bytes, str]`
  - `MockRazorpayAdapter.generate_mock_signed_payment_failed(...) -> tuple[bytes, str]`

### 7. Webhook Verification & Processor
- **Import Path**: `merchantos_razorpay.webhook.compute_webhook_signature`, `verify_webhook_signature`, `parse_webhook_event`, `process_webhook_payload`, `WebhookProcessResult`
- **Purpose**: HMAC SHA256 signature computation/verification and strict webhook payload parsing.
- **Key Signatures**:
  - `compute_webhook_signature(raw_body: bytes, secret: SecretStr) -> str`
  - `verify_webhook_signature(raw_body: bytes, signature_header: str | None, secret: SecretStr) -> bool`
  - `parse_webhook_event(raw_body: bytes) -> RazorpayPaymentCapturedEvent | RazorpayPaymentFailedEvent | UnknownWebhookEvent`
  - `process_webhook_payload(raw_body: bytes, signature_header: str | None, secret: SecretStr) -> WebhookProcessResult`

### 8. FastAPI Application Factory
- **Import Path**: `merchantos_api.main.create_app`, `merchantos_api.main.app`
- **Purpose**: App factory constructing the FastAPI service configured with `/healthz` and `/webhooks/razorpay` endpoints.
- **Key Signatures**:
  - `create_app(settings: Settings | None = None) -> FastAPI`

## 8. Key Design Decisions
1. **Raw Body Before JSON Parsing**: In `POST /webhooks/razorpay`, `await request.body()` is retrieved before any JSON deserialization. Signature verification is performed on the exact raw bytes to prevent header tampering or whitespace malleability attacks.
2. **Strict Extra Rules**: Internal models enforce `extra="forbid"` to prevent unrecognized fields from leaking into domain logic. Inbound webhook/response models enforce `extra="ignore"` to remain resilient against future upstream Razorpay schema additions while validating mandatory fields strictly.
3. **No Floats for Money**: All monetary quantities are strictly typed as integer paise (`amount_minor: int = Field(ge=0)`). Serialization aliases map `amount_minor` to Razorpay's expected `amount` integer field.
4. **Zero Untyped Dictionaries**: Discriminated unions and strictly typed models (`UnknownWebhookEvent`) are used instead of `dict` or `Any` throughout the codebase.
5. **Deterministic Mock Webhooks**: Mock adapter provides helper methods to produce cryptographically valid signed payloads using the effective mock secret, enabling full offline integration testing.

## 9. Security Controls
- **HMAC Verification**: Uses HMAC SHA256 hex digest computed over the raw request payload bytes.
- **Constant-Time Comparison**: Signature verification uses `hmac.compare_digest` to prevent timing attacks.
- **Secret Masking**: All secrets utilize `pydantic.SecretStr`, ensuring secrets are masked in `__repr__`, `__str__`, logs, error traces, and API responses.
- **Mock Fallback**: A dedicated constant `DEFAULT_MOCK_WEBHOOK_SECRET` is used strictly in mock mode, allowing offline testing without real credentials.
- **Fail-Fast Validation**: When `RAZORPAY_USE_MOCK=False`, `Settings` validator immediately raises a `ValueError` if `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, or `RAZORPAY_WEBHOOK_SECRET` is missing or empty.

## 10. Test Evidence Summary
- **Pytest Command**: `pytest -q`
- **Total Tests**: 44
- **Passed**: 44
- **Failed**: 0
- **Errors**: 0
- **Skipped**: 0
- **Exit Code**: 0

*(Full unedited test output is recorded in `REVIEW_PHASE_01.md`).*

## 11. Known Limitations
- No persistence layer / database integration (intentionally deferred per Phase 01 scope).
- No money movement or captured payment settlement logic executed on webhook reception (deferred to CommerceProof / order execution phase).
- Live adapter tested with `httpx.MockTransport`; live Razorpay sandbox network calls not made during CI/unit test execution.

## 12. Phase 2 Handoff
Phase 2 (Synthetic Data Generator and pre-computation script) can safely build upon this foundation.

### Safe Reusable Modules & Import Paths:
- `from merchantos_core.contracts import CheckoutSnapshot, CheckoutLineItem, CurrencyINR`
- `from merchantos_core.hashing import canonical_checkout_hash, sha256_hex`
- `from merchantos_core.config import Settings`
- `from merchantos_razorpay.adapter import build_razorpay_adapter, MockRazorpayAdapter`
- `from merchantos_razorpay.webhook import compute_webhook_signature, verify_webhook_signature, process_webhook_payload`

### Testing & Packaging Assumptions:
- All new packages must be declared in `pyproject.toml` under `[tool.setuptools.packages.find] where = [...]`.
- Tests must be placed in `tests/unit/` or `tests/integration/` and named `test_*.py`.
- Run tests via `pytest -q` from repository root.
- Keep money values strictly in integer minor units (paise). Never use floats.
- Maintain `extra="forbid"` on internal domain contracts and avoid `Any` / `dict` in public types.

## 13. Commands

### Create Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Install Dependencies
```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### Run Tests
```bash
pytest -q
```

### Run FastAPI Application
```bash
uvicorn merchantos_api.main:app --reload
```

## 14. Ambiguities Resolved
1. **Line Items in CheckoutSnapshot**: Requirement stated empty line items should be handled according to chosen rule. Decision: enforced `line_items: list[CheckoutLineItem] = Field(min_length=1)` because an empty checkout snapshot cannot represent a valid agreed commerce transaction.
2. **Webhook Payload Nesting**: Razorpay webhooks send entity nested under `payload.payment.entity`. The contract specifies `RazorpayWebhookPaymentPayload(entity: RazorpayPaymentEntity)`. Decision: implemented a pre-validator on `RazorpayWebhookPaymentPayload` that normalizes both direct `{"entity": ...}` and nested `{"payment": {"entity": ...}}` into `entity: RazorpayPaymentEntity` seamlessly.
3. **Unknown Webhook Events**: Required typed representation without untyped JSON. Decision: defined `UnknownWebhookEvent(event: str, raw_body_sha256: str)` which captures the event type string and SHA256 hex digest of the raw body bytes without exposing raw untyped dictionaries.
