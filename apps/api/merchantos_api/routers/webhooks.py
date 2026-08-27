"""Razorpay webhook handler endpoint."""

from datetime import datetime, timezone
import json
from typing import Annotated, Literal
import uuid

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from merchantos_api.deps import get_settings, get_trade_ledger
from merchantos_core.config import Settings
from merchantos_core.contracts import (
    RazorpayPaymentCapturedEvent,
    RazorpayPaymentFailedEvent,
    TradeEvent,
)
from merchantos_core.ledger.trade_ledger import TradeLedger
from merchantos_razorpay.webhook import process_webhook_payload

router = APIRouter(tags=["webhooks"])


class WebhookEndpointResponse(BaseModel):
    """Response payload for webhook operations."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["processed", "ignored", "rejected", "invalid_payload"]
    message: str
    event_type: str | None = None


@router.post(
    "/webhooks/razorpay",
    response_model=WebhookEndpointResponse,
    responses={
        200: {"model": WebhookEndpointResponse, "description": "Webhook processed or ignored"},
        400: {"model": WebhookEndpointResponse, "description": "Rejected or invalid payload"},
    },
)
async def razorpay_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    trade_ledger: Annotated[TradeLedger, Depends(get_trade_ledger)],
    x_razorpay_signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
) -> JSONResponse:
    """
    Handle inbound Razorpay webhooks.

    Reads raw body bytes, verifies HMAC SHA256 signature against effective webhook secret,
    cross-references payment terms against the TradeLedger to defend against cart mutations,
    and updates session audit trails without performing unverified state changes.
    """
    raw_body = await request.body()
    secret = settings.get_effective_webhook_secret()

    result = process_webhook_payload(
        raw_body=raw_body,
        signature_header=x_razorpay_signature,
        secret=secret,
    )

    if result.status in ("rejected", "invalid_payload"):
        response_payload = WebhookEndpointResponse(
            status=result.status,
            message=result.message,
            event_type=result.event_type,
        ).model_dump(mode="json")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=response_payload,
        )

    if result.status == "ignored":
        response_payload = WebhookEndpointResponse(
            status="ignored",
            message=result.message,
            event_type=result.event_type,
        ).model_dump(mode="json")
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=response_payload,
        )

    # For validly signed and parsed events, cross-reference against TradeLedger and log audit events
    timestamp_now = datetime.now(timezone.utc).isoformat()

    if isinstance(result.event, RazorpayPaymentCapturedEvent):
        payment_entity = result.event.payload.entity
        order_id = payment_entity.order_id
        payment_id = payment_entity.id
        amount_minor = payment_entity.amount_minor

        # Defense-in-depth: Check for registered order in TradeLedger to defend against cart mutation
        expected_amount_minor = trade_ledger.get_expected_amount_for_order(order_id)
        session_id = trade_ledger.get_session_id_for_order(order_id) or order_id

        if expected_amount_minor is not None and amount_minor != expected_amount_minor:
            # Cart mutation attack detected: tampered amount
            error_event = TradeEvent(
                event_id=f"evt_err_{uuid.uuid4().hex[:12]}",
                session_id=session_id,
                timestamp=timestamp_now,
                event_type="error",
                payload=json.dumps(
                    {
                        "error": "cart_mutation_tampered_amount",
                        "order_id": order_id,
                        "payment_id": payment_id,
                        "captured_amount_minor": amount_minor,
                        "expected_amount_minor": expected_amount_minor,
                        "message": f"Payment amount {amount_minor} does not match approved checkout amount {expected_amount_minor}",
                    }
                ),
            )
            trade_ledger.record_event(error_event)

            response_payload = WebhookEndpointResponse(
                status="rejected",
                message=f"Cart mutation rejected: payment amount {amount_minor} does not match approved checkout amount {expected_amount_minor}",
                event_type="payment.captured",
            ).model_dump(mode="json")
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content=response_payload,
            )

        # Valid payment captured: record in ledger
        captured_event = TradeEvent(
            event_id=f"evt_cap_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            timestamp=timestamp_now,
            event_type="payment_captured",
            payload=json.dumps(
                {
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "amount_minor": amount_minor,
                    "currency": payment_entity.currency,
                    "status": "captured",
                }
            ),
        )
        trade_ledger.record_event(captured_event)

    elif isinstance(result.event, RazorpayPaymentFailedEvent):
        payment_entity = result.event.payload.entity
        order_id = payment_entity.order_id
        payment_id = payment_entity.id
        session_id = trade_ledger.get_session_id_for_order(order_id) or order_id

        failed_event = TradeEvent(
            event_id=f"evt_fail_{uuid.uuid4().hex[:12]}",
            session_id=session_id,
            timestamp=timestamp_now,
            event_type="payment_failed",
            payload=json.dumps(
                {
                    "order_id": order_id,
                    "payment_id": payment_id,
                    "amount_minor": payment_entity.amount_minor,
                    "error_code": payment_entity.error_code,
                    "error_description": payment_entity.error_description,
                    "status": "failed",
                }
            ),
        )
        trade_ledger.record_event(failed_event)

    response_payload = WebhookEndpointResponse(
        status="processed",
        message=result.message,
        event_type=result.event_type,
    ).model_dump(mode="json")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_payload,
    )

