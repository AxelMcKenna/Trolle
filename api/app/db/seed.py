from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete

from app.db.models import Price, Product, Store
from app.db.session import get_async_session

CHAINS = ["countdown", "new_world", "paknsave"]
CATEGORIES = ["Fruit & Vegetables", "Meat & Seafood", "Dairy & Eggs", "Bakery", "Pantry", "Frozen"]
BRANDS = ["Anchor", "Tip Top", "Pams", "Meadow Fresh", "Sanitarium", "Watties", "Eta"]
DEPARTMENTS = [
    ("Fruit & Vegetables", "Apples & Pears"),
    ("Fruit & Vegetables", "Bananas"),
    ("Meat & Seafood", "Chicken"),
    ("Meat & Seafood", "Beef & Veal"),
    ("Dairy & Eggs", "Milk"),
    ("Dairy & Eggs", "Cheese"),
    ("Bakery", "Bread"),
    ("Pantry", "Rice, Pasta & Noodles"),
    ("Frozen", "Frozen Vegetables"),
    ("Frozen", "Ice Cream"),
]


async def seed() -> None:
    async with get_async_session() as session:
        await session.execute(delete(Price))
        await session.execute(delete(Product))
        await session.execute(delete(Store))
        stores = []
        for chain in CHAINS:
            for index in range(3):
                store = Store(
                    id=uuid4(),
                    name=f"{chain.replace('_', ' ').title()} Store {index+1}",
                    chain=chain,
                    lat=-36.85 + random.uniform(-0.5, 0.5),
                    lon=174.76 + random.uniform(-0.5, 0.5),
                    address=f"{100+index} Example Street",
                    region="Auckland",
                )
                session.add(store)
                stores.append(store)
        await session.flush()

        for i in range(60):
            chain = random.choice(CHAINS)
            brand = random.choice(BRANDS)
            department, subcategory = random.choice(DEPARTMENTS)
            category = random.choice(CATEGORIES)
            size = random.choice(["500g", "1kg", "2L", "1L", "750ml", "300g", "6 pack", "100g"])
            unit_price = round(random.uniform(0.50, 15.00), 2)
            unit_measure = random.choice(["1kg", "100g", "1L", "100ml", "1ea"])
            product = Product(
                id=uuid4(),
                chain=chain,
                source_product_id=f"seed-{i}",
                name=f"{brand} {subcategory} #{i}",
                brand=brand,
                category=category,
                department=department,
                subcategory=subcategory,
                size=size,
                unit_price=unit_price,
                unit_measure=unit_measure,
            )
            session.add(product)
            store = random.choice([s for s in stores if s.chain == chain])
            price_value = random.uniform(1.0, 25.0)
            promo_price = price_value * 0.9 if random.random() < 0.3 else None
            price = Price(
                id=uuid4(),
                product_id=product.id,
                store_id=store.id,
                price_nzd=round(price_value, 2),
                promo_price_nzd=round(promo_price, 2) if promo_price else None,
                promo_text="10% off" if promo_price else None,
                last_seen_at=datetime.now(timezone.utc),
                price_last_changed_at=datetime.now(timezone.utc),
                is_member_only=False,
            )
            session.add(price)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
