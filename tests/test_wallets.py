"""Wallet CRUD + balance math."""
import pytest

from src.db import wallets as wallets_db
from src.db import transactions as tx_db


@pytest.mark.asyncio
async def test_create_and_count(seeded_db):
    assert await wallets_db.count_active() == 0
    wid = await wallets_db.create("Cash", None, "cash", 0)
    assert wid > 0
    assert await wallets_db.count_active() == 1


@pytest.mark.asyncio
async def test_initial_balance(seeded_db):
    wid = await wallets_db.create("Bank A", None, "bank", 1000000)  # 10000 EGP
    assert await wallets_db.get_balance_cents(wid) == 1000000


@pytest.mark.asyncio
async def test_balance_after_spend(seeded_db):
    wid = await wallets_db.create("Bank A", None, "bank", 1000000)
    await tx_db.insert_spend(amount_cents=25000, source_wallet_id=wid, category_id=None)
    assert await wallets_db.get_balance_cents(wid) == 975000


@pytest.mark.asyncio
async def test_balance_after_income(seeded_db):
    wid = await wallets_db.create("Bank A", None, "bank", 1000000)
    await tx_db.insert_income(amount_cents=500000, dest_wallet_id=wid, category_id=None)
    assert await wallets_db.get_balance_cents(wid) == 1500000


@pytest.mark.asyncio
async def test_transfer_preserves_total(seeded_db):
    a = await wallets_db.create("Bank A", None, "bank", 1000000)
    b = await wallets_db.create("Cash", None, "cash", 0)
    await tx_db.insert_transfer(
        amount_cents=100000, source_wallet_id=a, dest_wallet_id=b
    )
    bal_a = await wallets_db.get_balance_cents(a)
    bal_b = await wallets_db.get_balance_cents(b)
    assert bal_a == 900000
    assert bal_b == 100000
    assert bal_a + bal_b == 1000000


@pytest.mark.asyncio
async def test_net_worth_sums_liquid_wallets(seeded_db):
    await wallets_db.create("Bank A", None, "bank",     1000000)
    await wallets_db.create("Cash",   None, "cash",      300000)
    await wallets_db.create("VCash",  None, "e_wallet",  150000)
    nw = await wallets_db.get_net_worth_cents()
    assert nw == 1450000


@pytest.mark.asyncio
async def test_soft_delete_excludes(seeded_db):
    wid = await wallets_db.create("Old Wallet", None, "cash", 50000)
    await wallets_db.soft_delete(wid)
    assert await wallets_db.count_active() == 0
    assert await wallets_db.get(wid) is None
    assert await wallets_db.get_net_worth_cents() == 0


@pytest.mark.asyncio
async def test_invalid_type_rejected(seeded_db):
    with pytest.raises(ValueError):
        await wallets_db.create("X", None, "crypto", 0)


@pytest.mark.asyncio
async def test_gold_wallet_value(seeded_db):
    """Gold value = grams_milligrams / 1000 * price_per_gram_cents."""
    import aiosqlite
    from src import config

    wid = await wallets_db.create("Gold 21k", None, "asset_gold", 0)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            """
            UPDATE wallets
            SET karat = 21,
                gold_grams_milligrams = 10000,
                gold_price_per_gram_cents = 400000
            WHERE id = ?
            """,
            (wid,),
        )
        await db.commit()
    # 10g × 4000 EGP/g = 40,000 EGP = 4_000_000 cents
    assert await wallets_db.get_net_worth_cents() == 4_000_000
