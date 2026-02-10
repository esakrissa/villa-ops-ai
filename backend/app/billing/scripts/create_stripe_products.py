"""Create Stripe products and prices in test mode.

Run once inside the backend container:
    python -m app.billing.scripts.create_stripe_products

Outputs price IDs to set in .env:
    STRIPE_PRO_PRICE_ID=price_xxx
    STRIPE_BUSINESS_PRICE_ID=price_xxx
"""

import asyncio

import stripe
from stripe import StripeClient

from app.config import settings


async def main() -> None:
    if not settings.stripe_secret_key:
        print("ERROR: STRIPE_SECRET_KEY is not set in .env")
        return

    client = StripeClient(
        settings.stripe_secret_key,
        http_client=stripe.HTTPXClient(),
    )

    # --- VillaOps Pro ($29/mo) ---
    pro_product = await client.v1.products.create_async(
        params={
            "name": "VillaOps Pro",
            "description": "5 properties, 500 AI queries/mo, full analytics, notifications",
        }
    )
    pro_price = await client.v1.prices.create_async(
        params={
            "product": pro_product.id,
            "unit_amount": 2900,
            "currency": "usd",
            "recurring": {"interval": "month"},
        }
    )
    print(f"Created product: {pro_product.name} ({pro_product.id})")
    print(f"  Price: $29.00/mo ({pro_price.id})")

    # --- VillaOps Business ($79/mo) ---
    biz_product = await client.v1.products.create_async(
        params={
            "name": "VillaOps Business",
            "description": "Unlimited properties, unlimited AI queries, full analytics + export, notifications, priority support",
        }
    )
    biz_price = await client.v1.prices.create_async(
        params={
            "product": biz_product.id,
            "unit_amount": 7900,
            "currency": "usd",
            "recurring": {"interval": "month"},
        }
    )
    print(f"Created product: {biz_product.name} ({biz_product.id})")
    print(f"  Price: $79.00/mo ({biz_price.id})")

    print("\n--- Add these to your .env ---")
    print(f"STRIPE_PRO_PRICE_ID={pro_price.id}")
    print(f"STRIPE_BUSINESS_PRICE_ID={biz_price.id}")


if __name__ == "__main__":
    asyncio.run(main())
