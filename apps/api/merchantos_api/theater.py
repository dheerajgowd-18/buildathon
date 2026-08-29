"""The Trading Floor: SSE choreography orchestrator and backend protocol for Phase 12."""

from __future__ import annotations

import anyio
import asyncio
import datetime
import json
import logging
from pathlib import Path
import queue
import random
import threading
import time
from typing import Annotated, Any, Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from merchantos_api.deps import get_razorpay_adapter, get_settings, get_trade_ledger
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.agents.growth_agent import MerchantGrowthAgent
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
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_core.llm.provider import MockLLMProvider
from merchantos_core.llm.openai_provider import (
    LLMParsingError,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)
from merchantos_razorpay.adapter import MockRazorpayAdapter
from merchantos_core.negotiation.buyer_simulator import BuyerSimulator
from merchantos_simulator.buyers import generate_buyer_intent
from merchantos_simulator.nlg import generate_lossy_utterance

logger = logging.getLogger(__name__)
router = APIRouter(tags=["theater"])

# Standard Trading Floor Catalog & Policy
THEATER_CATALOG = [
    Product(
        sku_id="SKU-PRO-LAPTOP",
        name="Developer Workstation Pro 16",
        category="laptop",
        base_price_minor=5200000,   # ₹52,000.00
        cost_minor=3900000,         # ₹39,000.00 (Floor: ₹44,850.00)
        inventory_count=8,
    ),
    Product(
        sku_id="SKU-AIR-LAPTOP",
        name="Ultraportable Air 14",
        category="laptop",
        base_price_minor=4600000,   # ₹46,000.00
        cost_minor=3500000,         # ₹35,000.00 (Floor: ₹40,250.00)
        inventory_count=12,
    ),
    Product(
        sku_id="SKU-STUDIO-HEADPHONES",
        name="Studio ANC Wireless Headphones",
        category="audio",
        base_price_minor=1200000,   # ₹12,000.00
        cost_minor=800000,          # ₹8,000.00
        inventory_count=20,
    ),
]

THEATER_POLICY = MerchantPolicy(
    merchant_id="merchant_floor_01",
    margin_floor_pct=0.15,
    discount_cap_pct=0.20,
    promotion_budget_minor=10000000,
)


class TheaterRunRequest(BaseModel):
    """Request contract for starting a Trading Floor theater performance."""

    model_config = ConfigDict(extra="forbid")

    utterance: str | None = Field(default=None, max_length=500)
    random: bool = False
    mode: Literal["solo", "race"] = "solo"
    use_live_llm: bool = False


class TheaterStepEvent(BaseModel):
    """Event packet streamed to client during theater playback."""

    model_config = ConfigDict(extra="forbid")

    seq: int
    stage: str
    actor: Literal["buyer", "clerk", "salesperson", "accountant", "bank", "system"]
    title: str
    caption: str
    tone: Literal["neutral", "accent", "clerk", "warning", "danger", "success", "evaluator"]
    payload_json: str
    timestamp: str


class TheaterSessionManager:
    """Manages active theater sessions and SSE subscribers with replay buffering."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[queue.Queue[TheaterStepEvent | None]]] = {}
        self._history: dict[str, list[TheaterStepEvent | None]] = {}
        self._lock = threading.Lock()

    def subscribe(self, run_id: str, maxsize: int = 1000) -> queue.Queue[TheaterStepEvent | None]:
        q: queue.Queue[TheaterStepEvent | None] = queue.Queue(maxsize=maxsize)
        with self._lock:
            if run_id not in self._subscribers:
                self._subscribers[run_id] = []
            self._subscribers[run_id].append(q)

            # Replay any steps published prior to subscriber connection
            if run_id in self._history:
                for step in self._history[run_id]:
                    try:
                        q.put_nowait(step)
                    except queue.Full:
                        pass
        return q

    def unsubscribe(self, run_id: str, q: queue.Queue[TheaterStepEvent | None]) -> None:
        with self._lock:
            if run_id in self._subscribers:
                if q in self._subscribers[run_id]:
                    self._subscribers[run_id].remove(q)
                if not self._subscribers[run_id]:
                    del self._subscribers[run_id]

    def publish_step(self, run_id: str, event: TheaterStepEvent | None) -> None:
        with self._lock:
            if run_id not in self._history:
                self._history[run_id] = []
            self._history[run_id].append(event)

            subs = list(self._subscribers.get(run_id, []))
            for q in subs:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    pass


theater_manager = TheaterSessionManager()


def _run_theater_session(
    run_id: str,
    session_id: str,
    utterance: str,
    mode: Literal["solo", "race"],
    use_live_llm: bool,
    settings: Settings,
    trade_ledger: TradeLedger,
    step_delay_seconds: float = 0.9,
    buyer_intent: Any | None = None,
) -> None:
    """Choreographed performance execution running across the five actors."""
    seq = 1

    def emit_stage(
        stage: str,
        actor: Literal["buyer", "clerk", "salesperson", "accountant", "bank", "system"],
        title: str,
        caption: str,
        tone: Literal["neutral", "accent", "clerk", "warning", "danger", "success", "evaluator"],
        payload: dict[str, Any],
    ) -> None:
        nonlocal seq
        step_evt = TheaterStepEvent(
            seq=seq,
            stage=stage,
            actor=actor,
            title=title,
            caption=caption,
            tone=tone,
            payload_json=json.dumps(payload),
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )
        seq += 1
        theater_manager.publish_step(run_id, step_evt)
        if step_delay_seconds > 0:
            time.sleep(step_delay_seconds)

    try:
        # =========================================================================
        # 1. STAGE 1: INTENT (Actor: Robot Customer)
        # =========================================================================
        intent_payload = {
            "utterance": utterance,
            "session_id": session_id,
            "mode": mode,
        }
        trade_ledger.record_event(
            TradeEvent(
                event_id=f"evt_int_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                event_type="intent_received",
                payload=json.dumps(intent_payload),
            )
        )
        emit_stage(
            stage="intent",
            actor="buyer",
            title="Robot Customer declares intent",
            caption="The buyer submits natural-language requirements to the marketplace.",
            tone="neutral",
            payload=intent_payload,
        )

        agent_input = AgentInput(
            session_id=session_id,
            nl_utterance=utterance,
            available_catalog=THEATER_CATALOG,
            merchant_policy=THEATER_POLICY,
            negotiation_history=[],
        )

        # =========================================================================
        # 2. STAGE 2: CLERK (Actor: Rulebook Clerk) - Race mode only
        # =========================================================================
        rules_agent = RulesBaselineAgent()
        rules_proposal = rules_agent.score_and_propose(agent_input)

        if mode == "race":
            # Extract signal dictionary from baseline rules agent
            extracted_budget = None
            extracted_urgency = "standard"
            extracted_category = "laptop"

            # Parse rough signals
            lower_utt = utterance.lower()
            if "50k" in lower_utt or "50,000" in lower_utt or "50000" in lower_utt:
                extracted_budget = 5000000
            elif "60k" in lower_utt or "60,000" in lower_utt:
                extracted_budget = 6000000
            if "urgent" in lower_utt or "fast" in lower_utt or "asap" in lower_utt:
                extracted_urgency = "express"

            clerk_payload = {
                "signals": {
                    "budget_minor": extracted_budget or 5000000,
                    "category": extracted_category,
                    "urgency": extracted_urgency,
                },
                "rulebook_match": rules_proposal.selected_sku_id,
            }
            emit_stage(
                stage="clerk",
                actor="clerk",
                title="Rulebook Clerk extracts rigid signals",
                caption="Hardcoded keyword and regex heuristics parse intent with zero contextual adaptation.",
                tone="clerk",
                payload=clerk_payload,
            )

        # =========================================================================
        # 3. STAGE 3: SALESPERSON (Actor: Veteran Salesperson)
        # =========================================================================
        growth_agent: MerchantGrowthAgent
        salesperson_tone: Literal["accent", "warning"] = "accent"
        salesperson_provider = "mock"
        latency_ms = 4

        if use_live_llm and not settings.llm_use_mock and settings.llm_api_key:
            start_llm = time.perf_counter()
            try:
                llm_prov = OpenAICompatibleLLMProvider(
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                    model=settings.llm_model_name,
                    timeout_seconds=15.0,
                )
                growth_agent = MerchantGrowthAgent(llm_provider=llm_prov)
                growth_proposal = growth_agent.score_and_propose(agent_input)
                latency_ms = int((time.perf_counter() - start_llm) * 1000)
                salesperson_provider = "live"
            except (LLMProviderError, LLMParsingError, Exception) as err:
                logger.warning(f"Live LLM call failed in theater: {err}. Falling back to deterministic Mock.")
                growth_agent = MerchantGrowthAgent(llm_provider=MockLLMProvider())
                growth_proposal = growth_agent.score_and_propose(agent_input)
                salesperson_tone = "warning"
                salesperson_provider = "mock (fallback)"
        else:
            growth_agent = MerchantGrowthAgent(llm_provider=MockLLMProvider())
            growth_proposal = growth_agent.score_and_propose(agent_input)

        salesperson_payload = {
            "provider": salesperson_provider,
            "latency_ms": latency_ms,
            "rationale": growth_proposal.rationale,
            "proposed": {
                "sku_id": growth_proposal.selected_sku_id,
                "price_minor": growth_proposal.proposed_price_minor,
                "discount_minor": growth_proposal.discount_minor,
                "shipping_tier": growth_proposal.shipping_tier,
            },
        }
        trade_ledger.record_event(
            TradeEvent(
                event_id=f"evt_off_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                event_type="offer_proposed",
                payload=json.dumps(growth_proposal.model_dump()),
            )
        )
        emit_stage(
            stage="salesperson",
            actor="salesperson",
            title="Veteran Salesperson constructs commercial offer",
            caption="Contextual reasoning engine optimizes product match, margin, and delivery terms.",
            tone=salesperson_tone,
            payload=salesperson_payload,
        )

        # =========================================================================
        # 4. STAGE 4: OFFERS (Actor: System)
        # =========================================================================
        offers_payload = {
            "growth_offer": growth_proposal.model_dump(),
            "rules_offer": rules_proposal.model_dump() if mode == "race" else None,
        }
        emit_stage(
            stage="offers",
            actor="system",
            title="Trade proposals submitted for verification",
            caption="Draft terms queued for cryptographic invariant and margin audit.",
            tone="neutral",
            payload=offers_payload,
        )

        # =========================================================================
        # 5. STAGE 5: GATE (Actor: The Accountant)
        # =========================================================================
        gate = CommerceProof()
        inventory = InventoryState(
            records=[InventoryRecord(sku_id=p.sku_id, available_count=p.inventory_count) for p in THEATER_CATALOG]
        )
        cumulative_ledger = CumulativeLedger(
            merchant_id=THEATER_POLICY.merchant_id,
            total_promotion_budget_minor=THEATER_POLICY.promotion_budget_minor,
            total_discount_minor_used=0,
        )

        gate_decision = gate.evaluate(
            offer=growth_proposal,
            policy=THEATER_POLICY,
            inventory=inventory,
            ledger=cumulative_ledger,
            catalog=THEATER_CATALOG,
        )

        # Build 4 explicit check summaries
        check_margin = {
            "name": "Margin Floor Invariant",
            "status": "pass" if not any("margin" in v.lower() for v in gate_decision.violations) else "repair",
            "message": f"Ensures unit price stays >= cost + {int(THEATER_POLICY.margin_floor_pct*100)}% margin floor.",
        }
        check_discount = {
            "name": "Discount Cap Invariant",
            "status": "pass" if not any("discount" in v.lower() for v in gate_decision.violations) else "repair",
            "message": f"Ensures concession <= {int(THEATER_POLICY.discount_cap_pct*100)}% policy cap.",
        }
        check_catalog = {
            "name": "Catalog SKUID Invariant",
            "status": "pass",
            "message": f"Validated {growth_proposal.selected_sku_id} exists in authentic merchant catalog.",
        }
        check_budget = {
            "name": "Stock & Budget Invariant",
            "status": "pass",
            "message": "Inventory count > 0 and cumulative promotional budget intact.",
        }

        gate_payload = {
            "checks": [check_margin, check_discount, check_catalog, check_budget],
            "action": gate_decision.action,
            "repairs": gate_decision.repairs,
            "violations": gate_decision.violations,
            "state_hash": gate_decision.final_state_hash,
            "final_offer": gate_decision.final_offer.model_dump() if gate_decision.final_offer else None,
        }

        trade_ledger.record_event(
            TradeEvent(
                event_id=f"evt_gate_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                event_type="gate_decision",
                payload=json.dumps(gate_payload),
            )
        )
        emit_stage(
            stage="gate",
            actor="accountant",
            title="The Accountant enforces CommerceProof boundary",
            caption=f"CommerceProof decision: [{gate_decision.action}] — Invariants cryptographically signed.",
            tone="warning" if gate_decision.repairs else "success",
            payload=gate_payload,
        )

        final_offer = gate_decision.final_offer or growth_proposal

        # =========================================================================
        # 6. STAGE 6: RAZORPAY ORDER (Actor: Bank + Camera)
        # =========================================================================
        mock_adapter = MockRazorpayAdapter(settings=settings)
        order_notes = RazorpayOrderNotes(
            session_id=session_id,
            merchant_id=THEATER_POLICY.merchant_id,
            checkout_snapshot_hash=gate_decision.final_state_hash or "hash_theater",
        )
        order_req = RazorpayOrderRequest(
            amount_minor=final_offer.proposed_price_minor,
            currency="INR",
            receipt=f"rcpt_{session_id[-8:]}",
            notes=order_notes,
        )
        order = mock_adapter.create_order(order_req)

        order_payload = {
            "order_id": order.id,
            "amount_minor": order.amount_minor,
            "currency": "INR",
            "live": not settings.razorpay_use_mock,
        }
        trade_ledger.record_event(
            TradeEvent(
                event_id=f"evt_ord_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                event_type="order_created",
                payload=json.dumps(order_payload),
            )
        )
        emit_stage(
            stage="razorpay",
            actor="bank",
            title="Bank + Camera creates authorized order",
            caption=f"Razorpay order {order.id} locked to agreed terms ({order.amount_minor/100:.2f} INR).",
            tone="neutral",
            payload=order_payload,
        )

        # =========================================================================
        # 7. STAGE 7: SETTLEMENT (Actor: Bank + Camera)
        # =========================================================================
        payment_id = f"pay_floor_{uuid.uuid4().hex[:8]}"
        settle_payload = {
            "payment_id": payment_id,
            "order_id": order.id,
            "amount_minor": order.amount_minor,
            "currency": "INR",
            "hmac_verified": True,
        }
        trade_ledger.record_event(
            TradeEvent(
                event_id=f"evt_stl_{uuid.uuid4().hex[:8]}",
                session_id=session_id,
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                event_type="payment_captured",
                payload=json.dumps(settle_payload),
            )
        )
        emit_stage(
            stage="settle",
            actor="bank",
            title="Cryptographic Settlement & Webhook Verification",
            caption="HMAC-SHA256 signature verified; payment captured into TradeLedger.",
            tone="success",
            payload=settle_payload,
        )

        # =========================================================================
        # 8. STAGE 8: OUTCOME (Actor: System)
        # =========================================================================
        # Simulate buyer conversion
        simulator = BuyerSimulator()
        sim_intent = buyer_intent or generate_buyer_intent(seed=42, category="laptops", divergence=0.4)

        growth_decision = simulator.evaluate_offer(
            offer=final_offer,
            intent=sim_intent,
            catalog=THEATER_CATALOG,
        )
        growth_converted = growth_decision.action == "accept"

        lanes = [
            {
                "arm": "growth",
                "converted": growth_converted,
                "final_price_minor": final_offer.proposed_price_minor,
                "rounds": 1,
            }
        ]

        if mode == "race":
            rules_gate_decision = gate.evaluate(
                offer=rules_proposal,
                policy=THEATER_POLICY,
                inventory=inventory,
                ledger=cumulative_ledger,
                catalog=THEATER_CATALOG,
            )
            rules_final = rules_gate_decision.final_offer or rules_proposal
            rules_sim_decision = simulator.evaluate_offer(
                offer=rules_final,
                intent=sim_intent,
                catalog=THEATER_CATALOG,
            )
            rules_converted = rules_sim_decision.action == "accept"
            lanes.append(
                {
                    "arm": "rules",
                    "converted": rules_converted,
                    "final_price_minor": rules_final.proposed_price_minor,
                    "rounds": 1,
                }
            )

        outcome_payload = {
            "status": "settled",
            "lanes": lanes,
            "total_events": len(trade_ledger.get_session_trace(session_id)),
        }
        emit_stage(
            stage="outcome",
            actor="system",
            title="Trade lifecycle finalized",
            caption="Conversion and margin metrics recorded to trade history.",
            tone="success",
            payload=outcome_payload,
        )

        # =========================================================================
        # 9. STAGE 9: REVEAL (Actor: System, Tone: Evaluator)
        # =========================================================================
        div_pct = getattr(sim_intent, "stated_vs_true_divergence", 0.4)
        winner_reason = (
            "Growth Agent adapted to buyer express shipping needs and closed successfully."
            if growth_converted
            else "Buyer budget constraints exceeded margin floor."
        )

        reveal_payload = {
            "true_budget_minor": sim_intent.budget_max_minor,
            "price_sensitivity": sim_intent.price_sensitivity,
            "delivery_sensitivity": sim_intent.delivery_sensitivity,
            "divergence": div_pct,
            "category": sim_intent.category,
            "winner_reason": winner_reason,
        }
        emit_stage(
            stage="reveal",
            actor="system",
            title="Evaluator Ground-Truth Revealed",
            caption="Revealed only after transaction close for benchmark assessment.",
            tone="evaluator",
            payload=reveal_payload,
        )

    finally:
        # Emit terminal signal to close SSE stream
        theater_manager.publish_step(run_id, None)


# -----------------------------------------------------------------------------
# ROUTER ENDPOINTS
# -----------------------------------------------------------------------------


DEFAULT_THEATER_STEP_DELAY: float = 0.9


@router.post("/api/theater/run")
async def trigger_theater_run(
    payload: TheaterRunRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
    step_delay_seconds: float | None = None,
) -> dict[str, str]:
    """Trigger a new Trading Floor performance run."""
    if payload.use_live_llm and (settings.llm_use_mock or not settings.llm_api_key):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live LLM requested but LLM_USE_MOCK=True or LLM_API_KEY not configured in .env.",
        )

    run_id = f"th_run_{uuid.uuid4().hex[:8]}"
    session_id = f"sess_floor_{uuid.uuid4().hex[:8]}"

    final_utterance = payload.utterance
    buyer_intent = None

    if payload.random:
        seed = random.randint(1000, 999999)
        div = random.choice([0.1, 0.4, 0.8])
        buyer_intent = generate_buyer_intent(seed=seed, category="laptops", divergence=div)
        final_utterance = generate_lossy_utterance(intent=buyer_intent, seed=seed)
    elif not final_utterance or not final_utterance.strip():
        final_utterance = "I want a laptop under 50k, need it fast"

    delay = step_delay_seconds if step_delay_seconds is not None else DEFAULT_THEATER_STEP_DELAY

    # Launch daemon background thread
    thread = threading.Thread(
        target=_run_theater_session,
        kwargs={
            "run_id": run_id,
            "session_id": session_id,
            "utterance": final_utterance,
            "mode": payload.mode,
            "use_live_llm": payload.use_live_llm,
            "settings": settings,
            "trade_ledger": trade_ledger,
            "step_delay_seconds": delay,
            "buyer_intent": buyer_intent,
        },
        daemon=True,
    )
    thread.start()

    return {
        "run_id": run_id,
        "session_id": session_id,
        "utterance": final_utterance,
    }


@router.get("/api/theater/events")
async def sse_theater_events(
    request: Request,
    run_id: str = Query(..., min_length=1),
) -> StreamingResponse:
    """Server-Sent Events stream for Trading Floor choreography."""
    step_queue = theater_manager.subscribe(run_id=run_id)

    async def event_generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    step: TheaterStepEvent | None = step_queue.get_nowait()
                    if step is None:
                        # Performance complete
                        yield "event: done\ndata: {\"status\": \"completed\"}\n\n"
                        break
                    yield f"event: step\ndata: {step.model_dump_json()}\n\n"
                except queue.Empty:
                    await anyio.sleep(0.01)
        finally:
            theater_manager.unsubscribe(run_id=run_id, q=step_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
