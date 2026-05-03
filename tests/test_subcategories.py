"""Hierarchical category helpers."""
import pytest

from src.db import categories as cats_db


@pytest.mark.asyncio
async def test_top_level_excludes_children(seeded_db):
    tops = await cats_db.list_top_level("expense")
    names = {c["name_en"] for c in tops}
    # Should include the 8 default parents
    assert {"Food", "Transport", "Bills", "Shopping",
            "Entertainment", "Health", "Gifts", "Other"} <= names
    # Should NOT include the seeded subcategories
    assert "Breakfast" not in names
    assert "Taxi" not in names
    assert "Rent" not in names


@pytest.mark.asyncio
async def test_food_children_seeded(seeded_db):
    food = await cats_db.get_by_name("Food", "expense")
    kids = await cats_db.list_children(food["id"])
    names = {k["name_en"] for k in kids}
    assert {"Breakfast", "Lunch", "Dinner", "Snacks", "Coffee"} == names


@pytest.mark.asyncio
async def test_transport_children_seeded(seeded_db):
    t = await cats_db.get_by_name("Transport", "expense")
    kids = await cats_db.list_children(t["id"])
    names = {k["name_en"] for k in kids}
    assert {"Taxi", "Fuel", "Public transport"} == names


@pytest.mark.asyncio
async def test_no_children_returns_empty(seeded_db):
    other = await cats_db.get_by_name("Other", "expense")
    kids = await cats_db.list_children(other["id"])
    assert kids == []


@pytest.mark.asyncio
async def test_has_children(seeded_db):
    food = await cats_db.get_by_name("Food", "expense")
    other = await cats_db.get_by_name("Other", "expense")
    assert await cats_db.has_children(food["id"]) is True
    assert await cats_db.has_children(other["id"]) is False
