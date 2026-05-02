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
async def test_recent_returns_newest_first(seeded_db):
    wid = await wallets_db.create("Cash", None, "cash", 0)
    a = await tx_db.insert_spend(amount_cents=100, source_wallet_id=wid, category_id=None)
    b = await tx_db.insert_spend(amount_cents=200, source_wallet_id=wid, category_id=None)
    c = await tx_db.insert_spend(amount_cents=300, source_wallet_id=wid, category_id=None)
    rows = await tx_db.recent(2)
    assert len(rows) == 2
    assert rows[0]['id'] == c
    assert rows[1]['id'] == b
