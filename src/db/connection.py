"""
aiosqlite connection helper. Always opens with WAL mode + foreign keys.
"""
import aiosqlite
from contextlib import asynccontextmanager

from src.config import DB_PATH


@asynccontextmanager
async def db_conn():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = aiosqlite.Row
        yield conn
