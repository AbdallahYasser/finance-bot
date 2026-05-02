"""Default categories are seeded on init_db()."""
import pytest

from src.db import categories as cats_db


@pytest.mark.asyncio
async def test_expense_categories_seeded(seeded_db):
    cats = await cats_db.list_by_kind("expense")
    names = {c['name_en'] for c in cats}
    assert {"Food", "Transport", "Bills", "Shopping",
            "Entertainment", "Health", "Gifts", "Other"} <= names


@pytest.mark.asyncio
async def test_income_categories_seeded(seeded_db):
    cats = await cats_db.list_by_kind("income")
    names = {c['name_en'] for c in cats}
    assert {"Salary", "Bonus", "Refund", "Other Income"} <= names


@pytest.mark.asyncio
async def test_categories_have_arabic_names(seeded_db):
    cats = await cats_db.list_by_kind("expense")
    for c in cats:
        assert c['name_ar'], f"category {c['name_en']} missing Arabic name"


@pytest.mark.asyncio
async def test_get_by_name(seeded_db):
    food = await cats_db.get_by_name("Food", "expense")
    assert food is not None
    assert food['name_en'] == "Food"
    assert food['kind'] == "expense"
