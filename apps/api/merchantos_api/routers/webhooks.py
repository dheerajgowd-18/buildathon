"""Razorpay webhook handler endpoint."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from merchantos_api.deps import get_settings
from merchantos_core.config import Settings
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
    x_razorpay_signature: Annotated[str | None, Header(alias="X-Razorpay-Signature")] = None,
) -> JSONResponse:
    """
    Handle inbound Razorpay webhooks.

    Reads raw body bytes, verifies HMAC SHA256 signature against effective webhook secret,
    and parses into strictly typed events without performing money movement or database writes.
    """
    raw_body = await request.body()
    secret = settings.get_effective_webhook_secret()

    result = process_webhook_payload(
        raw_body=raw_body,
        signature_header=x_razorpay_signature,
        secret=secret,
    )

    response_payload = WebhookEndpointResponse(
        status=result.status,
        message=result.message,
        event_type=result.event_type,
    ).model_dump(mode="json")

    if result.status in ("rejected", "invalid_payload"):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=response_payload,
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_payload,
    )
