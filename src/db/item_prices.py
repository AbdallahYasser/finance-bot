"""ItemPrice writes (M2 just inserts; M3 adds queries)."""
from typing import Optional

import aiosqlite

from src import config
from src.utils.dates import now_utc_iso


async def insert(
    item_id: int,
    place_id: int,
    price_cents: int,
    observed_at: Optional[str] = None,
    on_sale: int = 0,
    transaction_id: Optional[int] = None,
) -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO item_prices
              (item_id, place_id, price_cents, observed_at, on_sale, transaction_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, place_id, price_cents, observed_at or now_utc_iso(), on_sale, transaction_id),
        )
        await db.commit()
        return cur.lastrowid


async def list_for_item(item_id: int, limit: int = 20) -> list[dict]:
    """Recent observations for an item, used by M3's /price command."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM item_prices
            WHERE item_id = ?
            ORDER BY observed_at DESC
            LIMIT ?
            """,
            (item_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
