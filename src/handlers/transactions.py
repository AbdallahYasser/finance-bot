"""/spend, /income, /transfer FSM flows."""
import html
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.auth import require_allowed_user
from src.db import wallets as wallets_db
from src.db import categories as categories_db
from src.db import transactions as tx_db
from src.utils.currency import parse_amount, format_amount_cents
from src.utils.keyboards import wallets_kb, categories_kb, skip_kb

logger = logging.getLogger(__name__)

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")


async def _try_parse_or_reprompt(
    message: Message, example: str = "250"
) -> Optional[int]:
    """Parse message.text as an amount or send a helpful reprompt.

    Returns int cents on success, or None on failure (caller should `return`).
    Echoes the offending text so the user can see exactly what was received,
    and logs at WARNING level for diagnostics.
    """
    raw = message.text or ""
    try:
        cents = parse_amount(raw)
        if cents <= 0:
            raise ValueError("zero")
        return cents
    except ValueError:
        logger.warning("Failed to parse amount: %r", raw)
        safe = html.escape(raw)
        await message.answer(
            f"Couldn't parse <code>{safe}</code> as an amount.\n"
            f"Try <code>{example}</code> or <code>{example}.50</code> "
            f"(or send /cancel to stop)."
        )
        return None


class SpendStates(StatesGroup):
    amount = State()
    wallet = State()
    category = State()
    note = State()


class IncomeStates(StatesGroup):
    amount = State()
    wallet = State()
    category = State()
    note = State()


class TransferStates(StatesGroup):
    amount = State()
    from_wallet = State()
    to_wallet = State()
    note = State()


# ---------- /spend ----------

@router.message(Command("spend"))
@require_allowed_user
async def cmd_spend(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(SpendStates.amount)
    await message.answer("How much did you spend? (e.g. <code>250</code>)")


@router.message(SpendStates.amount, NOT_COMMAND)
@require_allowed_user
async def spend_amount(message: Message, state: FSMContext) -> None:
    cents = await _try_parse_or_reprompt(message, example="250")
    if cents is None:
        return
    await state.update_data(amount=cents)
    ws = await wallets_db.list_active()
    if not ws:
        await state.clear()
        await message.answer("No wallets exist. Run /addwallet first.")
        return
    await state.set_state(SpendStates.wallet)
    await message.answer("From which wallet?", reply_markup=wallets_kb(ws, "spend_w"))


@router.callback_query(SpendStates.wallet, F.data.startswith("spend_w:"))
@require_allowed_user
async def spend_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    await state.update_data(wallet_id=int(val))
    cats = await categories_db.list_by_kind("expense")
    await state.set_state(SpendStates.category)
    await callback.message.answer("What category?", reply_markup=categories_kb(cats, "spend_c"))


@router.callback_query(SpendStates.category, F.data.startswith("spend_c:"))
@require_allowed_user
async def spend_category(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    await state.update_data(category_id=int(val))
    await state.set_state(SpendStates.note)
    await callback.message.answer(
        "Add a note? (optional — type one or tap Skip)",
        reply_markup=skip_kb("spend_n"),
    )


@router.callback_query(SpendStates.note, F.data.startswith("spend_n:"))
@require_allowed_user
async def spend_note_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _save_spend(callback.message, state, note=None)


@router.message(SpendStates.note, NOT_COMMAND)
@require_allowed_user
async def spend_note_text(message: Message, state: FSMContext) -> None:
    note = (message.text or "").strip() or None
    await _save_spend(message, state, note=note)


async def _save_spend(message: Message, state: FSMContext, note: Optional[str]) -> None:
    data = await state.get_data()
    await state.clear()
    await tx_db.insert_spend(
        amount_cents=data["amount"],
        source_wallet_id=data["wallet_id"],
        category_id=data["category_id"],
        note=note,
    )
    w = await wallets_db.get(data["wallet_id"])
    cat = await categories_db.get(data["category_id"])
    bal = await wallets_db.get_balance_cents(data["wallet_id"])
    await message.answer(
        f"✅ Logged {format_amount_cents(data['amount'])} from "
        f"<b>{w['name_en'] or w['name_ar']}</b> → "
        f"{cat['icon'] or ''} {cat['name_en'] or cat['name_ar']}.\n"
        f"Balance: {format_amount_cents(bal)}"
    )


# ---------- /income ----------

@router.message(Command("income"))
@require_allowed_user
async def cmd_income(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(IncomeStates.amount)
    await message.answer("How much income? (e.g. <code>5000</code>)")


@router.message(IncomeStates.amount, NOT_COMMAND)
@require_allowed_user
async def income_amount(message: Message, state: FSMContext) -> None:
    cents = await _try_parse_or_reprompt(message, example="5000")
    if cents is None:
        return
    await state.update_data(amount=cents)
    ws = await wallets_db.list_active()
    if not ws:
        await state.clear()
        await message.answer("No wallets exist. Run /addwallet first.")
        return
    await state.set_state(IncomeStates.wallet)
    await message.answer("Which wallet receives it?", reply_markup=wallets_kb(ws, "inc_w"))


@router.callback_query(IncomeStates.wallet, F.data.startswith("inc_w:"))
@require_allowed_user
async def income_wallet(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    await state.update_data(wallet_id=int(val))
    cats = await categories_db.list_by_kind("income")
    await state.set_state(IncomeStates.category)
    await callback.message.answer("What kind of income?", reply_markup=categories_kb(cats, "inc_c"))


@router.callback_query(IncomeStates.category, F.data.startswith("inc_c:"))
@require_allowed_user
async def income_category(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    await state.update_data(category_id=int(val))
    await state.set_state(IncomeStates.note)
    await callback.message.answer(
        "Add a note? (optional)",
        reply_markup=skip_kb("inc_n"),
    )


@router.callback_query(IncomeStates.note, F.data.startswith("inc_n:"))
@require_allowed_user
async def income_note_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _save_income(callback.message, state, note=None)


@router.message(IncomeStates.note, NOT_COMMAND)
@require_allowed_user
async def income_note_text(message: Message, state: FSMContext) -> None:
    note = (message.text or "").strip() or None
    await _save_income(message, state, note=note)


async def _save_income(message: Message, state: FSMContext, note: Optional[str]) -> None:
    data = await state.get_data()
    await state.clear()
    await tx_db.insert_income(
        amount_cents=data["amount"],
        dest_wallet_id=data["wallet_id"],
        category_id=data["category_id"],
        note=note,
    )
    w = await wallets_db.get(data["wallet_id"])
    cat = await categories_db.get(data["category_id"])
    bal = await wallets_db.get_balance_cents(data["wallet_id"])
    await message.answer(
        f"✅ Logged {format_amount_cents(data['amount'])} income to "
        f"<b>{w['name_en'] or w['name_ar']}</b> · "
        f"{cat['icon'] or ''} {cat['name_en'] or cat['name_ar']}.\n"
        f"Balance: {format_amount_cents(bal)}"
    )


# ---------- /transfer ----------

@router.message(Command("transfer"))
@require_allowed_user
async def cmd_transfer(message: Message, state: FSMContext) -> None:
    ws = await wallets_db.list_active()
    if len(ws) < 2:
        await message.answer("Need at least 2 wallets to transfer. Run /addwallet first.")
        return
    await state.clear()
    await state.set_state(TransferStates.amount)
    await message.answer("How much to transfer? (e.g. <code>1000</code>)")


@router.message(TransferStates.amount, NOT_COMMAND)
@require_allowed_user
async def transfer_amount(message: Message, state: FSMContext) -> None:
    cents = await _try_parse_or_reprompt(message, example="1000")
    if cents is None:
        return
    await state.update_data(amount=cents)
    ws = await wallets_db.list_active()
    await state.set_state(TransferStates.from_wallet)
    await message.answer("From which wallet?", reply_markup=wallets_kb(ws, "tx_from"))


@router.callback_query(TransferStates.from_wallet, F.data.startswith("tx_from:"))
@require_allowed_user
async def transfer_from(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    await state.update_data(from_wallet_id=int(val))
    ws = [w for w in await wallets_db.list_active() if w["id"] != int(val)]
    if not ws:
        await state.clear()
        await callback.message.answer("No other wallet to transfer to. Run /addwallet first.")
        return
    await state.set_state(TransferStates.to_wallet)
    await callback.message.answer("To which wallet?", reply_markup=wallets_kb(ws, "tx_to"))


@router.callback_query(TransferStates.to_wallet, F.data.startswith("tx_to:"))
@require_allowed_user
async def transfer_to(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    data = await state.get_data()
    if int(val) == data.get("from_wallet_id"):
        await callback.message.answer("Source and destination must differ. Pick another wallet.")
        return
    await state.update_data(to_wallet_id=int(val))
    await state.set_state(TransferStates.note)
    await callback.message.answer(
        "Add a note? (optional)",
        reply_markup=skip_kb("tx_n"),
    )


@router.callback_query(TransferStates.note, F.data.startswith("tx_n:"))
@require_allowed_user
async def transfer_note_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _save_transfer(callback.message, state, note=None)


@router.message(TransferStates.note, NOT_COMMAND)
@require_allowed_user
async def transfer_note_text(message: Message, state: FSMContext) -> None:
    note = (message.text or "").strip() or None
    await _save_transfer(message, state, note=note)


async def _save_transfer(message: Message, state: FSMContext, note: Optional[str]) -> None:
    data = await state.get_data()
    await state.clear()
    await tx_db.insert_transfer(
        amount_cents=data["amount"],
        source_wallet_id=data["from_wallet_id"],
        dest_wallet_id=data["to_wallet_id"],
        note=note,
    )
    src = await wallets_db.get(data["from_wallet_id"])
    dst = await wallets_db.get(data["to_wallet_id"])
    src_bal = await wallets_db.get_balance_cents(data["from_wallet_id"])
    dst_bal = await wallets_db.get_balance_cents(data["to_wallet_id"])
    await message.answer(
        f"✅ Transferred {format_amount_cents(data['amount'])}.\n"
        f"<b>{src['name_en'] or src['name_ar']}</b>: {format_amount_cents(src_bal)}\n"
        f"<b>{dst['name_en'] or dst['name_ar']}</b>: {format_amount_cents(dst_bal)}"
    )
