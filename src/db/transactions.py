"""Transaction insert + query helpers.

Each insert validates the field combination required by its type:
- spend  → source_wallet_id, no dest_wallet_id
- income → dest_wallet_id, no source_wallet_id
- transfer → both, must differ
- refund → source_wallet_id + refund_of_id
"""
from typing import Optional

import aiosqlite

from src import config
from src.utils.dates import now_utc_iso as _now_utc_iso


async def insert_spend(
    amount_cents: int,
    source_wallet_id: int,
    category_id: Optional[int],
    note: Optional[str] = None,
    occurred_at: Optional[str] = None,
    item_id: Optional[int] = None,
    place_id: Optional[int] = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("amount must be > 0")
    if not source_wallet_id:
        raise ValueError("source_wallet_id required for spend")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO transactions
              (type, amount_cents, source_wallet_id, category_id,
               item_id, place_id, note, occurred_at, source)
            VALUES ('spend', ?, ?, ?, ?, ?, ?, ?, 'manual')
            """,
            (amount_cents, source_wallet_id, category_id,
             item_id, place_id, note, occurred_at or _now_utc_iso()),
        )
        await db.commit()
        return cur.lastrowid


async def insert_income(
    amount_cents: int,
    dest_wallet_id: int,
    category_id: Optional[int],
    note: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("amount must be > 0")
    if not dest_wallet_id:
        raise ValueError("dest_wallet_id required for income")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO transactions
              (type, amount_cents, dest_wallet_id, category_id, note, occurred_at, source)
            VALUES ('income', ?, ?, ?, ?, ?, 'manual')
            """,
            (amount_cents, dest_wallet_id, category_id, note, occurred_at or _now_utc_iso()),
        )
        await db.commit()
        return cur.lastrowid


async def insert_transfer(
    amount_cents: int,
    source_wallet_id: int,
    dest_wallet_id: int,
    note: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("amount must be > 0")
    if source_wallet_id == dest_wallet_id:
        raise ValueError("source and destination wallets must differ")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO transactions
              (type, amount_cents, source_wallet_id, dest_wallet_id, note, occurred_at, source)
            VALUES ('transfer', ?, ?, ?, ?, ?, 'manual')
            """,
            (amount_cents, source_wallet_id, dest_wallet_id, note, occurred_at or _now_utc_iso()),
        )
        await db.commit()
        return cur.lastrowid


async def insert_refund(
    amount_cents: int,
    dest_wallet_id: int,
    refund_of_id: int,
    category_id: Optional[int] = None,
    note: Optional[str] = None,
    occurred_at: Optional[str] = None,
) -> int:
    if amount_cents <= 0:
        raise ValueError("amount must be > 0")
    if not dest_wallet_id:
        raise ValueError("dest_wallet_id required for refund")
    if not refund_of_id:
        raise ValueError("refund_of_id required for refund")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO transactions
              (type, amount_cents, dest_wallet_id, category_id, refund_of_id, note, occurred_at, source)
            VALUES ('refund', ?, ?, ?, ?, ?, ?, 'manual')
            """,
            (amount_cents, dest_wallet_id, category_id, refund_of_id, note,
             occurred_at or _now_utc_iso()),
        )
        await db.commit()
        return cur.lastrowid


async def update_occurred_at(tx_id: int, new_iso_utc: str) -> bool:
    """Set occurred_at on a non-deleted transaction. Returns True if a row updated."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE transactions SET occurred_at = ? WHERE id = ? AND deleted_at IS NULL",
            (new_iso_utc, tx_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get(tx_id: int) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT t.*,
                   c.name_en  AS category_name,
                   c.name_ar  AS category_name_ar,
                   c.icon     AS category_icon,
                   sw.name_en AS source_name,    sw.name_ar AS source_name_ar,
                   dw.name_en AS dest_name,      dw.name_ar AS dest_name_ar,
                   i.canonical_name_en AS item_name,
                   i.canonical_name_ar AS item_name_ar,
                   i.size              AS item_size,
                   p.branch_name       AS place_branch,
                   p.chain_name        AS place_chain
            FROM transactions t
            LEFT JOIN categories c  ON c.id  = t.category_id
            LEFT JOIN wallets   sw ON sw.id = t.source_wallet_id
            LEFT JOIN wallets   dw ON dw.id = t.dest_wallet_id
            LEFT JOIN items     i  ON i.id  = t.item_id
            LEFT JOIN places    p  ON p.id  = t.place_id
            WHERE t.id = ? AND t.deleted_at IS NULL
            """,
            (tx_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def recent(limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT t.*,
                   c.name_en  AS category_name,
                   c.icon     AS category_icon,
                   i.canonical_name_en AS item_name,
                   i.size              AS item_size,
                   p.branch_name       AS place_branch
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            LEFT JOIN items     i ON i.id = t.item_id
            LEFT JOIN places    p ON p.id = t.place_id
            WHERE t.deleted_at IS NULL
            ORDER BY t.occurred_at DESC, t.id DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]
