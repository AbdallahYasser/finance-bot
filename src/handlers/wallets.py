"""/wallets and /addwallet handlers."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.auth import require_allowed_user
from src.db import wallets as wallets_db
from src.utils.currency import parse_amount, format_amount_cents
from src.utils.keyboards import wallet_types_kb

router = Router()


class AddWalletStates(StatesGroup):
    name = State()
    type = State()
    initial_balance = State()


_TYPE_ICON = {'cash': '💵', 'bank': '🏦', 'e_wallet': '📱', 'asset_gold': '🥇'}


@router.message(Command("wallets"))
@require_allowed_user
async def cmd_wallets(message: Message) -> None:
    ws = await wallets_db.list_active()
    if not ws:
        await message.answer("No wallets yet. Use /addwallet to create one.")
        return
    lines = ["<b>Your wallets:</b>", ""]
    for w in ws:
        bal = await wallets_db.get_balance_cents(w['id'])
        icon = _TYPE_ICON.get(w['type'], '•')
        name = w.get('name_en') or w.get('name_ar') or f"Wallet {w['id']}"
        lines.append(f"{icon} {name}: {format_amount_cents(bal)}")
    lines.append("")
    lines.append("/addwallet to add another")
    await message.answer("\n".join(lines))


@router.message(Command("addwallet"))
@require_allowed_user
async def cmd_addwallet(message: Message, state: FSMContext) -> None:
    await state.set_state(AddWalletStates.name)
    await message.answer(
        "New wallet — what should I call it? (e.g. <code>Cash</code>, <code>Bank (NBE)</code>)"
    )


@router.message(AddWalletStates.name)
@require_allowed_user
async def addwallet_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 60:
        await message.answer("Send a name between 1 and 60 characters.")
        return
    await state.update_data(name=name)
    await state.set_state(AddWalletStates.type)
    await message.answer("What type of wallet?", reply_markup=wallet_types_kb("addwallet_type"))


@router.callback_query(AddWalletStates.type, F.data.startswith("addwallet_type:"))
@require_allowed_user
async def addwallet_type_cb(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val not in wallets_db.WALLET_TYPES:
        return
    await state.update_data(type=val)
    await state.set_state(AddWalletStates.initial_balance)
    await callback.message.answer(
        "What's the current balance? (e.g. <code>12500</code> or <code>12500.50</code>). "
        "Send <code>0</code> if empty."
    )


@router.message(AddWalletStates.initial_balance)
@require_allowed_user
async def addwallet_balance(message: Message, state: FSMContext) -> None:
    try:
        cents = parse_amount(message.text or "")
    except ValueError:
        await message.answer("Couldn't parse that. Try <code>12500</code> or <code>12500.50</code>.")
        return
    data = await state.get_data()
    await wallets_db.create(
        name_en=data["name"],
        name_ar=None,
        type=data["type"],
        initial_balance_cents=cents,
    )
    await state.clear()
    icon = _TYPE_ICON.get(data["type"], "•")
    await message.answer(
        f"✅ Wallet created: {icon} <b>{data['name']}</b> with {format_amount_cents(cents)}."
    )
