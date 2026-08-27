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
