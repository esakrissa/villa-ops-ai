"""Seed the database with realistic Bali villa sample data.

Data inspired by real Booking.com listings retrieved via RapidAPI:
- Le Ayu Villa Canggu (hotel_id: 14922170) — Canggu, 2BR, ~$129/night, rated 9.6
- Pitu, a Punggul Village Escape (hotel_id: 12517649) — Sangeh/Ubud, ~$86/night, rated 9.7
- Da Vinci The Villa by Nagisa Bali (hotel_id: 12213698) — Canggu, 3BR, ~$350/night, rated 9.8
- Umah Anyar Villas Ubud (hotel_id: 13706617) — Ubud, 1BR, ~$163/night, rated 9.7
- Capung Asri Eco Luxury Resort (hotel_id: 9844997) — Ubud, 1BR, ~$122/night, rated 9.0

Run inside Docker:
    docker compose exec backend python -m scripts.seed_data
"""

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Add backend to path so imports work when run as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.auth.passwords import hash_password
from app.database import async_session_factory, engine
from app.models.booking import Booking
from app.models.guest import Guest
from app.models.property import Property
from app.models.subscription import Subscription
from app.models.user import User

# ---------------------------------------------------------------------------
# Seed data definitions
# ---------------------------------------------------------------------------

DEMO_USER = {
    "email": "demo@villaops.ai",
    "password": "demo1234",
    "name": "Demo Manager",
}

# Real Bali villa data sourced from Booking.com via RapidAPI (Feb 2026)
PROPERTIES = [
    {
        "name": "Le Ayu Villa Canggu",
        "description": (
            "A stunning 2-bedroom private pool villa in the heart of Canggu, Bali. "
            "Boasting a private entrance, this air-conditioned villa features 2 separate "
            "bedrooms, a living room, and 3 bathrooms with bath and shower. The well-equipped "
            "kitchen includes a stovetop, refrigerator, and kitchenware. Enjoy mountain and "
            "garden views from the terrace, plus a flat-screen TV with streaming services. "
            "Located on Jl. Raya Tumbak Bayuh, Pererenan — minutes from Canggu's best surf "
            "breaks and beach clubs."
        ),
        "location": "Canggu, Bali",
        "property_type": "villa",
        "max_guests": 4,
        "base_price_per_night": Decimal("129.00"),
        "amenities": [
            "private_pool",
            "wifi",
            "ac",
            "kitchen",
            "balcony",
            "terrace",
            "garden_view",
            "mountain_view",
            "bathtub",
            "streaming_tv",
            "parking",
            "room_service",
        ],
        "status": "active",
    },
    {
        "name": "Pitu Village Escape",
        "description": (
            "Nestled in the peaceful village of Punggul near Sangeh, this exceptional "
            "villa offers a serene Balinese countryside escape. Surrounded by lush gardens "
            "with an outdoor pool and terrace, the property provides accommodations with "
            "free private parking. All rooms feature a balcony with pool or garden views, "
            "a private bathroom with shower and free toiletries, plus complimentary WiFi. "
            "An à la carte breakfast is served daily. Bike and car rental available. "
            "7.5 miles from Ubud's Monkey Forest."
        ),
        "location": "Sangeh, Ubud, Bali",
        "property_type": "villa",
        "max_guests": 2,
        "base_price_per_night": Decimal("86.00"),
        "amenities": [
            "pool",
            "wifi",
            "garden",
            "terrace",
            "balcony",
            "parking",
            "breakfast",
            "room_service",
            "bike_rental",
            "concierge",
        ],
        "status": "active",
    },
    {
        "name": "Da Vinci Villa by Nagisa",
        "description": (
            "A magnificent 3-bedroom luxury villa in Canggu featuring 1,000 m² of living "
            "space with 4 living rooms and 3 bathrooms. This exceptional property includes "
            "breakfast and offers an unparalleled Bali experience with private pool, lush "
            "tropical gardens, and dedicated staff. Located in the sought-after Tumbak Bayuh "
            "area of Canggu, close to Echo Beach and Batu Bolong. Perfect for families "
            "or groups seeking the ultimate villa holiday."
        ),
        "location": "Canggu, Bali",
        "property_type": "villa",
        "max_guests": 8,
        "base_price_per_night": Decimal("350.00"),
        "amenities": [
            "private_pool",
            "wifi",
            "ac",
            "kitchen",
            "garden",
            "breakfast",
            "parking",
            "staff",
            "bbq",
            "laundry",
            "airport_shuttle",
        ],
        "status": "active",
    },
    {
        "name": "Umah Anyar Villas Ubud",
        "description": (
            "A charming private villa set amidst the rice terraces of Bedahulu, near Ubud. "
            "This intimate retreat features a bedroom with en-suite bathroom, a private "
            "pool, and stunning valley views. The villa offers a blend of traditional "
            "Balinese architecture and modern comforts. Located just 15 minutes from "
            "Ubud's art markets and the famous Tegallalang Rice Terraces. An ideal base "
            "for exploring Bali's cultural heartland."
        ),
        "location": "Ubud, Bali",
        "property_type": "villa",
        "max_guests": 2,
        "base_price_per_night": Decimal("163.00"),
        "amenities": [
            "private_pool",
            "wifi",
            "ac",
            "valley_view",
            "garden",
            "terrace",
            "parking",
            "breakfast",
        ],
        "status": "active",
    },
    {
        "name": "Capung Asri Eco Resort",
        "description": (
            "An eco-luxury resort in Bedahulu offering spacious 200 m² villas with "
            "private pools, 2 beds, a living room, and full bathroom. Breakfast included "
            "daily. Set in a lush tropical environment with commitment to sustainable "
            "tourism. The resort features a yoga pavilion, organic garden, and spa "
            "treatments. Located near Goa Gajah (Elephant Cave) and the Petanu River "
            "valley, offering authentic Balinese cultural immersion."
        ),
        "location": "Ubud, Bali",
        "property_type": "guesthouse",
        "max_guests": 4,
        "base_price_per_night": Decimal("122.00"),
        "amenities": [
            "private_pool",
            "wifi",
            "ac",
            "breakfast",
            "spa",
            "yoga",
            "organic_garden",
            "parking",
            "eco_friendly",
        ],
        "status": "active",
    },
]

GUESTS = [
    {
        "name": "Emma Thompson",
        "email": "emma.thompson@gmail.com",
        "phone": "+61412345678",
        "nationality": "Australian",
        "notes": "Prefers ground floor, allergic to shellfish",
    },
    {
        "name": "James Wilson",
        "email": "j.wilson@outlook.com",
        "phone": "+447911123456",
        "nationality": "British",
        "notes": "Returning guest — loves Villa Canggu",
    },
    {
        "name": "Sarah Chen",
        "email": "sarah.chen@yahoo.com",
        "phone": "+14155551234",
        "nationality": "American",
        "notes": None,
    },
    {
        "name": "Klaus Mueller",
        "email": "k.mueller@web.de",
        "phone": "+491711234567",
        "nationality": "German",
        "notes": "Vegan diet, requests plant-based breakfast options",
    },
    {
        "name": "Marie Dubois",
        "email": "m.dubois@free.fr",
        "phone": "+33612345678",
        "nationality": "French",
        "notes": None,
    },
    {
        "name": "Yuki Tanaka",
        "email": "yuki.tanaka@docomo.ne.jp",
        "phone": "+819012345678",
        "nationality": "Japanese",
        "notes": "Honeymoon trip — please arrange flowers",
    },
    {
        "name": "Liam O'Brien",
        "email": "liam.obrien@gmail.com",
        "phone": "+61423456789",
        "nationality": "Australian",
        "notes": None,
    },
    {
        "name": "Ananya Sharma",
        "email": "ananya.sharma@gmail.com",
        "phone": "+919876543210",
        "nationality": "Indian",
        "notes": "Vegetarian, traveling with elderly parents",
    },
    {
        "name": "Henrik Johansson",
        "email": "henrik.j@telia.se",
        "phone": "+46701234567",
        "nationality": "Swedish",
        "notes": None,
    },
    {
        "name": "Olivia Martinez",
        "email": "olivia.m@hotmail.com",
        "phone": "+34612345678",
        "nationality": "Spanish",
        "notes": "Needs airport transfer arranged",
    },
    {
        "name": "David Kim",
        "email": "david.kim@naver.com",
        "phone": "+821012345678",
        "nationality": "South Korean",
        "notes": None,
    },
    {
        "name": "Sophia Rossi",
        "email": "sophia.rossi@libero.it",
        "phone": None,
        "nationality": "Italian",
        "notes": "Anniversary celebration — special dinner request",
    },
    {
        "name": "Lucas van Dijk",
        "email": "l.vandijk@ziggo.nl",
        "phone": "+31612345678",
        "nationality": "Dutch",
        "notes": None,
    },
    {
        "name": "Chloe Williams",
        "email": "chloe.w@xtra.co.nz",
        "phone": "+64211234567",
        "nationality": "New Zealander",
        "notes": "Surfer — wants early check-in near Canggu breaks",
    },
    {
        "name": "Ahmed Hassan",
        "email": "ahmed.hassan@gmail.com",
        "phone": "+971501234567",
        "nationality": "Emirati",
        "notes": "Halal food options required",
    },
]


def _build_bookings(
    properties: list[Property],
    guests: list[Guest],
    today: date,
) -> list[dict]:
    """Generate 22 bookings spread across properties with realistic data.

    Rules:
    - No date conflicts for non-cancelled bookings on the same property
    - Mix of statuses: pending, confirmed, checked_in, checked_out, cancelled
    - Dates spread across past, present, and future
    """
    p = {prop.name: prop for prop in properties}
    g = {guest.name: guest for guest in guests}

    bookings_data = [
        # --- Le Ayu Villa Canggu ($129/night) ---
        # Past: checked_out
        {
            "property": p["Le Ayu Villa Canggu"],
            "guest": g["James Wilson"],
            "check_in": today - timedelta(days=30),
            "check_out": today - timedelta(days=25),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Late check-out if possible",
        },
        # Past: checked_out
        {
            "property": p["Le Ayu Villa Canggu"],
            "guest": g["Chloe Williams"],
            "check_in": today - timedelta(days=20),
            "check_out": today - timedelta(days=15),
            "num_guests": 1,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Extra surfboard storage needed",
        },
        # Current: checked_in
        {
            "property": p["Le Ayu Villa Canggu"],
            "guest": g["Emma Thompson"],
            "check_in": today - timedelta(days=2),
            "check_out": today + timedelta(days=5),
            "num_guests": 2,
            "status": "checked_in",
            "nights": 7,
            "special_requests": "Ground floor preferred, shellfish allergy",
        },
        # Future: confirmed
        {
            "property": p["Le Ayu Villa Canggu"],
            "guest": g["Sarah Chen"],
            "check_in": today + timedelta(days=10),
            "check_out": today + timedelta(days=14),
            "num_guests": 2,
            "status": "confirmed",
            "nights": 4,
            "special_requests": None,
        },
        # --- Pitu Village Escape ($86/night) ---
        # Past: checked_out
        {
            "property": p["Pitu Village Escape"],
            "guest": g["Yuki Tanaka"],
            "check_in": today - timedelta(days=45),
            "check_out": today - timedelta(days=40),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Honeymoon — flower arrangement please",
        },
        # Past: cancelled
        {
            "property": p["Pitu Village Escape"],
            "guest": g["Henrik Johansson"],
            "check_in": today - timedelta(days=25),
            "check_out": today - timedelta(days=20),
            "num_guests": 1,
            "status": "cancelled",
            "nights": 5,
            "special_requests": None,
        },
        # Current: checked_in
        {
            "property": p["Pitu Village Escape"],
            "guest": g["Marie Dubois"],
            "check_in": today - timedelta(days=1),
            "check_out": today + timedelta(days=6),
            "num_guests": 2,
            "status": "checked_in",
            "nights": 7,
            "special_requests": None,
        },
        # Future: pending
        {
            "property": p["Pitu Village Escape"],
            "guest": g["Ananya Sharma"],
            "check_in": today + timedelta(days=15),
            "check_out": today + timedelta(days=22),
            "num_guests": 2,
            "status": "pending",
            "nights": 7,
            "special_requests": "Vegetarian meals, traveling with elderly parents",
        },
        # --- Da Vinci Villa by Nagisa ($350/night) ---
        # Past: checked_out
        {
            "property": p["Da Vinci Villa by Nagisa"],
            "guest": g["Liam O'Brien"],
            "check_in": today - timedelta(days=60),
            "check_out": today - timedelta(days=53),
            "num_guests": 6,
            "status": "checked_out",
            "nights": 7,
            "special_requests": "Family reunion — need all bedrooms set up",
        },
        # Past: checked_out
        {
            "property": p["Da Vinci Villa by Nagisa"],
            "guest": g["Olivia Martinez"],
            "check_in": today - timedelta(days=40),
            "check_out": today - timedelta(days=35),
            "num_guests": 4,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Airport transfer on arrival and departure",
        },
        # Past: cancelled
        {
            "property": p["Da Vinci Villa by Nagisa"],
            "guest": g["Klaus Mueller"],
            "check_in": today - timedelta(days=10),
            "check_out": today - timedelta(days=5),
            "num_guests": 3,
            "status": "cancelled",
            "nights": 5,
            "special_requests": "Vegan breakfast options daily",
        },
        # Future: confirmed
        {
            "property": p["Da Vinci Villa by Nagisa"],
            "guest": g["David Kim"],
            "check_in": today + timedelta(days=7),
            "check_out": today + timedelta(days=14),
            "num_guests": 5,
            "status": "confirmed",
            "nights": 7,
            "special_requests": None,
        },
        # Future: pending
        {
            "property": p["Da Vinci Villa by Nagisa"],
            "guest": g["Ahmed Hassan"],
            "check_in": today + timedelta(days=20),
            "check_out": today + timedelta(days=27),
            "num_guests": 8,
            "status": "pending",
            "nights": 7,
            "special_requests": "Halal catering for all meals, 8 guests total",
        },
        # --- Umah Anyar Villas Ubud ($163/night) ---
        # Past: checked_out
        {
            "property": p["Umah Anyar Villas Ubud"],
            "guest": g["Sophia Rossi"],
            "check_in": today - timedelta(days=50),
            "check_out": today - timedelta(days=45),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Anniversary dinner at the villa",
        },
        # Past: checked_out
        {
            "property": p["Umah Anyar Villas Ubud"],
            "guest": g["Lucas van Dijk"],
            "check_in": today - timedelta(days=35),
            "check_out": today - timedelta(days=28),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 7,
            "special_requests": None,
        },
        # Current: checked_in
        {
            "property": p["Umah Anyar Villas Ubud"],
            "guest": g["Klaus Mueller"],
            "check_in": today - timedelta(days=3),
            "check_out": today + timedelta(days=4),
            "num_guests": 2,
            "status": "checked_in",
            "nights": 7,
            "special_requests": "Plant-based breakfast every morning",
        },
        # Future: confirmed
        {
            "property": p["Umah Anyar Villas Ubud"],
            "guest": g["James Wilson"],
            "check_in": today + timedelta(days=8),
            "check_out": today + timedelta(days=12),
            "num_guests": 2,
            "status": "confirmed",
            "nights": 4,
            "special_requests": None,
        },
        # --- Capung Asri Eco Resort ($122/night) ---
        # Past: checked_out
        {
            "property": p["Capung Asri Eco Resort"],
            "guest": g["Henrik Johansson"],
            "check_in": today - timedelta(days=55),
            "check_out": today - timedelta(days=48),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 7,
            "special_requests": None,
        },
        # Past: checked_out
        {
            "property": p["Capung Asri Eco Resort"],
            "guest": g["Emma Thompson"],
            "check_in": today - timedelta(days=15),
            "check_out": today - timedelta(days=10),
            "num_guests": 2,
            "status": "checked_out",
            "nights": 5,
            "special_requests": "Interested in yoga sessions",
        },
        # Future: confirmed
        {
            "property": p["Capung Asri Eco Resort"],
            "guest": g["Yuki Tanaka"],
            "check_in": today + timedelta(days=5),
            "check_out": today + timedelta(days=12),
            "num_guests": 2,
            "status": "confirmed",
            "nights": 7,
            "special_requests": "Daily spa treatment booking",
        },
        # Future: pending
        {
            "property": p["Capung Asri Eco Resort"],
            "guest": g["Ananya Sharma"],
            "check_in": today + timedelta(days=25),
            "check_out": today + timedelta(days=32),
            "num_guests": 4,
            "status": "pending",
            "nights": 7,
            "special_requests": "Vegetarian meals for 3 guests, wheelchair access needed",
        },
        # Future: cancelled
        {
            "property": p["Capung Asri Eco Resort"],
            "guest": g["Sarah Chen"],
            "check_in": today + timedelta(days=18),
            "check_out": today + timedelta(days=21),
            "num_guests": 1,
            "status": "cancelled",
            "nights": 3,
            "special_requests": None,
        },
    ]

    return bookings_data


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------


async def seed() -> None:
    """Populate the database with realistic Bali villa sample data.

    Idempotent: checks if demo user exists, deletes and re-seeds all
    associated data to ensure a clean state.
    """
    async with async_session_factory() as session:
        # Check if demo user already exists
        result = await session.execute(select(User).where(User.email == DEMO_USER["email"]))
        existing_user = result.scalar_one_or_none()

        if existing_user is not None:
            print(f"⚠️  Demo user '{DEMO_USER['email']}' already exists. Deleting and re-seeding...")
            # Delete dependents explicitly to avoid ORM cascade setting
            # owner_id=NULL (User.properties relationship lacks cascade config,
            # while the DB-level ON DELETE CASCADE won't fire via ORM delete).
            user_property_ids = [p.id for p in existing_user.properties]
            if user_property_ids:
                await session.execute(delete(Booking).where(Booking.property_id.in_(user_property_ids)))
                await session.execute(delete(Property).where(Property.id.in_(user_property_ids)))
            await session.execute(delete(Subscription).where(Subscription.user_id == existing_user.id))
            await session.flush()
            # Now safe to remove the user (no dangling FK references)
            await session.execute(delete(User).where(User.id == existing_user.id))
            await session.flush()

        # Also clear all guests (they're shared, not cascade-deleted with user)
        await session.execute(delete(Guest))
        await session.flush()

        # ------------------------------------------------------------------
        # 1. Create demo user
        # ------------------------------------------------------------------
        user = User(
            email=DEMO_USER["email"],
            hashed_password=hash_password(DEMO_USER["password"]),
            name=DEMO_USER["name"],
            auth_provider="local",
            is_active=True,
            role="manager",
        )
        session.add(user)
        await session.flush()

        # ------------------------------------------------------------------
        # 2. Create free subscription
        # ------------------------------------------------------------------
        subscription = Subscription(
            user_id=user.id,
            plan="free",
            status="active",
        )
        session.add(subscription)
        await session.flush()

        print(f"✅ Created demo user: {user.email} (id={user.id})")

        # ------------------------------------------------------------------
        # 3. Create properties
        # ------------------------------------------------------------------
        created_properties: list[Property] = []
        for prop_data in PROPERTIES:
            prop = Property(
                owner_id=user.id,
                **prop_data,
            )
            session.add(prop)
            await session.flush()
            created_properties.append(prop)
            print(f"   🏠 {prop.name} — {prop.location} (${prop.base_price_per_night}/night)")

        # ------------------------------------------------------------------
        # 4. Create guests
        # ------------------------------------------------------------------
        created_guests: list[Guest] = []
        for guest_data in GUESTS:
            guest = Guest(owner_id=user.id, **guest_data)
            session.add(guest)
            await session.flush()
            created_guests.append(guest)

        print(f"✅ Created {len(created_guests)} guests")

        # ------------------------------------------------------------------
        # 5. Create bookings
        # ------------------------------------------------------------------
        today = date.today()
        bookings_data = _build_bookings(created_properties, created_guests, today)
        booking_count = 0

        for bdata in bookings_data:
            prop: Property = bdata["property"]
            nights = bdata["nights"]
            total_price = prop.base_price_per_night * nights if prop.base_price_per_night else None

            booking = Booking(
                property_id=prop.id,
                guest_id=bdata["guest"].id,
                check_in=bdata["check_in"],
                check_out=bdata["check_out"],
                num_guests=bdata["num_guests"],
                status=bdata["status"],
                total_price=total_price,
                special_requests=bdata["special_requests"],
            )
            session.add(booking)
            booking_count += 1

        await session.flush()
        await session.commit()

        print(f"✅ Created {booking_count} bookings")
        print()
        print("=" * 60)
        print("📊 Seed Summary")
        print("=" * 60)
        print(f"   Users:         1 (demo@villaops.ai / demo1234)")
        print(f"   Subscriptions: 1 (free plan)")
        print(f"   Properties:    {len(created_properties)}")
        print(f"   Guests:        {len(created_guests)}")
        print(f"   Bookings:      {booking_count}")
        print("=" * 60)
        print("🎉 Done! You can now log in at /api/v1/auth/login")


if __name__ == "__main__":
    asyncio.run(seed())
