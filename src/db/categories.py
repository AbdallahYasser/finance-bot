"""Category lookups."""
from typing import Optional

import aiosqlite

from src import config


async def list_by_kind(kind: str) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM categories
            WHERE kind = ? AND deleted_at IS NULL
            ORDER BY is_default DESC, id
            """,
            (kind,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get(category_id: int) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM categories WHERE id = ? AND deleted_at IS NULL",
            (category_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_by_name(name_en: str, kind: str) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM categories
            WHERE name_en = ? AND kind = ? AND deleted_at IS NULL
            """,
            (name_en, kind),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
