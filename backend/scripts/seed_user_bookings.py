"""Seed mock guests and bookings for an existing user's own properties.

Gives the agent realistic data to answer from (arrivals, occupancy, revenue,
special requests, guest history) without touching other users.

    docker compose exec backend python scripts/seed_user_bookings.py esakrissa.wayan@gmail.com
    docker compose exec backend python scripts/seed_user_bookings.py you@example.com --reset   # wipe + reseed
    docker compose exec backend python scripts/seed_user_bookings.py you@example.com --plan business

Idempotent: skips if the user already has bookings, unless --reset is given.
Booking dates are relative to today, so "arrivals this week" always has data.
"""

import argparse
import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

from app.database import async_session_factory, engine
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property
from app.models.subscription import Subscription
from app.models.user import User

GUESTS = [
    ("Aisha Rahman", "aisha.rahman.sg@example.com", "+65 9123 4501", "Singaporean", "Repeat guest. Prefers a quiet villa; vegetarian."),
    ("Marcus Tan", "marcus.tan@example.com", "+65 9876 2210", "Singaporean", "Travels for work; needs a desk and fast Wi-Fi."),
    ("Putri Ayu Lestari", "putri.lestari@example.com", "+62 812 3344 5566", "Indonesian", "Books for family from Jakarta."),
    ("Kenji Watanabe", "kenji.watanabe@example.com", "+81 90 1234 5678", "Japanese", "Honeymoon couple. Celebrating anniversary."),
    ("Olivia Brown", "olivia.brown@example.com", "+61 412 345 678", "Australian", "Surfer; asked about Canggu transfers."),
    ("Lucas Moreau", "lucas.moreau@example.com", "+33 6 12 34 56 78", "French", "Yoga retreat; early riser."),
    ("Hannah Schmidt", "hannah.schmidt@example.com", "+49 151 2345 6789", "German", "Allergic to nuts."),
    ("Wei Ling Chua", "weiling.chua@example.com", "+65 8234 5678", "Singaporean", "Travelling with two kids; needs a baby cot."),
    ("Daniel Kim", "daniel.kim.kr@example.com", "+82 10 2345 6789", "Korean", "Content creator; asked about drone rules."),
    ("Priya Nair", "priya.nair@example.com", "+91 98765 43210", "Indian", "Late arrival flights; needs night check-in."),
    ("James O'Connor", "james.oconnor@example.com", "+44 7700 900123", "British", "Left a 5-star review last stay."),
    ("Sofia Rossi", "sofia.rossi@example.com", "+39 333 123 4567", "Italian", "Asked for a private chef one evening."),
    ("Ryan Mitchell", "ryan.mitchell@example.com", "+1 415 555 0142", "American", "Group of friends; reminded about quiet hours."),
    ("Nurul Huda", "nurul.huda@example.com", "+60 12 345 6789", "Malaysian", "Requested halal food options nearby."),
]

SPECIAL_REQUESTS = [
    "Airport pickup from Ngurah Rai at 22:30.",
    "Baby cot and high chair, please.",
    "Late check-out until 15:00 if possible.",
    "Anniversary — flowers and a cake on arrival.",
    "Vegetarian breakfast every morning.",
    "Early check-in at 10:00, arriving on the red-eye.",
    "Quiet room away from the road; light sleeper.",
    None,
    None,
    None,
]

# (days from today for check-in, nights, guests, status, guest index, request index)
# Spread over ~6 weeks back and ~6 weeks ahead; no overlaps within a property.
SCHEDULE = [
    # property 0
    [(-40, 4, 2, "checked_out", 0, 4), (-21, 3, 2, "checked_out", 3, 3), (-2, 5, 2, "checked_in", 1, 6),
     (6, 3, 2, "confirmed", 9, 0), (15, 6, 3, "confirmed", 7, 1), (30, 4, 2, "pending", 12, 7)],
    # property 1
    [(-33, 5, 4, "checked_out", 2, 7), (-12, 4, 2, "checked_out", 10, 8), (0, 3, 2, "confirmed", 5, 5),
     (9, 2, 2, "cancelled", 8, 9), (12, 5, 4, "confirmed", 13, 4), (25, 3, 2, "pending", 6, 7)],
    # property 2
    [(-28, 6, 2, "checked_out", 6, 4), (-7, 4, 2, "checked_out", 4, 7), (2, 4, 2, "confirmed", 3, 3),
     (14, 3, 2, "confirmed", 11, 2), (22, 7, 2, "confirmed", 0, 6)],
    # property 3
    [(-36, 3, 2, "checked_out", 12, 8), (-15, 2, 1, "cancelled", 9, 9), (-4, 6, 2, "checked_in", 8, 9),
     (5, 2, 1, "confirmed", 1, 7), (18, 4, 2, "pending", 5, 8)],
    # property 4
    [(-25, 4, 3, "checked_out", 7, 1), (-9, 3, 2, "checked_out", 13, 7), (1, 5, 2, "confirmed", 10, 2),
     (11, 3, 2, "confirmed", 2, 0), (27, 5, 4, "pending", 4, 7)],
]

DEFAULT_CAPACITY = [4, 2, 4, 2, 6]
DEFAULT_AMENITIES = [
    ["pool", "wifi", "ac", "kitchen", "rice field view"],
    ["pool", "wifi", "ac", "breakfast", "garden"],
    ["infinity pool", "wifi", "ac", "jungle view", "yoga deck"],
    ["wifi", "ac", "breakfast", "shared pool"],
    ["private pool", "wifi", "ac", "kitchen", "rice field view", "bbq"],
]


async def seed(email: str, reset: bool, plan: str | None) -> None:
    today = date.today()
    async with async_session_factory() as session:
        user = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if user is None:
            sys.exit(f"No user with email {email}")

        props = list(
            (
                await session.execute(
                    select(Property).where(Property.owner_id == user.id).order_by(Property.created_at, Property.name)
                )
            ).scalars()
        )
        if not props:
            sys.exit(f"{email} has no properties — add some first")
        prop_ids = [p.id for p in props]

        existing = await session.scalar(select(func.count()).select_from(Booking).where(Booking.property_id.in_(prop_ids)))
        if existing and not reset:
            print(f"{email} already has {existing} bookings — use --reset to wipe and reseed.")
            return
        if reset:
            await session.execute(delete(Booking).where(Booking.property_id.in_(prop_ids)))
            await session.execute(delete(Guest).where(Guest.owner_id == user.id))
            await session.flush()

        # Fill in capacity/amenities the user left blank so availability checks make sense
        for i, p in enumerate(props):
            if not p.max_guests:
                p.max_guests = DEFAULT_CAPACITY[i % len(DEFAULT_CAPACITY)]
            if not p.amenities:
                p.amenities = DEFAULT_AMENITIES[i % len(DEFAULT_AMENITIES)]
            if not p.location:
                p.location = "Ubud, Bali"

        guests = []
        for name, guest_email, phone, nationality, notes in GUESTS:
            g = Guest(owner_id=user.id, name=name, email=guest_email, phone=phone, nationality=nationality, notes=notes)
            session.add(g)
            guests.append(g)
        await session.flush()

        count = 0
        for p_index, prop in enumerate(props):
            price = prop.base_price_per_night or Decimal("100.00")
            for offset, nights, n_guests, status, g_index, r_index in SCHEDULE[p_index % len(SCHEDULE)]:
                check_in = today + timedelta(days=offset)
                session.add(
                    Booking(
                        property_id=prop.id,
                        guest_id=guests[g_index].id,
                        check_in=check_in,
                        check_out=check_in + timedelta(days=nights),
                        num_guests=min(n_guests, prop.max_guests or n_guests),
                        status=status,
                        total_price=(price * nights).quantize(Decimal("0.01")),
                        special_requests=SPECIAL_REQUESTS[r_index],
                    )
                )
                count += 1

        if plan:
            sub = (await session.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one_or_none()
            if sub is None:
                session.add(Subscription(user_id=user.id, plan=plan, status="active"))
            else:
                sub.plan, sub.status = plan, "active"

        await session.commit()
        print(f"Seeded {len(guests)} guests and {count} bookings across {len(props)} properties for {email}"
              + (f" (plan → {plan})" if plan else ""))
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("email")
    parser.add_argument("--reset", action="store_true", help="delete this user's bookings and guests first")
    parser.add_argument("--plan", choices=["free", "pro", "business"], help="also set the user's plan (no Stripe)")
    args = parser.parse_args()
    asyncio.run(seed(args.email, args.reset, args.plan))
