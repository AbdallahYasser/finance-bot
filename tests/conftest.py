"""Shared pytest fixtures. Uses an in-memory SQLite DB per test."""
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(monkeypatch):
    """Each test gets its own SQLite file under a temp dir."""
    tmpdir = tempfile.mkdtemp()
    db_path = str(Path(tmpdir) / "test.db")
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("ALLOWED_USERS", "5904148250")
    monkeypatch.setenv("BOT_TOKEN", "test-token")
    return db_path
