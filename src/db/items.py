"""Item CRUD + alias resolution + recent + fuzzy search."""
from typing import Optional

import aiosqlite

from src import config


async def list_active() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM items WHERE deleted_at IS NULL ORDER BY id DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get(item_id: int) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM items WHERE id = ? AND deleted_at IS NULL",
            (item_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create(
    canonical_name_en: Optional[str] = None,
    canonical_name_ar: Optional[str] = None,
    size: Optional[str] = None,
    unit: Optional[str] = None,
    default_category_id: Optional[int] = None,
) -> int:
    if not (canonical_name_en or canonical_name_ar):
        raise ValueError("at least one of canonical_name_en / canonical_name_ar required")

    en = (canonical_name_en or "").strip() or None
    ar = (canonical_name_ar or "").strip() or None
    size = (size or "").strip() or None
    unit = (unit or "").strip() or None

    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO items (canonical_name_en, canonical_name_ar, size, unit, default_category_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (en, ar, size, unit, default_category_id),
        )
        item_id = cur.lastrowid
        # Auto-create alias from each canonical name (typed variants accumulate later)
        for alias in (en, ar):
            if alias:
                await db.execute(
                    "INSERT OR IGNORE INTO item_aliases (item_id, alias_text) VALUES (?, ?)",
                    (item_id, alias),
                )
        await db.commit()
        return item_id


async def add_alias(item_id: int, alias_text: str) -> None:
    alias_text = alias_text.strip()
    if not alias_text:
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO item_aliases (item_id, alias_text) VALUES (?, ?)",
            (item_id, alias_text),
        )
        await db.commit()


async def soft_delete(item_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE items SET deleted_at = datetime('now') WHERE id = ?",
            (item_id,),
        )
        await db.commit()


async def recent(limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT i.*, MAX(t.occurred_at) AS last_used
            FROM items i
            LEFT JOIN transactions t ON t.item_id = i.id AND t.deleted_at IS NULL
            WHERE i.deleted_at IS NULL
            GROUP BY i.id
            ORDER BY (last_used IS NULL), last_used DESC, i.id DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def recent_at_place(place_id: int, limit: int = 5) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT i.*, MAX(t.occurred_at) AS last_used
            FROM items i
            JOIN transactions t ON t.item_id = i.id AND t.deleted_at IS NULL
            WHERE i.deleted_at IS NULL AND t.place_id = ?
            GROUP BY i.id
            ORDER BY last_used DESC, i.id DESC
            LIMIT ?
            """,
            (place_id, limit),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def aliases_for(item_id: int) -> list[str]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            "SELECT alias_text FROM item_aliases WHERE item_id = ? AND deleted_at IS NULL",
            (item_id,),
        ) as cur:
            return [r[0] for r in await cur.fetchall()]


async def all_search_choices() -> list[tuple[str, int]]:
    """All (label, item_id) pairs from canonical names + aliases for fuzzy ranking."""
    out: list[tuple[str, int]] = []
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute(
            """
            SELECT id, canonical_name_en, canonical_name_ar
            FROM items
            WHERE deleted_at IS NULL
            """
        ) as cur:
            for row in await cur.fetchall():
                iid, en, ar = row
                if en:
                    out.append((en, iid))
                if ar and ar != en:
                    out.append((ar, iid))
        async with db.execute(
            """
            SELECT a.item_id, a.alias_text
            FROM item_aliases a
            JOIN items i ON i.id = a.item_id
            WHERE a.deleted_at IS NULL AND i.deleted_at IS NULL
            """
        ) as cur:
            for iid, alias in await cur.fetchall():
                out.append((alias, iid))
    return out


def label(item: dict) -> str:
    """Display label: 'Water bottle (500ml)' or 'Water bottle'."""
    name = item.get("canonical_name_en") or item.get("canonical_name_ar") or "Item"
    size = item.get("size")
    if size:
        return f"{name} ({size})"
    return name
