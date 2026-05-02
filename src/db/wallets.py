"""Wallet CRUD + balance computation."""
from typing import Optional

import aiosqlite

from src import config

WALLET_TYPES = ('cash', 'bank', 'e_wallet', 'asset_gold')


async def list_active() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wallets WHERE deleted_at IS NULL ORDER BY id"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def count_active() -> int:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM wallets WHERE deleted_at IS NULL"
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get(wallet_id: int) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM wallets WHERE id = ? AND deleted_at IS NULL",
            (wallet_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create(
    name_en: Optional[str],
    name_ar: Optional[str],
    type: str,
    initial_balance_cents: int = 0,
) -> int:
    if type not in WALLET_TYPES:
        raise ValueError(f"invalid wallet type: {type}")
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO wallets (name_en, name_ar, type, initial_balance_cents)
            VALUES (?, ?, ?, ?)
            """,
            (name_en, name_ar, type, initial_balance_cents),
        )
        await db.commit()
        return cur.lastrowid


async def get_balance_cents(wallet_id: int) -> int:
    """initial + Σ ins − Σ outs across non-deleted transactions."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT initial_balance_cents FROM wallets WHERE id = ? AND deleted_at IS NULL",
            (wallet_id,),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                return 0
            balance = row[0]

        async with db.execute(
            """
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM transactions
            WHERE dest_wallet_id = ? AND deleted_at IS NULL
            """,
            (wallet_id,),
        ) as cur:
            balance += (await cur.fetchone())[0]

        async with db.execute(
            """
            SELECT COALESCE(SUM(amount_cents), 0)
            FROM transactions
            WHERE source_wallet_id = ? AND deleted_at IS NULL
            """,
            (wallet_id,),
        ) as cur:
            balance -= (await cur.fetchone())[0]

        return balance


async def get_net_worth_cents() -> int:
    total = 0
    for w in await list_active():
        if w['type'] in ('cash', 'bank', 'e_wallet'):
            total += await get_balance_cents(w['id'])
        elif w['type'] == 'asset_gold':
            grams_mg = w.get('gold_grams_milligrams') or 0
            price_cents = w.get('gold_price_per_gram_cents') or 0
            total += (grams_mg * price_cents) // 1000
    return total


async def soft_delete(wallet_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE wallets SET deleted_at = datetime('now') WHERE id = ?",
            (wallet_id,),
        )
        await db.commit()
