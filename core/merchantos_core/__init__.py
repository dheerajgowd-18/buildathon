"""MerchantOS AI Core Package."""

from merchantos_core.config import Settings
from merchantos_core.contracts import (
    CheckoutLineItem,
    CheckoutSnapshot,
    CurrencyINR,
    RazorpayOrder,
    RazorpayOrderNotes,
    RazorpayOrderRequest,
    RazorpayOrderStatus,
    RazorpayPaymentCapturedEvent,
    RazorpayPaymentEntity,
    RazorpayPaymentFailedEvent,
    RazorpayPaymentStatus,
    RazorpayWebhookEventName,
    RazorpayWebhookPaymentPayload,
    UnknownWebhookEvent,
    Product,
    MerchantPolicy,
    BuyerIntent,
    SimulatedScenario,
    AgentInput,
    ExtractedSignals,
    ProposedOffer,
)
from merchantos_core.agents.rules_baseline import RulesBaselineAgent
from merchantos_core.hashing import canonical_checkout_hash, sha256_hex

__all__ = [
    "Settings",
    "CurrencyINR",
    "RazorpayOrderStatus",
    "RazorpayPaymentStatus",
    "RazorpayWebhookEventName",
    "CheckoutLineItem",
    "CheckoutSnapshot",
    "RazorpayOrderNotes",
    "RazorpayOrderRequest",
    "RazorpayOrder",
    "RazorpayPaymentEntity",
    "RazorpayWebhookPaymentPayload",
    "RazorpayPaymentCapturedEvent",
    "RazorpayPaymentFailedEvent",
    "UnknownWebhookEvent",
    "Product",
    "MerchantPolicy",
    "BuyerIntent",
    "SimulatedScenario",
    "AgentInput",
    "ExtractedSignals",
    "ProposedOffer",
    "RulesBaselineAgent",
    "sha256_hex",
    "canonical_checkout_hash",
]

