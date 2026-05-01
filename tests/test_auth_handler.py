"""M0 sanity test: the auth gate drops events from non-allowed users."""
import pytest

from src import state
from src.auth import is_allowed


def test_allowed_user_passes():
    state.allowed_users = {5904148250}
    assert is_allowed(5904148250) is True


def test_unknown_user_blocked():
    state.allowed_users = {5904148250}
    assert is_allowed(999) is False


def test_empty_allowlist_blocks_everyone():
    state.allowed_users = set()
    assert is_allowed(5904148250) is False
