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


class AgentInput(BaseModel):
    """The strict boundary contract for all decision agents (Rules and LLM).

    Contains only buyer-facing information (utterance), available catalog,
    and merchant commercial policy. Ground-truth buyer preferences (BuyerIntent)
    and evaluation metadata are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(min_length=1)
    nl_utterance: str = Field(min_length=1)
    available_catalog: list[Product] = Field(min_length=1)
    merchant_policy: MerchantPolicy


class ExtractedSignals(BaseModel):
    """Deterministic signals extracted from buyer natural language utterance."""

    model_config = ConfigDict(extra="forbid")

    estimated_budget_minor: int | None = Field(default=None, ge=0)
    estimated_category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    urgency_level: Literal["low", "medium", "high"] = "medium"


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


