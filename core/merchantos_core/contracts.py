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


class Product(BaseModel):
    """Product entity in the merchant's catalog."""

    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    cost_minor: int = Field(ge=0)
    base_price_minor: int = Field(ge=0)
    inventory_count: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_price_ge_cost(self) -> "Product":
        """Ensure base_price_minor is at least cost_minor."""
        if self.base_price_minor < self.cost_minor:
            raise ValueError(
                f"base_price_minor ({self.base_price_minor}) must be greater than or equal to cost_minor ({self.cost_minor})"
            )
        return self


class MerchantPolicy(BaseModel):
    """Commercial rules and constraints defined by the merchant."""

    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1)
    margin_floor_pct: float = Field(ge=0.0, le=1.0)
    discount_cap_pct: float = Field(ge=0.0, le=1.0)
    promotion_budget_minor: int = Field(ge=0)


class BuyerIntent(BaseModel):
    """Ground truth buyer intent and internal preferences (NEVER sent to agents)."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    budget_max_minor: int = Field(ge=0)
    delivery_days_max: int = Field(ge=1)
    priority: list[str] = Field(default_factory=list)
    hard_exclusions: list[str] = Field(default_factory=list)
    price_sensitivity: float = Field(ge=0.0, le=1.0)
    delivery_sensitivity: float = Field(ge=0.0, le=1.0)
    acceptance_threshold: float = Field(ge=0.0, le=1.0)
    stated_vs_true_divergence: float = Field(ge=0.0, le=1.0)


class SimulatedScenario(BaseModel):
    """Complete simulation scenario combining buyer intent, lossy NL, catalog, and merchant policy."""

    model_config = ConfigDict(extra="forbid")

    scenario_id: str = Field(min_length=1)
    intent: BuyerIntent
    nl_utterance: str = Field(min_length=1)
    available_catalog: list[Product] = Field(min_length=1)
    merchant_policy: MerchantPolicy


class ProposedOffer(BaseModel):
    """Commercial offer generated by a decision agent for a buyer session."""

    model_config = ConfigDict(extra="forbid")

    offer_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    selected_sku_id: str = Field(min_length=1)
    proposed_price_minor: int = Field(ge=0)
    discount_minor: int = Field(ge=0)
    shipping_tier: Literal["standard", "express"]
    rationale: str = Field(min_length=1)


class NegotiationEvent(BaseModel):
    """Single turn event in a multi-round negotiation between merchant and buyer."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    round: int = Field(ge=1)
    actor: Literal["merchant_agent", "buyer_agent"]
    message_type: Literal["initial_offer", "counter_offer", "accept", "reject"]
    offer_id: str | None = None
    proposed_offer: ProposedOffer | None = None
    reason_text: str = Field(default="")


class BuyerResponse(BaseModel):
    """Evaluation response generated by the buyer simulator."""

    model_config = ConfigDict(extra="forbid")

    action: Literal["accept", "reject", "counter"]
    reason: str
    counter_utterance: str | None = None


class NegotiationSessionState(BaseModel):
    """Full state of a negotiation session across multiple turns."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    status: Literal["in_progress", "accepted", "rejected", "max_rounds_reached"]
    current_round: int = Field(ge=0)
    history: list[NegotiationEvent] = Field(default_factory=list)
    final_offer: ProposedOffer | None = None


class LLMOutput(BaseModel):
    """Strict structured output contract expected from LLM generation."""

    model_config = ConfigDict(extra="forbid")

    selected_sku_id: str = Field(min_length=1)
    proposed_price_minor: int = Field(ge=0)
    discount_minor: int = Field(ge=0)
    shipping_tier: Literal["standard", "express"]
    rationale: str = Field(min_length=1)


class AgentInput(BaseModel):
    """The strict boundary contract for all decision agents (Rules and LLM).

    Contains only buyer-facing information (utterance), available catalog,
    merchant commercial policy, and negotiation history. Ground-truth buyer
    preferences (BuyerIntent) and evaluation metadata are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    nl_utterance: str = Field(min_length=1)
    available_catalog: list[Product] = Field(min_length=1)
    merchant_policy: MerchantPolicy
    negotiation_history: list[NegotiationEvent] = Field(default_factory=list)


class ExtractedSignals(BaseModel):
    """Deterministic signals extracted from buyer natural language utterance."""

    model_config = ConfigDict(extra="forbid")

    estimated_budget_minor: int | None = Field(default=None, ge=0)
    estimated_category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    urgency_level: Literal["low", "medium", "high"] = "medium"


class InventoryRecord(BaseModel):
    """Stock level record for a specific SKU."""

    model_config = ConfigDict(extra="forbid")

    sku_id: str = Field(min_length=1)
    available_count: int = Field(ge=0)


class InventoryState(BaseModel):
    """Snapshot of inventory availability across SKUs."""

    model_config = ConfigDict(extra="forbid")

    records: list[InventoryRecord]


class CumulativeLedger(BaseModel):
    """Cumulative financial ledger tracking merchant promotion budget consumption."""

    model_config = ConfigDict(extra="forbid")

    merchant_id: str = Field(min_length=1)
    total_promotion_budget_minor: int = Field(ge=0)
    total_discount_minor_used: int = Field(ge=0)


class PolicyCheck(BaseModel):
    """Individual policy validation check result."""

    model_config = ConfigDict(extra="forbid")

    check_name: str = Field(min_length=1)
    status: Literal["pass", "fail", "repaired"]
    message: str = Field(min_length=1)


class CommerceDecision(BaseModel):
    """Deterministic decision generated by the CommerceProof control layer."""

    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    action: Literal["EXECUTE", "REPAIR", "ESCALATE", "BLOCK"]
    violations: list[str] = Field(default_factory=list)
    repairs: list[str] = Field(default_factory=list)
    checks: list[PolicyCheck] = Field(default_factory=list)
    original_offer_id: str = Field(min_length=1)
    final_offer: ProposedOffer | None = None
    final_state_hash: str | None = None


class ArmResult(BaseModel):
    """Execution result for a single scenario under a specific agent arm and gate."""

    model_config = ConfigDict(extra="forbid")

    arm_name: Literal["rules_baseline", "growth_agent"]
    scenario_id: str = Field(min_length=1)
    status: Literal["converted", "rejected", "max_rounds_reached", "blocked_by_gate"]
    final_price_minor: int | None = Field(default=None, ge=0)
    final_discount_minor: int | None = Field(default=None, ge=0)
    negotiation_rounds: int = Field(ge=0)
    gate_rejections: int = Field(ge=0)
    gate_repairs: int = Field(ge=0)
    contribution_margin_minor: int | None = None


class EvaluationMetrics(BaseModel):
    """Aggregated statistical metrics for an evaluation arm."""

    model_config = ConfigDict(extra="forbid")

    total_scenarios: int = Field(ge=0)
    conversion_rate: float = Field(ge=0.0, le=1.0)
    avg_contribution_margin_minor: float
    avg_negotiation_rounds: float = Field(ge=0.0)
    gate_rejection_rate: float = Field(ge=0.0, le=1.0)
    repair_rate: float = Field(ge=0.0, le=1.0)


class DivergenceBucket(BaseModel):
    """Paired evaluation metrics grouped by stated-vs-true buyer intent divergence."""

    model_config = ConfigDict(extra="forbid")

    bucket_name: Literal["low", "medium", "high"]
    divergence_range: str = Field(min_length=1)
    rules_metrics: EvaluationMetrics
    growth_metrics: EvaluationMetrics
    conversion_delta: float
    margin_delta_minor: float


class EvaluationReport(BaseModel):
    """Comprehensive paired evaluation report comparing rules baseline and growth agent."""

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    dataset: Literal["dev", "heldout"]
    overall_rules_metrics: EvaluationMetrics
    overall_growth_metrics: EvaluationMetrics
    divergence_buckets: list[DivergenceBucket]


TradeEventType = Literal[
    "intent_received",
    "offer_proposed",
    "gate_decision",
    "order_created",
    "payment_captured",
    "payment_failed",
    "error",
]


class TradeEvent(BaseModel):
    """Immutable audit trail event in the trade ledger."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    event_type: Literal[
        "intent_received",
        "offer_proposed",
        "gate_decision",
        "order_created",
        "payment_captured",
        "payment_failed",
        "error",
    ]
    payload: str = Field(description="JSON-serialized string of event payload")


class LedgerEntry(BaseModel):
    """Aggregated session trace containing chronological trade events."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    events: list[TradeEvent] = Field(default_factory=list)


class ValidationCheckResult(BaseModel):
    """Result of an individual validation check (hermetic or live)."""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: Literal["hermetic", "live_razorpay", "live_llm"]
    status: Literal["pass", "fail", "skipped"]
    latency_ms: int | None = Field(default=None, ge=0)
    detail: str
    evidence_json: str = Field(default="", description="serialized evidence; empty string if none")
    timestamp: str = Field(min_length=1)


class ValidationReport(BaseModel):
    """Aggregated report of a complete validation run across checks."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    scope: Literal["hermetic", "live", "all"]
    started_at: str = Field(min_length=1)
    finished_at: str | None = None
    overall_status: Literal["running", "pass", "fail"]
    results: list[ValidationCheckResult] = Field(default_factory=list)






