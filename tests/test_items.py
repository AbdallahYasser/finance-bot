"""Item CRUD + aliases + recent + label formatting."""
import pytest

from src.db import items as items_db
from src.db import categories as cats_db


@pytest.mark.asyncio
async def test_create_with_size_unit(seeded_db):
    food = await cats_db.get_by_name("Food", "expense")
    iid = await items_db.create(
        canonical_name_en="Water bottle",
        size="500ml",
        unit="bottle",
        default_category_id=food["id"],
    )
    item = await items_db.get(iid)
    assert item["canonical_name_en"] == "Water bottle"
    assert item["size"] == "500ml"
    assert item["unit"] == "bottle"
    assert item["default_category_id"] == food["id"]


@pytest.mark.asyncio
async def test_canonical_creates_alias(seeded_db):
    iid = await items_db.create(canonical_name_en="Pepsi")
    aliases = await items_db.aliases_for(iid)
    assert "Pepsi" in aliases


@pytest.mark.asyncio
async def test_add_alias_idempotent(seeded_db):
    iid = await items_db.create(canonical_name_en="Coca")
    await items_db.add_alias(iid, "Coke")
    await items_db.add_alias(iid, "Coke")  # duplicate
    aliases = await items_db.aliases_for(iid)
    assert sorted(aliases) == ["Coca", "Coke"]


@pytest.mark.asyncio
async def test_requires_at_least_one_canonical(seeded_db):
    with pytest.raises(ValueError):
        await items_db.create()


@pytest.mark.asyncio
async def test_soft_delete_excludes(seeded_db):
    iid = await items_db.create(canonical_name_en="X")
    await items_db.soft_delete(iid)
    assert await items_db.get(iid) is None
    assert await items_db.list_active() == []


@pytest.mark.asyncio
async def test_search_choices_includes_aliases(seeded_db):
    iid = await items_db.create(canonical_name_en="Water 500ml", canonical_name_ar="ماء")
    await items_db.add_alias(iid, "S water")
    choices = await items_db.all_search_choices()
    labels = {c[0] for c in choices}
    assert "Water 500ml" in labels
    assert "ماء" in labels
    assert "S water" in labels


@pytest.mark.asyncio
async def test_label_with_size():
    assert items_db.label({"canonical_name_en": "Coffee", "size": "small"}) == "Coffee (small)"
    assert items_db.label({"canonical_name_en": "Coffee", "size": None}) == "Coffee"
    assert items_db.label({"canonical_name_en": None, "canonical_name_ar": "قهوة", "size": None}) == "قهوة"
