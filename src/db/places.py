"""Place CRUD + search + recent."""
from typing import Optional

import aiosqlite

from src import config


async def list_active() -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM places WHERE deleted_at IS NULL ORDER BY id DESC"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get(place_id: int) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM places WHERE id = ? AND deleted_at IS NULL",
            (place_id,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create(branch_name: str, chain_name: Optional[str] = None) -> int:
    branch_name = branch_name.strip()
    if not branch_name:
        raise ValueError("branch_name required")
    chain = chain_name.strip() if chain_name else None
    if chain == "":
        chain = None

    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO places (branch_name, chain_name)
            VALUES (?, ?)
            """,
            (branch_name, chain),
        )
        await db.commit()
        return cur.lastrowid


async def get_by_branch_chain(branch_name: str, chain_name: Optional[str]) -> Optional[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if chain_name is None:
            async with db.execute(
                "SELECT * FROM places WHERE branch_name = ? AND chain_name IS NULL AND deleted_at IS NULL",
                (branch_name,),
            ) as cur:
                row = await cur.fetchone()
        else:
            async with db.execute(
                "SELECT * FROM places WHERE branch_name = ? AND chain_name = ? AND deleted_at IS NULL",
                (branch_name, chain_name),
            ) as cur:
                row = await cur.fetchone()
        return dict(row) if row else None


async def soft_delete(place_id: int) -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE places SET deleted_at = datetime('now') WHERE id = ?",
            (place_id,),
        )
        await db.commit()


async def recent(limit: int = 5) -> list[dict]:
    """Places ordered by most recent transaction usage."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT p.*, MAX(t.occurred_at) AS last_used
            FROM places p
            LEFT JOIN transactions t ON t.place_id = p.id AND t.deleted_at IS NULL
            WHERE p.deleted_at IS NULL
            GROUP BY p.id
            ORDER BY (last_used IS NULL), last_used DESC, p.id DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


def label(place: dict) -> str:
    """Human-readable place label, e.g. 'Carrefour Maadi · Carrefour'."""
    branch = place.get("branch_name") or ""
    chain = place.get("chain_name") or ""
    if chain and chain != branch:
        return f"{branch} · {chain}"
    return branch
