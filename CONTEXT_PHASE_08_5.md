# CONTEXT_PHASE_08_5

## 1. Phase Identity
- **Phase Number**: 08.5
- **Phase Name**: Live Integration Validation Layer (Real APIs & Swappable Providers)
- **Build Status**: PASS
- **Date / Execution Label**: 2026-08-28
- **Repository Root Path**: `d:\buildathon`

## 2. Executive Summary
Phase 08.5 finalizes MerchantOS AI's production readiness by delivering the **Live Integration Validation Layer**. This layer connects MerchantOS AI to real external APIs—specifically an **OpenAI-Compatible LLM Provider** (calling OpenAI, Grok, Groq, or open-source endpoints) and the **Real Razorpay Test-Mode REST API**—without breaking any hermetic test guarantees or architectural trust boundaries.

Key Accomplishments:
1. **OpenAI-Compatible LLM Provider (`OpenAICompatibleLLMProvider`)**:
   - Implements `AbstractLLMProvider` using the official `openai` Python SDK.
   - Enforces structured JSON output matching the strict `LLMOutput` Pydantic model (`selected_sku_id`, `proposed_price_minor`, `discount_minor`, `shipping_tier`, `rationale`).
   - Automatically handles JSON markdown fence stripping and provides graceful error types (`LLMProviderError`, `LLMParsingError`).
   - Factory function `build_llm_provider(settings)` allows seamless switching between Mock and Live LLM modes.
2. **Deterministic Fallback for Demos (Master Plan §18)**:
   - If an external LLM call times out or encounters network/authentication errors during a live evaluation, the system immediately catches the failure, reports the exact error transparently, and falls back to `MockLLMProvider` to complete the full 4-phase audit trail and checkout flow.
3. **End-to-End Live Validation CLI Script (`scripts/live_validation.py`)**:
   - Executes the complete 4-phase commerce trade lifecycle:
     - **Phase A**: Intent intake & autonomous LLM negotiation.
     - **Phase B**: CommerceProof deterministic gate invariant verification (margin floors, discount caps, cumulative budget).
     - **Phase C**: Real Razorpay test order creation (`POST https://api.razorpay.com/v1/orders`) creating real live order IDs.
     - **Phase D**: Cryptographic HMAC-SHA256 settlement webhook generation and output of ready-to-run curl commands.
   - Automatically registers all 4 lifecycle phases into `TradeLedger` for immediate inspection on the Static Judge Dashboard (`http://localhost:8000/dashboard/trace/{session_id}`).
4. **Hermetic & Isolated Testing**:
   - Added `tests/integration/test_live_validation.py` verifying JSON parsing, markdown code fences, malformed output handling, and API failure modes.
   - Updated `test_settings.py` to ensure local `.env` values do not interfere with unit test isolation.
   - All 121 tests pass deterministically in seconds.

---

## 3. Exact Commands to Run Live Validation

### Command 1: Full Live Validation (Using Real Credentials from `.env`)
```bash
python scripts/live_validation.py
```

### Command 2: Mock Mode Fallback (Zero Credentials Required / Offline)
```bash
python scripts/live_validation.py --mock-llm --mock-razorpay
```

### Command 3: Launch FastAPI & Static Judge Dashboard
```bash
uvicorn merchantos_api.main:app --reload --port 8000
```
- Dashboard UI: `http://localhost:8000/dashboard`
- Live Trace Inspection: `http://localhost:8000/dashboard/trace/{session_id}`

---

## 4. Required `.env` File Configuration

To run with real external APIs, configure the `.env` file at the repository root as follows:

```env
# Razorpay Configuration (Test Mode)
RAZORPAY_USE_MOCK=False
RAZORPAY_KEY_ID=rzp_test_your_key_id_here
RAZORPAY_KEY_SECRET=your_razorpay_secret_here
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
RAZORPAY_BASE_URL=https://api.razorpay.com
RAZORPAY_REQUEST_TIMEOUT_SECONDS=10.0

# LLM Configuration (OpenAI-Compatible: Grok, Groq, or OpenAI)
LLM_USE_MOCK=False
LLM_API_KEY=gsk_your_groq_or_openai_api_key_here
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL_NAME=llama-3.3-70b-versatile
```

*Note: If `RAZORPAY_USE_MOCK=True` and `LLM_USE_MOCK=True`, no external API keys are required.*

---

## 5. Live Demo Script for the 5-Minute Pitch Video

1. **Step 1 — Show Terminal Architecture & Config (0:00 - 1:00)**:
   - Run `pytest -v` to show all 121 tests passing across unit, adversarial, integration, and live validation suites.
   - Run `python scripts/run_evaluation.py --dataset dev` to display the Divergence Thesis benchmark (+19% to +41% conversion improvement over rules baseline under intent ambiguity).

2. **Step 2 — Execute Live Validation Script (1:00 - 2:30)**:
   - Run `python scripts/live_validation.py`.
   - Highlight **Phase A**: Real LLM reasoning through buyer intent and proposing price + shipping terms.
   - Highlight **Phase B**: CommerceProof gate intercepting the proposal, calculating SHA-256 state hash, and verifying the merchant margin floor and discount cap.
   - Highlight **Phase C**: Real call to `https://api.razorpay.com/v1/orders` returning a real Razorpay Order ID (e.g. `order_TVFIXQjyL2jQQT`).
   - Highlight **Phase D**: Signed HMAC-SHA256 webhook payload generation.

3. **Step 3 — Open Judge Dashboard & Trace Visualizer (2:30 - 4:00)**:
   - Open browser at `http://localhost:8000/dashboard`.
   - Click the live session (`/dashboard/trace/{session_id}`).
   - Walk through the 4 visual cards:
     - **Phase A (Blue)**: Buyer natural language & proposed concession.
     - **Phase B (Green)**: Gate decision badge (`EXECUTE`), invariant checks, and SHA-256 hash.
     - **Phase C (Purple)**: Razorpay order ID & receipt.
     - **Phase D (Teal)**: Captured payment and HMAC cryptographic confirmation.
   - Expand the collapsible `<details>` raw JSON payloads to demonstrate end-to-end cryptographic state integrity.

4. **Step 4 — Conclusion & Value Proposition (4:00 - 5:00)**:
   - Emphasize: *AI negotiates with human empathy, but deterministic code guards the money.*
