"""Notification MCP tool — compose and send templated guest notifications."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.mcp import get_session_factory, mcp
from app.models.booking import Booking
from app.models.guest import Guest

logger = logging.getLogger(__name__)

TEMPLATES = {
    "check_in_reminder": {
        "subject": "Reminder: Check-in at {property_name} on {check_in}",
        "body": (
            "Dear {guest_name},\n\n"
            "This is a friendly reminder that your check-in at {property_name} "
            "is scheduled for {check_in}.\n\n"
            "Property: {property_name}\n"
            "Location: {location}\n"
            "Check-in: {check_in}\n"
            "Check-out: {check_out}\n"
            "Guests: {num_guests}\n\n"
            "We look forward to welcoming you!\n\n"
            "Best regards,\nVillaOps AI"
        ),
    },
    "check_out_reminder": {
        "subject": "Reminder: Check-out from {property_name} on {check_out}",
        "body": (
            "Dear {guest_name},\n\n"
            "This is a reminder that your check-out from {property_name} "
            "is scheduled for {check_out}.\n\n"
            "We hope you enjoyed your stay!\n\n"
            "Best regards,\nVillaOps AI"
        ),
    },
    "booking_confirmation": {
        "subject": "Booking Confirmed: {property_name}",
        "body": (
            "Dear {guest_name},\n\n"
            "Your booking at {property_name} has been confirmed.\n\n"
            "Booking Details:\n"
            "- Property: {property_name}\n"
            "- Location: {location}\n"
            "- Check-in: {check_in}\n"
            "- Check-out: {check_out}\n"
            "- Guests: {num_guests}\n"
            "- Total Price: ${total_price}\n\n"
            "Thank you for choosing us!\n\n"
            "Best regards,\nVillaOps AI"
        ),
    },
    "booking_cancellation": {
        "subject": "Booking Cancelled: {property_name}",
        "body": (
            "Dear {guest_name},\n\n"
            "Your booking at {property_name} ({check_in} to {check_out}) "
            "has been cancelled.\n\n"
            "If you have any questions, please don't hesitate to contact us.\n\n"
            "Best regards,\nVillaOps AI"
        ),
    },
    "welcome": {
        "subject": "Welcome to {property_name}!",
        "body": (
            "Dear {guest_name},\n\n"
            "Welcome to {property_name}! We're delighted to have you.\n\n"
            "Your stay details:\n"
            "- Check-out: {check_out}\n"
            "- Guests: {num_guests}\n\n"
            "If you need anything during your stay, please let us know.\n\n"
            "Best regards,\nVillaOps AI"
        ),
    },
    "custom": {
        "subject": "{custom_subject}",
        "body": "{custom_message}",
    },
}

VALID_TEMPLATES = set(TEMPLATES.keys())


@mcp.tool()
async def send_notification(
    template: str,
    guest_id: str | None = None,
    guest_email: str | None = None,
    booking_id: str | None = None,
    custom_message: str | None = None,
) -> dict:
    """Compose and send a notification to a guest using a template.

    Args:
        template: Notification template — one of:
            "check_in_reminder", "check_out_reminder", "booking_confirmation",
            "booking_cancellation", "welcome", "custom"
        guest_id: UUID of the guest (looks up name and email)
        guest_email: Direct email address (alternative to guest_id)
        booking_id: UUID of the related booking (used to fill template variables)
        custom_message: Custom message body (required for "custom" template)

    Returns:
        Dict with composed notification details (recipient, subject, body) and status.
    """
    if template not in VALID_TEMPLATES:
        return {
            "error": f"Invalid template '{template}'. Must be one of: {', '.join(sorted(VALID_TEMPLATES))}",
            "status": "failed",
        }

    if not guest_id and not guest_email:
        return {
            "error": "Either guest_id or guest_email must be provided.",
            "status": "failed",
        }

    if template == "custom" and not custom_message:
        return {
            "error": "custom_message is required when using the 'custom' template.",
            "status": "failed",
        }

    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            # Resolve guest
            guest = None
            if guest_id:
                try:
                    guest = await session.get(Guest, uuid.UUID(guest_id))
                except ValueError:
                    return {"error": f"Invalid guest_id: '{guest_id}'", "status": "failed"}
            elif guest_email:
                result = await session.execute(
                    select(Guest).where(Guest.email.ilike(guest_email))
                )
                guest = result.scalar_one_or_none()

            if guest is None:
                identifier = guest_id or guest_email
                return {"error": f"Guest not found: '{identifier}'", "status": "failed"}

            # Resolve booking if provided
            booking = None
            prop = None
            if booking_id:
                try:
                    result = await session.execute(
                        select(Booking)
                        .where(Booking.id == uuid.UUID(booking_id))
                        .options(selectinload(Booking.property))
                    )
                    booking = result.scalar_one_or_none()
                except ValueError:
                    return {"error": f"Invalid booking_id: '{booking_id}'", "status": "failed"}

                if booking is None:
                    return {"error": f"Booking not found: '{booking_id}'", "status": "failed"}
                prop = booking.property

            # Build template variables
            template_vars = {
                "guest_name": guest.name,
                "guest_email": guest.email,
                "property_name": prop.name if prop else "N/A",
                "location": prop.location if prop else "N/A",
                "check_in": booking.check_in.isoformat() if booking else "N/A",
                "check_out": booking.check_out.isoformat() if booking else "N/A",
                "num_guests": str(booking.num_guests) if booking else "N/A",
                "total_price": str(booking.total_price) if booking and booking.total_price else "N/A",
                "custom_subject": f"Message for {guest.name}",
                "custom_message": custom_message or "",
            }

            # Render template
            tmpl = TEMPLATES[template]
            subject = tmpl["subject"].format(**template_vars)
            body = tmpl["body"].format(**template_vars)

            # Log the notification (simulated send)
            logger.info(
                "Notification sent [%s] to %s <%s>: %s",
                template, guest.name, guest.email, subject,
            )

            return {
                "status": "simulated",
                "notification": {
                    "recipient_name": guest.name,
                    "recipient_email": guest.email,
                    "subject": subject,
                    "body": body,
                    "template_used": template,
                },
            }
    except Exception as e:
        logger.exception("send_notification failed")
        return {"error": str(e), "status": "failed"}
