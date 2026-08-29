"""Named validation checks for hermetic logic and live external API connectivity."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import time
from typing import Any
import uuid

import httpx

from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.config import Settings
from pydantic import SecretStr
from merchantos_core.contracts import (
    AgentInput,
    CheckoutLineItem,
    CheckoutSnapshot,
    CumulativeLedger,
    InventoryRecord,
    InventoryState,
    MerchantPolicy,
    Product,
    ProposedOffer,
    TradeEvent,
    ValidationCheckResult,
)
from merchantos_core.hashing import canonical_checkout_hash
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_core.llm.openai_provider import OpenAICompatibleLLMProvider
from merchantos_razorpay.webhook import compute_webhook_signature, verify_webhook_signature


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# HERMETIC CHECKS
# -----------------------------------------------------------------------------


def check_hmac_webhook_roundtrip() -> ValidationCheckResult:
    """Hermetic: Sign body with HMAC-SHA256, verify signature, tamper body, and verify rejection."""
    start_time = time.perf_counter()
    secret = SecretStr("val_secret_hermetic_test_12345")
    raw_body = json.dumps({"event": "payment.captured", "id": "pay_test_001", "amount": 5200000}).encode("utf-8")

    # 1. Sign
    signature = compute_webhook_signature(raw_body, secret)

    # 2. Verify Valid
    valid = verify_webhook_signature(raw_body, signature, secret)
    if not valid:
        latency = int((time.perf_counter() - start_time) * 1000)
        return ValidationCheckResult(
            check_id="hmac_webhook_roundtrip",
            name="HMAC Webhook Cryptographic Verification",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Failed to verify legitimate HMAC signature on valid webhook body.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    # 3. Tamper Body
    tampered_body = json.dumps({"event": "payment.captured", "id": "pay_test_001", "amount": 100}).encode("utf-8")
    tampered_valid = verify_webhook_signature(tampered_body, signature, secret)
    latency = int((time.perf_counter() - start_time) * 1000)

    if tampered_valid:
        return ValidationCheckResult(
            check_id="hmac_webhook_roundtrip",
            name="HMAC Webhook Cryptographic Verification",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Security violation: HMAC signature verified tampered webhook body.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="hmac_webhook_roundtrip",
        name="HMAC Webhook Cryptographic Verification",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail="HMAC-SHA256 signature generated and verified; tampered payload successfully rejected.",
        evidence_json=json.dumps({"algorithm": "HMAC-SHA256", "signature_length": len(signature)}),
        timestamp=_now_iso(),
    )


def check_canonical_hash_determinism() -> ValidationCheckResult:
    """Hermetic: Assert identical snapshots yield identical SHA-256 hashes and 1-paise changes diverge."""
    start_time = time.perf_counter()

    snap1 = CheckoutSnapshot(
        session_id="sess_val_hash_01",
        merchant_id="merchant_001",
        currency="INR",
        amount_minor=500000,
        line_items=[
            CheckoutLineItem(
                sku_id="SKU-TEST-01",
                name="Test Laptop",
                quantity=1,
                unit_amount_minor=500000,
                line_total_minor=500000,
            )
        ],
    )

    snap2 = CheckoutSnapshot(
        session_id="sess_val_hash_01",
        merchant_id="merchant_001",
        currency="INR",
        amount_minor=500000,
        line_items=[
            CheckoutLineItem(
                sku_id="SKU-TEST-01",
                name="Test Laptop",
                quantity=1,
                unit_amount_minor=500000,
                line_total_minor=500000,
            )
        ],
    )

    snap_tampered = CheckoutSnapshot(
        session_id="sess_val_hash_01",
        merchant_id="merchant_001",
        currency="INR",
        amount_minor=500001,  # 1 paise difference
        line_items=[
            CheckoutLineItem(
                sku_id="SKU-TEST-01",
                name="Test Laptop",
                quantity=1,
                unit_amount_minor=500001,
                line_total_minor=500001,
            )
        ],
    )

    h1 = canonical_checkout_hash(snap1)
    h2 = canonical_checkout_hash(snap2)
    h3 = canonical_checkout_hash(snap_tampered)
    latency = int((time.perf_counter() - start_time) * 1000)

    if h1 != h2:
        return ValidationCheckResult(
            check_id="canonical_hash_determinism",
            name="Canonical Checkout State Hash Determinism",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Determinism violation: Identical snapshots produced different hashes.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    if h1 == h3:
        return ValidationCheckResult(
            check_id="canonical_hash_determinism",
            name="Canonical Checkout State Hash Determinism",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Collision violation: 1-paise difference produced identical state hash.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="canonical_hash_determinism",
        name="Canonical Checkout State Hash Determinism",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail="Deterministic SHA-256 canonical hashing verified; 1-paise modification produces hash divergence.",
        evidence_json=json.dumps({"canonical_hash": h1[:16] + "...", "modified_hash": h3[:16] + "..."}),
        timestamp=_now_iso(),
    )


def check_commerceproof_clamp() -> ValidationCheckResult:
    """Hermetic: Assert illegal 50% discount offer is REPAIRed to cap and margin floor is enforced."""
    start_time = time.perf_counter()

    product = Product(
        sku_id="SKU-VAL-LAPTOP",
        name="Validation Laptop",
        category="laptop",
        base_price_minor=5200000,  # ₹52,000.00
        cost_minor=3900000,        # ₹39,000.00 (15% margin floor = 44,850.00 / 4485000 paise)
        inventory_count=10,
    )
    policy = MerchantPolicy(
        merchant_id="merchant_val",
        margin_floor_pct=0.15,
        discount_cap_pct=0.20,      # 20% cap = ₹10,400 max discount -> min price ₹41,600
        promotion_budget_minor=10000000,
    )
    inventory = InventoryState(records=[InventoryRecord(sku_id="SKU-VAL-LAPTOP", available_count=10)])
    ledger = CumulativeLedger(merchant_id="merchant_val", total_promotion_budget_minor=10000000, total_discount_minor_used=0)

    # Illegal 50% discount proposal
    illegal_offer = ProposedOffer(
        offer_id="off_illegal_50",
        session_id="sess_val_clamp",
        selected_sku_id="SKU-VAL-LAPTOP",
        proposed_price_minor=2600000,  # 50% off
        discount_minor=2600000,
        shipping_tier="standard",
        rationale="Illegal 50% discount test",
    )

    gate = CommerceProof()
    decision = gate.evaluate(
        offer=illegal_offer,
        policy=policy,
        inventory=inventory,
        ledger=ledger,
        catalog=[product],
    )
    latency = int((time.perf_counter() - start_time) * 1000)

    if decision.action != "REPAIR" or not decision.final_offer:
        return ValidationCheckResult(
            check_id="commerceproof_clamp",
            name="CommerceProof Invariant Enforcement & Clamping",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail=f"Expected REPAIR action, got {decision.action}.",
            evidence_json=json.dumps({"action": decision.action, "violations": decision.violations}),
            timestamp=_now_iso(),
        )

    # Check that price is at or above margin floor (₹44,850.00 = 4485000 paise)
    final_price = decision.final_offer.proposed_price_minor
    if final_price < 4485000:
        return ValidationCheckResult(
            check_id="commerceproof_clamp",
            name="CommerceProof Invariant Enforcement & Clamping",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail=f"Margin floor breached: repaired price {final_price} < minimum floor 4485000.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="commerceproof_clamp",
        name="CommerceProof Invariant Enforcement & Clamping",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail="Excessive discount proposal intercepted and clamped to policy discount cap and margin floor.",
        evidence_json=json.dumps(
            {
                "original_price_minor": illegal_offer.proposed_price_minor,
                "repaired_price_minor": final_price,
                "repairs": decision.repairs,
            }
        ),
        timestamp=_now_iso(),
    )


def check_ground_truth_leakage_scan(scenarios: list[dict[str, Any]] | None = None) -> ValidationCheckResult:
    """Hermetic: Scan dataset utterances to assert zero ground-truth keys or internal budget minor values leak."""
    start_time = time.perf_counter()

    scenario_records: list[dict[str, Any]] = []

    if scenarios is not None:
        scenario_records = scenarios
    else:
        root_data = Path(__file__).resolve().parent.parent.parent.parent / "data"
        for dataset_filename in ("dev_scenarios.jsonl", "heldout_scenarios.jsonl"):
            fpath = root_data / dataset_filename
            if fpath.exists():
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                scenario_records.append(json.loads(line))
                            except Exception:
                                pass

    leaked_scenarios: list[dict[str, str]] = []
    forbidden_substrings = [
        "ground_truth",
        "true_intent",
        "target_sku",
        "min_acceptable_utility",
        "urgency_weight",
        "quality_weight",
        "price_weight",
    ]

    for sc in scenario_records:
        utterance = sc.get("nl_utterance", "")
        # Check forbidden substrings
        for forbidden in forbidden_substrings:
            if forbidden in utterance.lower():
                leaked_scenarios.append({"scenario_id": sc.get("scenario_id", "unknown"), "leak": forbidden})

        # Check raw minor budget leakage
        true_intent = sc.get("true_intent") or sc.get("ground_truth") or {}
        max_budget_minor = true_intent.get("max_budget_minor")
        if max_budget_minor and str(max_budget_minor) in utterance:
            leaked_scenarios.append(
                {"scenario_id": sc.get("scenario_id", "unknown"), "leak": f"raw_budget_{max_budget_minor}"}
            )

    latency = int((time.perf_counter() - start_time) * 1000)

    if leaked_scenarios:
        return ValidationCheckResult(
            check_id="ground_truth_leakage_scan",
            name="Zero Ground-Truth Leakage CI Scan",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail=f"Leakage detected in {len(leaked_scenarios)} scenario(s): {leaked_scenarios[0]}",
            evidence_json=json.dumps({"leaks": leaked_scenarios[:5]}),
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="ground_truth_leakage_scan",
        name="Zero Ground-Truth Leakage CI Scan",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail=f"Scanned {len(scenario_records)} benchmark scenarios; 0 internal evaluation keys or raw minor values leaked.",
        evidence_json=json.dumps({"scenarios_scanned": len(scenario_records), "leaks_found": 0}),
        timestamp=_now_iso(),
    )


def check_negotiation_determinism() -> ValidationCheckResult:
    """Hermetic: RulesBaselineAgent produces identical offers when evaluated repeatedly on same input."""
    start_time = time.perf_counter()

    catalog = [
        Product(
            sku_id="SKU-01",
            name="Laptop",
            category="laptop",
            base_price_minor=5000000,
            cost_minor=4000000,
            inventory_count=5,
        )
    ]
    policy = MerchantPolicy(
        merchant_id="merchant_001",
        margin_floor_pct=0.10,
        discount_cap_pct=0.15,
        promotion_budget_minor=1000000,
    )
    agent_input = AgentInput(
        session_id="sess_det_test",
        nl_utterance="Looking for a laptop with urgent express delivery.",
        available_catalog=catalog,
        merchant_policy=policy,
        negotiation_history=[],
    )

    agent = RulesBaselineAgent()
    p1 = agent.score_and_propose(agent_input)
    p2 = agent.score_and_propose(agent_input)

    latency = int((time.perf_counter() - start_time) * 1000)

    if p1.model_dump() != p2.model_dump():
        return ValidationCheckResult(
            check_id="negotiation_determinism",
            name="Rules Baseline Negotiation Determinism",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Baseline agent produced non-deterministic proposals on identical input.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="negotiation_determinism",
        name="Rules Baseline Negotiation Determinism",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail="Baseline agent generated bit-identical offer proposals on repeat evaluation.",
        evidence_json=json.dumps({"selected_sku": p1.selected_sku_id, "proposed_price": p1.proposed_price_minor}),
        timestamp=_now_iso(),
    )


def check_ledger_subscription_roundtrip(trade_ledger: TradeLedger | None = None) -> ValidationCheckResult:
    """Hermetic: Subscribe to TradeLedger, record event, verify non-blocking delivery, and unsubscribe."""
    start_time = time.perf_counter()
    ledger = trade_ledger or TradeLedger()
    q = ledger.subscribe()

    test_event_id = f"evt_val_sub_{uuid.uuid4().hex[:6]}"
    evt = TradeEvent(
        event_id=test_event_id,
        session_id="sess_val_sub",
        timestamp=_now_iso(),
        event_type="intent_received",
        payload=json.dumps({"test": "subscription_roundtrip"}),
    )
    ledger.record_event(evt)

    try:
        received = q.get(timeout=1.0)
        received_match = received.event_id == test_event_id
    except Exception:
        received_match = False

    ledger.unsubscribe(q)
    latency = int((time.perf_counter() - start_time) * 1000)

    if not received_match:
        return ValidationCheckResult(
            check_id="ledger_subscription_roundtrip",
            name="TradeLedger Real-Time Event Subscription",
            category="hermetic",
            status="fail",
            latency_ms=latency,
            detail="Subscriber queue failed to receive event dispatched from TradeLedger.record_event.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    return ValidationCheckResult(
        check_id="ledger_subscription_roundtrip",
        name="TradeLedger Real-Time Event Subscription",
        category="hermetic",
        status="pass",
        latency_ms=latency,
        detail="Subscriber queue successfully received live event packet; cleanly unsubscribed.",
        evidence_json=json.dumps({"dispatched_event_id": test_event_id, "queue_latency_ms": latency}),
        timestamp=_now_iso(),
    )


# -----------------------------------------------------------------------------
# LIVE EXTERNAL CHECKS
# -----------------------------------------------------------------------------


def check_live_razorpay(settings: Settings, http_client: Any | None = None) -> ValidationCheckResult:
    """Live: Create minimal ₹1 order via Razorpay API, fetch order by ID, and verify amount."""
    start_time = time.perf_counter()

    if settings.razorpay_use_mock or not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return ValidationCheckResult(
            check_id="live_razorpay",
            name="Razorpay Test-Mode Gateway Connectivity",
            category="live_razorpay",
            status="skipped",
            latency_ms=0,
            detail="Skipped: RAZORPAY_USE_MOCK=True or Razorpay API credentials not configured in .env.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    key_id = settings.razorpay_key_id.get_secret_value() if hasattr(settings.razorpay_key_id, "get_secret_value") else str(settings.razorpay_key_id)
    key_secret = settings.razorpay_key_secret.get_secret_value()
    base_url = settings.razorpay_base_url.rstrip("/")

    receipt_id = f"validation_{int(time.time())}"
    order_payload = {
        "amount": 100,  # ₹1.00 = 100 paise
        "currency": "INR",
        "receipt": receipt_id,
        "notes": {"purpose": "connectivity_check"},
    }

    try:
        client = http_client or httpx.Client(auth=(key_id, key_secret), timeout=15.0)
        # 1. POST /v1/orders
        post_resp = client.post(f"{base_url}/v1/orders", json=order_payload)
        if post_resp.status_code not in (200, 201):
            latency = int((time.perf_counter() - start_time) * 1000)
            return ValidationCheckResult(
                check_id="live_razorpay",
                name="Razorpay Test-Mode Gateway Connectivity",
                category="live_razorpay",
                status="fail",
                latency_ms=latency,
                detail=f"Razorpay POST /v1/orders failed with HTTP {post_resp.status_code}: {post_resp.text[:120]}",
                evidence_json="",
                timestamp=_now_iso(),
            )

        order_data = post_resp.json()
        order_id = order_data.get("id")
        if not order_id:
            latency = int((time.perf_counter() - start_time) * 1000)
            return ValidationCheckResult(
                check_id="live_razorpay",
                name="Razorpay Test-Mode Gateway Connectivity",
                category="live_razorpay",
                status="fail",
                latency_ms=latency,
                detail="Razorpay order response missing order ID.",
                evidence_json="",
                timestamp=_now_iso(),
            )

        # 2. GET /v1/orders/{order_id}
        get_resp = client.get(f"{base_url}/v1/orders/{order_id}")
        latency = int((time.perf_counter() - start_time) * 1000)

        if get_resp.status_code != 200:
            return ValidationCheckResult(
                check_id="live_razorpay",
                name="Razorpay Test-Mode Gateway Connectivity",
                category="live_razorpay",
                status="fail",
                latency_ms=latency,
                detail=f"Razorpay GET /v1/orders/{order_id} failed with HTTP {get_resp.status_code}",
                evidence_json="",
                timestamp=_now_iso(),
            )

        fetched_data = get_resp.json()
        fetched_amount = fetched_data.get("amount")
        if fetched_amount != 100:
            return ValidationCheckResult(
                check_id="live_razorpay",
                name="Razorpay Test-Mode Gateway Connectivity",
                category="live_razorpay",
                status="fail",
                latency_ms=latency,
                detail=f"Amount mismatch on order verification: expected 100, got {fetched_amount}",
                evidence_json="",
                timestamp=_now_iso(),
            )

        return ValidationCheckResult(
            check_id="live_razorpay",
            name="Razorpay Test-Mode Gateway Connectivity",
            category="live_razorpay",
            status="pass",
            latency_ms=latency,
            detail=f"Real Razorpay test-mode order {order_id} created and re-verified via GET /v1/orders/{order_id}.",
            evidence_json=json.dumps(
                {
                    "order_id": order_id,
                    "amount_minor": 100,
                    "currency": "INR",
                    "status": fetched_data.get("status", "created"),
                    "receipt": receipt_id,
                }
            ),
            timestamp=_now_iso(),
        )
    except Exception as err:
        latency = int((time.perf_counter() - start_time) * 1000)
        # Sanitize exception so secrets are never rendered
        err_msg = str(err).replace(key_secret, "[REDACTED]")
        return ValidationCheckResult(
            check_id="live_razorpay",
            name="Razorpay Test-Mode Gateway Connectivity",
            category="live_razorpay",
            status="fail",
            latency_ms=latency,
            detail=f"Razorpay request failed: {err_msg[:120]}",
            evidence_json="",
            timestamp=_now_iso(),
        )


def check_live_llm(settings: Settings, provider: Any | None = None) -> ValidationCheckResult:
    """Live: Send minimal ping completion to OpenAI-compatible LLM endpoint and measure latency."""
    start_time = time.perf_counter()

    if settings.llm_use_mock or not settings.llm_api_key:
        return ValidationCheckResult(
            check_id="live_llm",
            name="OpenAI-Compatible LLM Provider Connectivity",
            category="live_llm",
            status="skipped",
            latency_ms=0,
            detail="Skipped: LLM_USE_MOCK=True or LLM_API_KEY not configured in .env.",
            evidence_json="",
            timestamp=_now_iso(),
        )

    try:
        llm_prov = provider or OpenAICompatibleLLMProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model_name,
            timeout_seconds=30.0,
        )
        reply = llm_prov.ping()
        latency = int((time.perf_counter() - start_time) * 1000)

        return ValidationCheckResult(
            check_id="live_llm",
            name="OpenAI-Compatible LLM Provider Connectivity",
            category="live_llm",
            status="pass",
            latency_ms=latency,
            detail=f"Live LLM provider ping succeeded ({settings.llm_model_name}).",
            evidence_json=json.dumps(
                {
                    "model": settings.llm_model_name,
                    "base_url": settings.llm_base_url,
                    "reply_snippet": str(reply)[:40],
                    "latency_ms": latency,
                }
            ),
            timestamp=_now_iso(),
        )
    except Exception as err:
        latency = int((time.perf_counter() - start_time) * 1000)
        raw_secret = settings.llm_api_key.get_secret_value() if settings.llm_api_key else ""
        err_msg = str(err).replace(raw_secret, "[REDACTED]") if raw_secret else str(err)
        return ValidationCheckResult(
            check_id="live_llm",
            name="OpenAI-Compatible LLM Provider Connectivity",
            category="live_llm",
            status="fail",
            latency_ms=latency,
            detail=f"LLM ping request failed: {err_msg[:120]}",
            evidence_json="",
            timestamp=_now_iso(),
        )
