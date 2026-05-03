"""Place CRUD + UNIQUE + soft-delete + recent ordering."""
import pytest

from src.db import places as places_db


@pytest.mark.asyncio
async def test_create_and_list(seeded_db):
    pid = await places_db.create("7-Eleven Maadi", "7-Eleven")
    assert pid > 0
    ps = await places_db.list_active()
    assert len(ps) == 1
    assert ps[0]["branch_name"] == "7-Eleven Maadi"


@pytest.mark.asyncio
async def test_unique_branch_chain(seeded_db):
    await places_db.create("7-Eleven Maadi", "7-Eleven")
    with pytest.raises(Exception):
        await places_db.create("7-Eleven Maadi", "7-Eleven")


@pytest.mark.asyncio
async def test_same_branch_different_chain_allowed(seeded_db):
    await places_db.create("Cafe Misr", "Chain A")
    await places_db.create("Cafe Misr", "Chain B")
    ps = await places_db.list_active()
    assert len(ps) == 2


@pytest.mark.asyncio
async def test_no_chain_allowed(seeded_db):
    await places_db.create("ATM CIB Maadi")
    p = await places_db.list_active()
    assert p[0]["chain_name"] is None


@pytest.mark.asyncio
async def test_get_by_branch_chain(seeded_db):
    pid = await places_db.create("7-Eleven Nasr City", "7-Eleven")
    p = await places_db.get_by_branch_chain("7-Eleven Nasr City", "7-Eleven")
    assert p["id"] == pid
    p2 = await places_db.get_by_branch_chain("Nope", "7-Eleven")
    assert p2 is None


@pytest.mark.asyncio
async def test_soft_delete_excludes(seeded_db):
    pid = await places_db.create("X", None)
    await places_db.soft_delete(pid)
    ps = await places_db.list_active()
    assert ps == []
    assert await places_db.get(pid) is None


@pytest.mark.asyncio
async def test_label_with_and_without_chain():
    assert places_db.label({"branch_name": "X Branch", "chain_name": "X"}) == "X Branch · X"
    assert places_db.label({"branch_name": "Solo", "chain_name": None}) == "Solo"
    assert places_db.label({"branch_name": "Same", "chain_name": "Same"}) == "Same"
