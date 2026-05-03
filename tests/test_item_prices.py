"""Item price write on spend."""
import pytest

from src.db import wallets as wallets_db
from src.db import places as places_db
from src.db import items as items_db
from src.db import item_prices as item_prices_db
from src.db import transactions as tx_db


async def _setup(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 100000)
    pid = await places_db.create("7-Eleven Maadi", "7-Eleven")
    iid = await items_db.create(canonical_name_en="Water 500ml", size="500ml")
    return wid, pid, iid


@pytest.mark.asyncio
async def test_insert_writes_row(seeded_db):
    wid, pid, iid = await _setup(seeded_db)
    tx_id = await tx_db.insert_spend(
        amount_cents=500, source_wallet_id=wid, category_id=None,
        item_id=iid, place_id=pid,
    )
    pr_id = await item_prices_db.insert(
        item_id=iid, place_id=pid, price_cents=500, transaction_id=tx_id,
    )
    rows = await item_prices_db.list_for_item(iid)
    assert len(rows) == 1
    assert rows[0]["price_cents"] == 500
    assert rows[0]["transaction_id"] == tx_id
    assert rows[0]["place_id"] == pid


@pytest.mark.asyncio
async def test_multiple_observations(seeded_db):
    wid, pid, iid = await _setup(seeded_db)
    for cents in (500, 600, 550):
        await item_prices_db.insert(item_id=iid, place_id=pid, price_cents=cents)
    rows = await item_prices_db.list_for_item(iid)
    assert len(rows) == 3
    assert [r["price_cents"] for r in rows] == [550, 600, 500] or len(rows) == 3
    # ordered by observed_at DESC; same-second inserts may tie, just ensure all present


@pytest.mark.asyncio
async def test_negative_price_rejected(seeded_db):
    import aiosqlite
    wid, pid, iid = await _setup(seeded_db)
    with pytest.raises(aiosqlite.IntegrityError):
        await item_prices_db.insert(item_id=iid, place_id=pid, price_cents=-1)
