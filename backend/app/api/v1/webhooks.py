"""Stripe webhook endpoint — receives and processes Stripe events."""

import logging

import stripe
from fastapi import APIRouter, HTTPException, Request, status

from app.billing.stripe_client import construct_webhook_event
from app.billing.webhooks import (
    handle_checkout_session_completed,
    handle_invoice_paid,
    handle_invoice_payment_failed,
    handle_subscription_deleted,
    handle_subscription_updated,
)
from app.database import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# Map event types to handler functions
EVENT_HANDLERS = {
    "checkout.session.completed": handle_checkout_session_completed,
    "invoice.paid": handle_invoice_paid,
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_subscription_deleted,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Receive and process Stripe webhook events."""
    # 1. Read raw body (MUST be raw bytes for signature verification)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # 2. Verify signature
    try:
        event = construct_webhook_event(payload, sig_header)
    except stripe.SignatureVerificationError as e:
        logger.warning("Webhook signature verification failed")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e
    except ValueError as e:
        logger.warning("Invalid webhook payload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e

    # 3. Dispatch to handler
    handler = EVENT_HANDLERS.get(event.type)
    if handler is None:
        logger.debug("Unhandled webhook event type: %s", event.type)
        return {"status": "ignored"}

    logger.info("Processing webhook event: %s (id=%s)", event.type, event.id)

    # 4. Create own DB session (webhook has no auth context)
    async with async_session_factory() as db:
        try:
            await handler(db, event)
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.exception("Error processing webhook event %s", event.id)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Webhook processing failed",
            ) from e

    return {"status": "processed"}
