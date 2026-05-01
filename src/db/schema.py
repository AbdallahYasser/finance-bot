"""
Database schema for finance-bot.

M0 placeholder: only the `users` table and a seed for the allowed-users list.
Real entities (wallets, transactions, etc.) land in M1+.

Migrations are appended to the MIGRATIONS list — never modify existing entries.
Each is wrapped in try/except so re-running is safe.
"""
import logging

import aiosqlite

from src.config import DB_PATH, ALLOWED_USERS, DEFAULT_LANGUAGE, TIMEZONE

logger = logging.getLogger(__name__)


_CREATE_USERS = """
CREATE TABLE IF NOT EXISTS users (
    user_id              INTEGER PRIMARY KEY,
    language             TEXT    NOT NULL DEFAULT 'en',
    number_display_mode  TEXT    NOT NULL DEFAULT 'follow',
    timezone             TEXT    NOT NULL DEFAULT 'Africa/Cairo',
    salary_day           INTEGER,
    notification_prefs   TEXT,
    quiet_hours_start    TEXT,
    quiet_hours_end      TEXT,
    created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_ALLOWED_USERS = """
CREATE TABLE IF NOT EXISTS allowed_users (
    user_id   INTEGER PRIMARY KEY,
    added_at  TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""

_CREATE_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""

MIGRATIONS: list[tuple[str, str]] = [
    # ("migration_name", "SQL statement")
    # Add migrations here in order — never edit or remove existing ones.
]


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys = ON")
        await db.execute(_CREATE_USERS)
        await db.execute(_CREATE_ALLOWED_USERS)
        await db.execute(_CREATE_MIGRATIONS)

        for name, stmt in MIGRATIONS:
            async with db.execute(
                "SELECT 1 FROM schema_migrations WHERE name = ?", (name,)
            ) as cur:
                if await cur.fetchone():
                    continue
            try:
                await db.execute(stmt)
                await db.execute(
                    "INSERT INTO schema_migrations (name) VALUES (?)", (name,)
                )
                logger.info("Applied migration: %s", name)
            except Exception as e:
                logger.warning("Migration %s skipped or failed: %s", name, e)

        await db.commit()
    logger.info("Database initialized at %s", DB_PATH)


async def seed_allowed_users() -> None:
    """Seed allowed_users from ALLOWED_USERS env var on first run, then load into memory."""
    from src import state

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM allowed_users") as cur:
            rows = await cur.fetchall()

        if not rows and ALLOWED_USERS:
            for uid in ALLOWED_USERS:
                await db.execute(
                    "INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (uid,)
                )
                await db.execute(
                    """
                    INSERT OR IGNORE INTO users (user_id, language, timezone)
                    VALUES (?, ?, ?)
                    """,
                    (uid, DEFAULT_LANGUAGE, TIMEZONE),
                )
            await db.commit()
            rows = [(uid,) for uid in ALLOWED_USERS]

        state.allowed_users = {r[0] for r in rows}

    logger.info("Allowed users loaded: %d", len(state.allowed_users))
