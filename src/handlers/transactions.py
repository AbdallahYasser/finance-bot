"""/spend, /income, /transfer FSM flows + post-save date editing."""
import html
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.auth import require_allowed_user
from src.db import wallets as wallets_db
from src.db import categories as categories_db
from src.db import transactions as tx_db
from src.utils.currency import parse_amount, format_amount_cents
from src.utils.dates import days_ago_utc_iso, parse_user_date, format_date_relative
from src.utils.keyboards import wallets_kb, categories_kb, skip_kb

logger = logging.getLogger(__name__)

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")


# ---------- Confirmation rendering + edit-date keyboard ----------

def _editdate_kb(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📅 Change date", callback_data=f"editdate_open:{tx_id}"),
    ]])


def _editdate_picker_kb(tx_id: int) -> InlineKeyboardMarkup:
    rows = []
    for a, b in [(0, 1), (2, 3), (4, 5), (6, 7)]:
        labels = {
            0: "📅 Today", 1: "⬅️ Yesterday",
            2: "2 days ago", 3: "3 days ago",
            4: "4 days ago", 5: "5 days ago",
            6: "6 days ago", 7: "7 days ago",
        }
        rows.append([
            InlineKeyboardButton(text=labels[a], callback_data=f"editdate_pick:{tx_id}:{a}"),
            InlineKeyboardButton(text=labels[b], callback_data=f"editdate_pick:{tx_id}:{b}"),
        ])
    rows.append([
        InlineKeyboardButton(text="✏️ Type a date", callback_data=f"editdate_custom:{tx_id}"),
    ])
    rows.append([
        InlineKeyboardButton(text="✖ Close", callback_data=f"editdate_close:{tx_id}"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _render_tx_confirmation(tx_id: int) -> str:
    """Build the confirmation text for a saved transaction (re-fetched fresh)."""
    t = await tx_db.get(tx_id)
    if not t:
        return "(transaction not found)"

    date_str = format_date_relative(t["occurred_at"])
    amt = format_amount_cents(t["amount_cents"])

    cat_icon = t.get("category_icon") or ""
    cat_name = t.get("category_name") or t.get("category_name_ar") or ""
    cat_label = (cat_icon + " " + cat_name).strip() or "—"

    if t["type"] == "spend":
        src_name = t.get("source_name") or t.get("source_name_ar") or "?"
        bal = await wallets_db.get_balance_cents(t["source_wallet_id"])
        text = (
            f"✅ Logged {amt} from <b>{src_name}</b> → {cat_label} "
            f"<i>({date_str})</i>.\nBalance: {format_amount_cents(bal)}"
        )
    elif t["type"] == "income":
        dst_name = t.get("dest_name") or t.get("dest_name_ar") or "?"
        bal = await wallets_db.get_balance_cents(t["dest_wallet_id"])
        text = (
            f"✅ Logged {amt} income to <b>{dst_name}</b> · {cat_label} "
            f"<i>({date_str})</i>.\nBalance: {format_amount_cents(bal)}"
        )
    elif t["type"] == "transfer":
        src_name = t.get("source_name") or t.get("source_name_ar") or "?"
        dst_name = t.get("dest_name") or t.get("dest_name_ar") or "?"
        src_bal = await wallets_db.get_balance_cents(t["source_wallet_id"])
        dst_bal = await wallets_db.get_balance_cents(t["dest_wallet_id"])
        text = (
            f"✅ Transferred {amt} <i>({date_str})</i>.\n"
            f"<b>{src_name}</b>: {format_amount_cents(src_bal)}\n"
            f"<b>{dst_name}</b>: {format_amount_cents(dst_bal)}"
        )
    else:
        text = f"✅ {amt} <i>({date_str})</i>"

    if t.get("note"):
        text += f"\nNote: {html.escape(t['note'])}"
    return text


class EditDateStates(StatesGroup):
    custom = State()


@router.callback_query(F.data.startswith("editdate_open:"))
@require_allowed_user
async def editdate_open(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=_editdate_picker_kb(tx_id))


@router.callback_query(F.data.startswith("editdate_close:"))
@require_allowed_user
async def editdate_close(callback: CallbackQuery) -> None:
    tx_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=_editdate_kb(tx_id))


@router.callback_query(F.data.startswith("editdate_pick:"))
@require_allowed_user
async def editdate_pick(callback: CallbackQuery) -> None:
    parts = callback.data.split(":")
    tx_id = int(parts[1])
    days_ago = int(parts[2])
    new_iso = days_ago_utc_iso(days_ago)
    ok = await tx_db.update_occurred_at(tx_id, new_iso)
    await callback.answer("Date updated" if ok else "Transaction not found")
    text = await _render_tx_confirmation(tx_id)
    await callback.message.edit_text(text, reply_markup=_editdate_kb(tx_id))


@router.callback_query(F.data.startswith("editdate_custom:"))
@require_allowed_user
async def editdate_custom_open(callback: CallbackQuery, state: FSMContext) -> None:
    tx_id = int(callback.data.split(":")[1])
    await callback.answer()
    await state.clear()
    await state.set_state(EditDateStates.custom)
    await state.update_data(tx_id=tx_id)
    await callback.message.answer(
        "Type the date — examples:\n"
        "• <code>2026-05-01</code>\n"
        "• <code>1/5/2026</code>\n"
        "• <code>1/5</code> (this year)\n"
        "• <code>yesterday</code>\n"
        "Or send /cancel."
    )


@router.message(EditDateStates.custom, NOT_COMMAND)
@require_allowed_user
async def editdate_custom_text(message: Message, state: FSMContext) -> None:
    raw = message.text or ""
    try:
        new_iso = parse_user_date(raw)
    except ValueError:
        logger.warning("Failed to parse date: %r", raw)
        await message.answer(
            f"Couldn't parse <code>{html.escape(raw)}</code> as a date.\n"
            "Try <code>2026-05-01</code> or <code>1/5/2026</code> (or /cancel)."
        )
        return
    data = await state.get_data()
    tx_id = data.get("tx_id")
    await state.clear()
    if not tx_id:
        await message.answer("Lost track of which transaction to edit. Try again.")
        return
    await tx_db.update_occurred_at(tx_id, new_iso)
    text = await _render_tx_confirmation(tx_id)
    await message.answer(text, reply_markup=_editdate_kb(tx_id))


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
    tx_id = await tx_db.insert_spend(
        amount_cents=data["amount"],
        source_wallet_id=data["wallet_id"],
        category_id=data["category_id"],
        note=note,
    )
    text = await _render_tx_confirmation(tx_id)
    await message.answer(text, reply_markup=_editdate_kb(tx_id))


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
    tx_id = await tx_db.insert_income(
        amount_cents=data["amount"],
        dest_wallet_id=data["wallet_id"],
        category_id=data["category_id"],
        note=note,
    )
    text = await _render_tx_confirmation(tx_id)
    await message.answer(text, reply_markup=_editdate_kb(tx_id))


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
    tx_id = await tx_db.insert_transfer(
        amount_cents=data["amount"],
        source_wallet_id=data["from_wallet_id"],
        dest_wallet_id=data["to_wallet_id"],
        note=note,
    )
    text = await _render_tx_confirmation(tx_id)
    await message.answer(text, reply_markup=_editdate_kb(tx_id))
