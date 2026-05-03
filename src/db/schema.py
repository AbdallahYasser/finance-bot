"""
Database schema for finance-bot.

Migrations are appended to the MIGRATIONS list — never modify existing entries.
Each is wrapped in try/except so re-running is safe; the schema_migrations table
records which have been applied.

DB_PATH and other config values are accessed lazily via `src.config` so that
tests can monkeypatch them without reloading modules.
"""
import logging

import aiosqlite

from src import config

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
    ("M1_0001_create_wallets", """
        CREATE TABLE IF NOT EXISTS wallets (
            id                              INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar                         TEXT,
            name_en                         TEXT,
            type                            TEXT NOT NULL CHECK (type IN ('cash','bank','e_wallet','asset_gold')),
            initial_balance_cents           INTEGER NOT NULL DEFAULT 0,
            last_reconciled_at              TEXT,
            last_reconciled_balance_cents   INTEGER,
            karat                           INTEGER,
            gold_grams_milligrams           INTEGER,
            gold_price_per_gram_cents       INTEGER,
            gold_price_updated_at           TEXT,
            created_at                      TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at                      TEXT
        )
    """),
    ("M1_0002_create_categories", """
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id   INTEGER REFERENCES categories(id),
            name_ar     TEXT,
            name_en     TEXT,
            kind        TEXT NOT NULL CHECK (kind IN ('expense','income','transfer','adjustment')) DEFAULT 'expense',
            icon        TEXT,
            is_default  INTEGER NOT NULL DEFAULT 0,
            deleted_at  TEXT
        )
    """),
    ("M1_0003_create_transactions", """
        CREATE TABLE IF NOT EXISTS transactions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            type                TEXT NOT NULL CHECK (type IN (
                                  'spend','income','transfer','refund',
                                  'lend','borrow','repay_in','repay_out','forgive',
                                  'gold_buy','gold_sell','reconcile_adjust'
                                )),
            amount_cents        INTEGER NOT NULL CHECK (amount_cents > 0),
            source_wallet_id    INTEGER REFERENCES wallets(id),
            dest_wallet_id      INTEGER REFERENCES wallets(id),
            category_id         INTEGER REFERENCES categories(id),
            item_id             INTEGER,
            place_id            INTEGER,
            person_id           INTEGER,
            refund_of_id        INTEGER REFERENCES transactions(id),
            debt_id             INTEGER,
            occurred_at         TEXT NOT NULL,
            note                TEXT,
            photo_file_id       TEXT,
            sms_inbox_id        INTEGER,
            is_draft            INTEGER NOT NULL DEFAULT 0,
            source              TEXT NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','sms','recurring','wizard')),
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at          TEXT
        )
    """),
    ("M1_0004_idx_tx_occurred_at",
        "CREATE INDEX IF NOT EXISTS idx_tx_occurred_at ON transactions(occurred_at)"),
    ("M1_0005_idx_tx_source_wallet",
        "CREATE INDEX IF NOT EXISTS idx_tx_source_wallet ON transactions(source_wallet_id, occurred_at)"),
    ("M1_0006_idx_tx_dest_wallet",
        "CREATE INDEX IF NOT EXISTS idx_tx_dest_wallet ON transactions(dest_wallet_id, occurred_at)"),
    ("M1_0007_idx_tx_category",
        "CREATE INDEX IF NOT EXISTS idx_tx_category ON transactions(category_id, occurred_at)"),
    ("M1_0008_seed_default_categories", """
        INSERT INTO categories (name_en, name_ar, kind, icon, is_default) VALUES
          ('Food',         'الطعام',    'expense', '🍴', 1),
          ('Transport',    'المواصلات', 'expense', '🚗', 1),
          ('Bills',        'الفواتير',  'expense', '💡', 1),
          ('Shopping',     'التسوق',    'expense', '🛍', 1),
          ('Entertainment','الترفيه',   'expense', '🎬', 1),
          ('Health',       'الصحة',     'expense', '🏥', 1),
          ('Gifts',        'الهدايا',   'expense', '🎁', 1),
          ('Other',        'أخرى',      'expense', '📦', 1),
          ('Salary',       'الراتب',    'income',  '💰', 1),
          ('Bonus',        'مكافأة',   'income',  '🎉', 1),
          ('Refund',       'استرجاع',  'income',  '🔄', 1),
          ('Other Income', 'دخل آخر',   'income',  '➕', 1)
    """),
    ("M2_0001_create_places", """
        CREATE TABLE IF NOT EXISTS places (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            branch_name  TEXT NOT NULL,
            chain_name   TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at   TEXT,
            UNIQUE(branch_name, chain_name)
        )
    """),
    ("M2_0002_create_items", """
        CREATE TABLE IF NOT EXISTS items (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_name_en    TEXT,
            canonical_name_ar    TEXT,
            size                 TEXT,
            unit                 TEXT,
            default_category_id  INTEGER REFERENCES categories(id),
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            deleted_at           TEXT
        )
    """),
    ("M2_0003_create_item_aliases", """
        CREATE TABLE IF NOT EXISTS item_aliases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL REFERENCES items(id),
            alias_text  TEXT NOT NULL,
            deleted_at  TEXT,
            UNIQUE(item_id, alias_text)
        )
    """),
    ("M2_0004_create_item_prices", """
        CREATE TABLE IF NOT EXISTS item_prices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id         INTEGER NOT NULL REFERENCES items(id),
            place_id        INTEGER NOT NULL REFERENCES places(id),
            price_cents     INTEGER NOT NULL CHECK (price_cents >= 0),
            observed_at     TEXT NOT NULL,
            on_sale         INTEGER NOT NULL DEFAULT 0,
            transaction_id  INTEGER REFERENCES transactions(id),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """),
    ("M2_0005_idx_item_aliases_text",
        "CREATE INDEX IF NOT EXISTS idx_item_aliases_text ON item_aliases(alias_text COLLATE NOCASE)"),
    ("M2_0006_idx_item_prices",
        "CREATE INDEX IF NOT EXISTS idx_item_prices ON item_prices(item_id, place_id, observed_at DESC)"),
    ("M2_0007_idx_items_canonical_en",
        "CREATE INDEX IF NOT EXISTS idx_items_canonical_en ON items(canonical_name_en COLLATE NOCASE)"),
    ("M2_0008_seed_subcategories", """
        INSERT INTO categories (parent_id, name_en, name_ar, kind, icon, is_default)
        SELECT p.id, sub.name_en, sub.name_ar, 'expense', sub.icon, 1
        FROM categories p
        JOIN (
          SELECT 'Food' AS parent, 'Breakfast'         AS name_en, 'فطار'        AS name_ar, '🌅' AS icon UNION ALL
          SELECT 'Food',           'Lunch',                          'غداء',                    '🍽'  UNION ALL
          SELECT 'Food',           'Dinner',                         'عشاء',                    '🌙' UNION ALL
          SELECT 'Food',           'Snacks',                         'سناكس',                   '🍿' UNION ALL
          SELECT 'Food',           'Coffee',                         'قهوة',                    '☕' UNION ALL
          SELECT 'Transport',      'Taxi',                           'تاكسي',                   '🚕' UNION ALL
          SELECT 'Transport',      'Fuel',                           'بنزين',                   '⛽' UNION ALL
          SELECT 'Transport',      'Public transport',               'مواصلات عامة',           '🚌' UNION ALL
          SELECT 'Bills',          'Rent',                           'إيجار',                   '🏠' UNION ALL
          SELECT 'Bills',          'Internet',                       'إنترنت',                  '📶' UNION ALL
          SELECT 'Bills',          'Electricity',                    'كهرباء',                  '⚡' UNION ALL
          SELECT 'Bills',          'Phone',                          'موبايل',                  '📱' UNION ALL
          SELECT 'Shopping',       'Groceries',                      'بقالة',                   '🛒' UNION ALL
          SELECT 'Shopping',       'Clothes',                        'ملابس',                   '👕'
        ) AS sub ON p.name_en = sub.parent AND p.parent_id IS NULL
        WHERE NOT EXISTS (
          SELECT 1 FROM categories c
          WHERE c.parent_id = p.id AND c.name_en = sub.name_en
        )
    """),
]


async def init_db() -> None:
    import os
    db_dir = os.path.dirname(config.DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    async with aiosqlite.connect(config.DB_PATH) as db:
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
    logger.info("Database initialized at %s", config.DB_PATH)


async def seed_allowed_users() -> None:
    """Seed allowed_users from ALLOWED_USERS env on first run, then load into memory."""
    from src import state

    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute("SELECT user_id FROM allowed_users") as cur:
            rows = await cur.fetchall()

        if not rows and config.ALLOWED_USERS:
            for uid in config.ALLOWED_USERS:
                await db.execute(
                    "INSERT OR IGNORE INTO allowed_users (user_id) VALUES (?)", (uid,)
                )
                await db.execute(
                    """
                    INSERT OR IGNORE INTO users (user_id, language, timezone)
                    VALUES (?, ?, ?)
                    """,
                    (uid, config.DEFAULT_LANGUAGE, config.TIMEZONE),
                )
            await db.commit()
            rows = [(uid,) for uid in config.ALLOWED_USERS]

        state.allowed_users = {r[0] for r in rows}

    logger.info("Allowed users loaded: %d", len(state.allowed_users))
