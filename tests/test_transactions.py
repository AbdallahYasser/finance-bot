"""Transaction insert validation and constraint enforcement."""
import aiosqlite
import pytest

from src import config
from src.db import wallets as wallets_db
from src.db import transactions as tx_db


@pytest.mark.asyncio
async def test_spend_requires_source(seeded_db):
    with pytest.raises(ValueError):
        await tx_db.insert_spend(
            amount_cents=100, source_wallet_id=0, category_id=None
        )


@pytest.mark.asyncio
async def test_income_requires_dest(seeded_db):
    with pytest.raises(ValueError):
        await tx_db.insert_income(
            amount_cents=100, dest_wallet_id=0, category_id=None
        )


@pytest.mark.asyncio
async def test_transfer_rejects_same_wallets(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 0)
    with pytest.raises(ValueError):
        await tx_db.insert_transfer(
            amount_cents=100, source_wallet_id=wid, dest_wallet_id=wid
        )


@pytest.mark.asyncio
async def test_zero_amount_rejected_by_app(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 0)
    with pytest.raises(ValueError):
        await tx_db.insert_spend(amount_cents=0, source_wallet_id=wid, category_id=None)


@pytest.mark.asyncio
async def test_negative_amount_check_constraint(seeded_db):
    """The amount_cents>0 CHECK enforced at DB level even if app guard slips."""
    wid = await wallets_db.create("Cash", None, "cash", 0)
    async with aiosqlite.connect(config.DB_PATH) as db:
        with pytest.raises(aiosqlite.IntegrityError):
            await db.execute(
                """
                INSERT INTO transactions
                  (type, amount_cents, source_wallet_id, occurred_at, source)
                VALUES ('spend', -1, ?, datetime('now'), 'manual')
                """,
                (wid,),
            )
            await db.commit()


@pytest.mark.asyncio
async def test_refund_links_to_original(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 100000)
    spend_id = await tx_db.insert_spend(
        amount_cents=50000, source_wallet_id=wid, category_id=None
    )
    refund_id = await tx_db.insert_refund(
        amount_cents=50000,
        dest_wallet_id=wid,
        refund_of_id=spend_id,
    )
    assert refund_id > spend_id
    # Net wallet balance: -50000 (spend) + 50000 (refund) = 0 → back to initial
    assert await wallets_db.get_balance_cents(wid) == 100000


@pytest.mark.asyncio
async def test_update_occurred_at(seeded_db):
    from src.utils.dates import days_ago_utc_iso
    wid = await wallets_db.create("Cash", None, "cash", 0)
    tx_id = await tx_db.insert_spend(
        amount_cents=100, source_wallet_id=wid, category_id=None
    )
    new_iso = days_ago_utc_iso(2)
    ok = await tx_db.update_occurred_at(tx_id, new_iso)
    assert ok is True

    row = await tx_db.get(tx_id)
    assert row['occurred_at'] == new_iso


@pytest.mark.asyncio
async def test_update_occurred_at_missing_returns_false(seeded_db):
    ok = await tx_db.update_occurred_at(99999, "2020-01-01T12:00:00Z")
    assert ok is False


@pytest.mark.asyncio
async def test_get_returns_joined_fields(seeded_db):
    from src.db import categories as cats_db
    wid = await wallets_db.create("Cash", None, "cash", 0)
    food = await cats_db.get_by_name("Food", "expense")
    tx_id = await tx_db.insert_spend(
        amount_cents=200, source_wallet_id=wid, category_id=food['id'], note="lunch"
    )
    row = await tx_db.get(tx_id)
    assert row['category_name'] == "Food"
    assert row['source_name'] == "Cash"
    assert row['note'] == "lunch"


@pytest.mark.asyncio
async def test_recent_returns_newest_first(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 0)
    a = await tx_db.insert_spend(amount_cents=100, source_wallet_id=wid, category_id=None)
    b = await tx_db.insert_spend(amount_cents=200, source_wallet_id=wid, category_id=None)
    c = await tx_db.insert_spend(amount_cents=300, source_wallet_id=wid, category_id=None)
    rows = await tx_db.recent(2)
    assert len(rows) == 2
    assert rows[0]['id'] == c
    assert rows[1]['id'] == b
