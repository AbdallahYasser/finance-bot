"""Shared pytest fixtures.

`tmp_db_path` allocates a temp DB file but does NOT initialise schema.
`seeded_db` runs `init_db()` + `seed_allowed_users()` against the temp DB so
schema and default categories are present — use this for any test that
touches wallets/categories/transactions.
"""
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture
def tmp_db_path(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ALLOWED_USERS", "5904148250")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    return db_path


@pytest_asyncio.fixture
async def seeded_db(monkeypatch):
    """Temp DB with schema + default categories applied.

    Modules access `src.config.DB_PATH` lazily, so monkeypatching it on the
    config module is enough — no import reloads needed.
    """
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")

    from src import config
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(config, "ALLOWED_USERS", {5904148250})

    from src.db.schema import init_db, seed_allowed_users
    await init_db()
    await seed_allowed_users()
    return db_path
