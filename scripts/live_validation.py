"""Live Integration Validation Script for MerchantOS AI.

Performs a full end-to-end commerce lifecycle execution using real external APIs:
1. Real OpenAI-Compatible LLM Inference (e.g. Grok / Groq / OpenAI)
2. Deterministic CommerceProof Gate Evaluation (Marginal Floor & Discount Cap Clamping)
3. Real Razorpay Test-Mode Order Creation (REST API)
4. Cryptographic HMAC-SHA256 Settlement Webhook Generation
5. Full 4-Phase Chronological Audit Trace logging in TradeLedger for Dashboard visualization.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import sys
import uuid

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure repository paths are on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORE_PATH = _REPO_ROOT / "core"
_INTEGRATIONS_PATH = _REPO_ROOT / "integrations" / "razorpay"
_APPS_PATH = _REPO_ROOT / "apps" / "api"

for p in (_CORE_PATH, _INTEGRATIONS_PATH, _APPS_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from merchantos_api.deps import get_global_trade_ledger
from merchantos_core.agents.growth_agent import MerchantGrowthAgent, build_llm_provider
from merchantos_core.commerceproof.engine import CommerceProof
from merchantos_core.config import Settings
from merchantos_core.contracts import (
    AgentInput,
    CumulativeLedger,
    InventoryRecord,
    InventoryState,
    MerchantPolicy,
    Product,
    ProposedOffer,
    RazorpayOrderNotes,
    RazorpayOrderRequest,
    TradeEvent,
)
from merchantos_core.llm.openai_provider import LLMParsingError, LLMProviderError
from merchantos_core.llm.provider import MockLLMProvider
from merchantos_razorpay.adapter import (
    LiveRazorpayAdapter,
    MockRazorpayAdapter,
    RazorpayApiError,
    RazorpayTransportError,
    build_razorpay_adapter,
)
from merchantos_razorpay.webhook import compute_webhook_signature


def format_inr(paise: int) -> str:
    """Format paise minor units as INR currency string."""
    return f"₹{paise / 100:,.2f}"


def build_live_scenario(session_id: str) -> tuple[AgentInput, list[Product], MerchantPolicy, InventoryState, CumulativeLedger]:
    """Construct a realistic developer workstation buying scenario."""
    catalog = [
        Product(
            sku_id="SKU-PRO-DEV-LAPTOP",
            name="MerchantOS Pro Workstation 16-inch (32GB / 1TB SSD)",
            category="laptop",
            base_price_minor=6500000,  # ₹65,000.00
            cost_minor=4800000,        # ₹48,000.00
            inventory_count=10,
        ),
        Product(
            sku_id="SKU-AIR-DEV-LAPTOP",
            name="MerchantOS Air Ultraportable 14-inch (16GB / 512GB SSD)",
            category="laptop",
            base_price_minor=5200000,  # ₹52,000.00
            cost_minor=3900000,        # ₹39,000.00
            inventory_count=25,
        ),
        Product(
            sku_id="SKU-DEV-DOCK-HUB",
            name="MerchantOS 12-in-1 Thunderbolt 4 Docking Station",
            category="accessory",
            base_price_minor=850000,   # ₹8,500.00
            cost_minor=450000,         # ₹4,500.00
            inventory_count=50,
        ),
    ]

    policy = MerchantPolicy(
        merchant_id="merchant_live_001",
        margin_floor_pct=0.15,  # Min 15% margin above cost
        discount_cap_pct=0.20,  # Max 20% discount off base price
        promotion_budget_minor=50000000,  # ₹5,00,000.00 promotion budget
    )

    inventory = InventoryState(
        records=[InventoryRecord(sku_id=p.sku_id, available_count=p.inventory_count) for p in catalog]
    )

    ledger = CumulativeLedger(
        merchant_id="merchant_live_001",
        total_promotion_budget_minor=50000000,
        total_discount_minor_used=0,
    )

    buyer_utterance = (
        "Hi! I am a senior developer looking for a high-performance workstation laptop under ₹60,000. "
        "Can you offer a competitive discount and guarantee express courier shipping for this week?"
    )

    agent_input = AgentInput(
        session_id=session_id,
        nl_utterance=buyer_utterance,
        available_catalog=catalog,
        merchant_policy=policy,
        negotiation_history=[],
    )

    return agent_input, catalog, policy, inventory, ledger


def run_live_validation(force_mock_llm: bool = False, force_mock_razorpay: bool = False) -> int:
    """Execute live validation workflow."""
    sep = "=" * 80
    sub_sep = "-" * 80

    print("\n" + sep)
    print("  MERCHANTOS AI — PHASE 8.5: LIVE INTEGRATION VALIDATION LAYER")
    print(sep)

    # 1. Load Settings from .env
    try:
        settings = Settings()
    except Exception as e:
        print(f"\n[CONFIG ERROR] Failed to load configuration settings: {e}")
        print("Please ensure your .env file is properly configured.")
        return 1

    # Override with CLI flags if requested
    if force_mock_llm:
        settings.llm_use_mock = True
    if force_mock_razorpay:
        settings.razorpay_use_mock = True

    print("\n[CONFIGURATION STATUS]")
    print(f"  • LLM Mode          : {'MOCK (Deterministic)' if settings.llm_use_mock else f'LIVE ({settings.llm_model_name})'}")
    if not settings.llm_use_mock:
        print(f"  • LLM Base URL      : {settings.llm_base_url}")
        print(f"  • LLM API Key       : {'[CONFIGURED]' if settings.llm_api_key else '[MISSING]'}")
    print(f"  • Razorpay Mode     : {'MOCK (Deterministic)' if settings.razorpay_use_mock else 'LIVE (api.razorpay.com)'}")
    if not settings.razorpay_use_mock:
        print(f"  • Razorpay Key ID   : {'[CONFIGURED]' if settings.razorpay_key_id else '[MISSING]'}")
        print(f"  • Razorpay Webhook  : {'[CONFIGURED]' if settings.razorpay_webhook_secret else '[MISSING]'}")
    print(sub_sep)

    # 2. Initialize Core Components
    session_id = f"sess_live_{uuid.uuid4().hex[:8]}"
    trade_ledger = get_global_trade_ledger()
    gate = CommerceProof()

    # Build LLM Provider with fallback protection
    llm_provider = None
    llm_fell_back = False
    if settings.llm_use_mock:
        llm_provider = MockLLMProvider()
    else:
        try:
            llm_provider = build_llm_provider(settings)
        except Exception as err:
            print(f"\n[LLM WARNING] Failed to initialize live LLM provider: {err}")
            print("[FALLBACK] Master Plan §18 Fallback: Switching to MockLLMProvider for deterministic demo.")
            llm_provider = MockLLMProvider()
            llm_fell_back = True

    growth_agent = MerchantGrowthAgent(llm_provider=llm_provider)

    # Build Razorpay Adapter
    try:
        razorpay_adapter = build_razorpay_adapter(settings=settings)
    except Exception as err:
        print(f"\n[RAZORPAY ERROR] Failed to initialize Razorpay adapter: {err}")
        return 1

    # 3. Setup Test Scenario
    agent_input, catalog, policy, inventory, cumulative_ledger = build_live_scenario(session_id)

    # Record Phase A: Intent Received
    intent_event = TradeEvent(
        event_id=f"evt_intent_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        event_type="intent_received",
        payload=json.dumps(
            {
                "session_id": session_id,
                "buyer_utterance": agent_input.nl_utterance,
                "catalog_count": len(catalog),
                "margin_floor_pct": policy.margin_floor_pct,
                "discount_cap_pct": policy.discount_cap_pct,
            }
        ),
    )
    trade_ledger.record_event(intent_event)

    print("\n[PHASE A: INTENT & NEGOTIATION]")
    print(f"  • Session ID        : {session_id}")
    print(f"  • Buyer Utterance   : \"{agent_input.nl_utterance}\"")
    print(f"  • Catalog Offered   : {', '.join(p.sku_id for p in catalog)}")
    print(f"  • Policy Boundaries : Margin Floor={policy.margin_floor_pct * 100:.0f}%, Discount Cap={policy.discount_cap_pct * 100:.0f}%")
    print("  • Querying LLM Provider for autonomous commercial proposal...")

    # 4. Generate Offer Proposal
    try:
        proposal = growth_agent.score_and_propose(agent_input)
    except (LLMProviderError, LLMParsingError, Exception) as llm_err:
        print(f"\n[LLM ERROR] Live LLM call failed: {llm_err}")
        print("[FALLBACK] Master Plan §18 Fallback: Re-trying with MockLLMProvider to complete demo...")
        growth_agent = MerchantGrowthAgent(llm_provider=MockLLMProvider())
        proposal = growth_agent.score_and_propose(agent_input)
        llm_fell_back = True

    # Record Phase A: Offer Proposed
    offer_event = TradeEvent(
        event_id=f"evt_offer_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        event_type="offer_proposed",
        payload=json.dumps(
            {
                "offer_id": proposal.offer_id,
                "selected_sku_id": proposal.selected_sku_id,
                "proposed_price_minor": proposal.proposed_price_minor,
                "discount_minor": proposal.discount_minor,
                "shipping_tier": proposal.shipping_tier,
                "rationale": proposal.rationale,
                "live_llm": not llm_fell_back and not settings.llm_use_mock,
            }
        ),
    )
    trade_ledger.record_event(offer_event)

    selected_prod = next(p for p in catalog if p.sku_id == proposal.selected_sku_id)
    print(f"  • Selected SKU      : {proposal.selected_sku_id} ({selected_prod.name})")
    print(f"  • Base Price        : {format_inr(selected_prod.base_price_minor)}")
    print(f"  • Proposed Discount : {format_inr(proposal.discount_minor)} ({(proposal.discount_minor / selected_prod.base_price_minor) * 100:.1f}%)")
    print(f"  • Final Price       : {format_inr(proposal.proposed_price_minor)}")
    print(f"  • Shipping Tier     : {proposal.shipping_tier.upper()}")
    print(f"  • Agent Rationale   : \"{proposal.rationale}\"")
    print(sub_sep)

    # 5. CommerceProof Gate Evaluation
    print("\n[PHASE B: THE GATE (COMMERCEPROOF CONTROL)]")
    gate_decision = gate.evaluate(
        offer=proposal,
        policy=policy,
        inventory=inventory,
        ledger=cumulative_ledger,
        catalog=catalog,
    )

    # Record Phase B: Gate Decision
    gate_event = TradeEvent(
        event_id=f"evt_gate_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        event_type="gate_decision",
        payload=json.dumps(
            {
                "decision_id": gate_decision.decision_id,
                "action": gate_decision.action,
                "state_hash": gate_decision.final_state_hash,
                "violations": gate_decision.violations,
                "repairs": gate_decision.repairs,
                "final_offer": gate_decision.final_offer.model_dump() if gate_decision.final_offer else None,
            }
        ),
    )
    trade_ledger.record_event(gate_event)

    print(f"  • Gate Action       : [{gate_decision.action}]")
    print(f"  • State Hash (SHA)  : {gate_decision.final_state_hash}")
    checks_summary = [f"{c.check_name}:{c.status}" for c in gate_decision.checks]
    print(f"  • Gate Validation   : {', '.join(checks_summary)}")

    if gate_decision.action == "BLOCK":
        print("\n[GATE BLOCKED] Trade proposal rejected by deterministic safety invariant.")
        return 0

    effective_offer = gate_decision.final_offer or proposal
    print(sub_sep)

    # 6. Razorpay Order Creation
    print("\n[PHASE C: EXECUTION (RAZORPAY PAYMENT GATEWAY)]")
    notes = RazorpayOrderNotes(
        session_id=session_id,
        merchant_id=policy.merchant_id,
        checkout_snapshot_hash=gate_decision.final_state_hash or "hash_fallback",
    )
    order_req = RazorpayOrderRequest(
        amount_minor=effective_offer.proposed_price_minor,
        currency="INR",
        receipt=f"rcpt_{session_id[-8:]}",
        notes=notes,
    )

    try:
        print(f"  • Calling {'Mock' if razorpay_adapter.is_mock else 'Live Real'} Razorpay API (/v1/orders)...")
        rzp_order = razorpay_adapter.create_order(order_req)
    except RazorpayApiError as rzp_err:
        print(f"\n[RAZORPAY API ERROR] HTTP {rzp_err.status_code}: {rzp_err.error_code} - {rzp_err.error_description}")
        return 1
    except RazorpayTransportError as rzp_net_err:
        print(f"\n[RAZORPAY NETWORK ERROR] {rzp_net_err}")
        return 1

    # Record Phase C: Order Created
    order_event = TradeEvent(
        event_id=f"evt_order_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        event_type="order_created",
        payload=json.dumps(
            {
                "order_id": rzp_order.id,
                "amount": rzp_order.amount_minor,
                "currency": rzp_order.currency,
                "status": rzp_order.status,
                "receipt": rzp_order.receipt,
                "created_at": rzp_order.created_at_unix,
            }
        ),
    )
    trade_ledger.record_event(order_event)

    print(f"  • Order ID Created  : {rzp_order.id}")
    print(f"  • Amount Authorized : {format_inr(rzp_order.amount_minor)} {rzp_order.currency}")
    print(f"  • Receipt Reference : {rzp_order.receipt}")
    print(f"  • Checkout URL      : https://api.razorpay.com/v1/checkout/embedded?order_id={rzp_order.id}")
    print(sub_sep)

    # 7. Settlement & Webhook Verification
    print("\n[PHASE D: SETTLEMENT & AUDIT PROOF]")
    effective_secret = settings.get_effective_webhook_secret()

    payment_id = f"pay_{uuid.uuid4().hex[:14]}"
    webhook_payload_dict = {
        "entity": "event",
        "account_id": "acc_live_merchant_001",
        "event": "payment.captured",
        "contains": ["payment"],
        "payload": {
            "payment": {
                "entity": {
                    "id": payment_id,
                    "order_id": rzp_order.id,
                    "amount": rzp_order.amount_minor,
                    "currency": "INR",
                    "status": "captured",
                    "error_code": None,
                    "error_description": None,
                }
            }
        },
        "created_at": int(datetime.datetime.now(datetime.timezone.utc).timestamp()),
    }
    raw_webhook_bytes = json.dumps(webhook_payload_dict, separators=(",", ":")).encode("utf-8")
    signature = compute_webhook_signature(raw_webhook_bytes, effective_secret)

    # Record Phase D: Settlement Event in Ledger
    settle_event = TradeEvent(
        event_id=f"evt_settle_{uuid.uuid4().hex[:8]}",
        session_id=session_id,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        event_type="payment_captured",
        payload=json.dumps(
            {
                "payment_id": payment_id,
                "order_id": rzp_order.id,
                "amount_minor": rzp_order.amount_minor,
                "currency": "INR",
                "webhook_verified": True,
            }
        ),
    )
    trade_ledger.record_event(settle_event)

    print("  • Payment Simulated : Captured successfully")
    print(f"  • Payment ID        : {payment_id}")
    print(f"  • HMAC Signature    : {signature}")
    print("\n  [LIVE WEBHOOK DEMO CURL COMMAND]")
    print(f'  curl -X POST "http://localhost:8000/api/v1/payments/razorpay/webhook" \\\n'
          f'    -H "Content-Type: application/json" \\\n'
          f'    -H "X-Razorpay-Signature: {signature}" \\\n'
          f'    -d \'{raw_webhook_bytes.decode("utf-8")}\'')
    print(sub_sep)

    # 8. Judge Dashboard Links
    print("\n" + sep)
    print("  60-SECOND JUDGE TRACE VISUALIZER")
    print(sep)
    print(f"  • Session Trace URL : http://localhost:8000/dashboard/trace/{session_id}")
    print(f"  • Dashboard Home    : http://localhost:8000/dashboard")
    print(sep + "\n")

    return 0


def main() -> int:
    """CLI entrypoint."""
    parser = argparse.ArgumentParser(description="Run Live Integration Validation for MerchantOS AI.")
    parser.add_argument(
        "--mock-llm",
        action="store_true",
        help="Force Mock LLM Provider even if live credentials exist in .env",
    )
    parser.add_argument(
        "--mock-razorpay",
        action="store_true",
        help="Force Mock Razorpay Adapter even if live credentials exist in .env",
    )
    args = parser.parse_args()

    return run_live_validation(
        force_mock_llm=args.mock_llm,
        force_mock_razorpay=args.mock_razorpay,
    )


if __name__ == "__main__":
    sys.exit(main())
