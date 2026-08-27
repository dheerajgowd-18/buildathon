# MerchantOS AI

MerchantOS AI is an agentic merchant intelligence and commerce platform.

## Phase 01: Repository Scaffold, Core Contracts, Razorpay Adapter & Webhook Security

Phase 01 delivers:
- Repository scaffolding and packaging for `merchantos_core`, `merchantos_razorpay`, and `merchantos_api`.
- Strict Pydantic v2 data contracts for checkout state representation and Razorpay order/payment/webhook events.
- Canonical checkout state hashing (`SHA256`).
- Dual-mode Razorpay adapter (deterministic mock fallback and test-mode live client using `httpx`).
- Secure webhook signature verification using HMAC SHA256 over raw request payload.
- FastAPI service with `/healthz` and `/webhooks/razorpay` endpoints.

## Local Setup

### 1. Create Virtual Environment and Install Dependencies

```bash
cd merchantos-ai
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

### 2. Run Tests

```bash
pytest -q
```

### 3. Run FastAPI Application

```bash
uvicorn merchantos_api.main:app --reload
```
