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
from src.db import places as places_db
from src.db import items as items_db
from src.db import item_prices as item_prices_db
from src.utils.currency import parse_amount, format_amount_cents
from src.utils.dates import days_ago_utc_iso, parse_user_date, format_date_relative
from src.utils.fuzzy import rank as fuzzy_rank
from src.utils.keyboards import (
    wallets_kb, categories_kb, skip_kb,
    subcategories_kb, places_kb, items_kb, search_results_kb,
)

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


def _item_place_suffix(t: dict) -> str:
    """Build ' · Water 500ml @ 7-Eleven Maadi' if either is set, else ''."""
    parts = []
    if t.get("item_name"):
        name = t["item_name"]
        if t.get("item_size"):
            name = f"{name} ({t['item_size']})"
        parts.append(name)
    if t.get("place_branch"):
        parts.append(f"@ {t['place_branch']}")
    if not parts:
        return ""
    return " · " + " ".join(parts)


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
    extras = _item_place_suffix(t)

    if t["type"] == "spend":
        src_name = t.get("source_name") or t.get("source_name_ar") or "?"
        bal = await wallets_db.get_balance_cents(t["source_wallet_id"])
        text = (
            f"✅ Logged {amt} from <b>{src_name}</b> → {cat_label}{extras} "
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
    subcategory = State()
    place = State()
    place_new_branch = State()
    place_new_chain = State()
    item = State()
    item_new_size = State()
    item_new_unit = State()
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

    parent_id = int(val)
    # Track the parent so subcategory step / save can fall back to it.
    await state.update_data(parent_category_id=parent_id, category_id=parent_id)

    children = await categories_db.list_children(parent_id)
    if children:
        await state.set_state(SpendStates.subcategory)
        await callback.message.answer(
            "Subcategory?",
            reply_markup=subcategories_kb(children, "spend_sc", parent_id),
        )
        return

    await _ask_place_step(callback.message, state)


@router.callback_query(SpendStates.subcategory, F.data.startswith("spend_sc:"))
@require_allowed_user
async def spend_subcategory(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    val = parts[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "none":
        # Skip subcategory: keep parent category_id (already set).
        pass
    else:
        await state.update_data(category_id=int(val))
    await _ask_place_step(callback.message, state)


# ---------- Place step ----------

async def _ask_place_step(message: Message, state: FSMContext) -> None:
    await state.set_state(SpendStates.place)
    recent = await places_db.recent(limit=5)
    text = (
        "Where? Pick from recent, type to search, or create new.\n"
        "Tap <b>Skip & save now</b> to skip place/item/note."
    )
    await message.answer(text, reply_markup=places_kb(recent, "spend_p"))


@router.callback_query(SpendStates.place, F.data.startswith("spend_p:"))
@require_allowed_user
async def spend_place_pick(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip_save":
        # Quick-save with no place/item/note
        await _save_spend(callback.message, state, note=None)
        return
    if val == "skip":
        # No place — continue to item step (e.g. phone bill, gift)
        await state.update_data(place_id=None)
        await _ask_item_step(callback.message, state, place_id=None)
        return
    if val == "new":
        await state.set_state(SpendStates.place_new_branch)
        await callback.message.answer(
            "New place — branch name? (e.g. <code>7-Eleven Maadi</code>)"
        )
        return
    if val == "create_place":
        # Created from search results — use the typed query as branch name
        data = await state.get_data()
        query = (data.get("place_query") or "").strip()
        if not query:
            await callback.message.answer("Lost the search query — type the branch name.")
            await state.set_state(SpendStates.place_new_branch)
            return
        await state.update_data(place_new_branch=query)
        await state.set_state(SpendStates.place_new_chain)
        await callback.message.answer(
            f"Got <b>{html.escape(query)}</b>. Chain name? (optional)",
            reply_markup=skip_kb("spend_pchain"),
        )
        return

    # Existing place picked
    try:
        await state.update_data(place_id=int(val))
    except ValueError:
        return
    await _ask_item_step(callback.message, state, place_id=int(val))


@router.message(SpendStates.place, NOT_COMMAND)
@require_allowed_user
async def spend_place_search(message: Message, state: FSMContext) -> None:
    """Free-text in place state = fuzzy search; reshow keyboard with matches."""
    query = (message.text or "").strip()
    if not query:
        return
    await state.update_data(place_query=query)
    all_places = await places_db.list_active()
    choices = []
    for p in all_places:
        label = places_db.label(p)
        choices.append((label, p["id"]))
    matches = fuzzy_rank(query, choices, limit=8, cutoff=50)
    await message.answer(
        f"Matches for <b>{html.escape(query)}</b>:",
        reply_markup=search_results_kb(
            matches, prefix="spend_p", create_query=query, create_callback="create_place"
        ),
    )


@router.message(SpendStates.place_new_branch, NOT_COMMAND)
@require_allowed_user
async def spend_place_new_branch(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if not branch or len(branch) > 80:
        await message.answer("Send a branch name (1-80 characters).")
        return
    await state.update_data(place_new_branch=branch)
    await state.set_state(SpendStates.place_new_chain)
    await message.answer(
        "Chain name? (optional — e.g. <code>7-Eleven</code>)",
        reply_markup=skip_kb("spend_pchain"),
    )


async def _create_place_and_continue(
    message: Message, state: FSMContext, chain: Optional[str]
) -> None:
    data = await state.get_data()
    branch = data["place_new_branch"]
    try:
        place_id = await places_db.create(branch_name=branch, chain_name=chain)
    except Exception:
        # Most likely UNIQUE(branch_name, chain_name) conflict — fetch existing
        existing = await places_db.get_by_branch_chain(branch, chain)
        place_id = existing["id"] if existing else 0
        if not place_id:
            await message.answer("Couldn't create place. Try again.")
            return
    await state.update_data(place_id=place_id)
    await _ask_item_step(message, state, place_id=place_id)


@router.callback_query(SpendStates.place_new_chain, F.data.startswith("spend_pchain:"))
@require_allowed_user
async def spend_place_new_chain_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _create_place_and_continue(callback.message, state, chain=None)


@router.message(SpendStates.place_new_chain, NOT_COMMAND)
@require_allowed_user
async def spend_place_new_chain_text(message: Message, state: FSMContext) -> None:
    chain = (message.text or "").strip()
    if len(chain) > 80:
        await message.answer("Chain name too long (max 80 characters).")
        return
    await _create_place_and_continue(message, state, chain=chain or None)


# ---------- Item step ----------

async def _ask_item_step(
    message: Message, state: FSMContext, place_id: Optional[int]
) -> None:
    await state.set_state(SpendStates.item)
    if place_id:
        recent = await items_db.recent_at_place(place_id, limit=5)
        if not recent:
            recent = await items_db.recent(limit=5)
    else:
        recent = await items_db.recent(limit=5)
    text = (
        "What item? Pick recent, type to search, or create new.\n"
        "Tap <b>Skip item</b> to continue without one, "
        "or <b>Save now</b> to skip everything."
    )
    await message.answer(text, reply_markup=items_kb(recent, "spend_i"))


@router.callback_query(SpendStates.item, F.data.startswith("spend_i:"))
@require_allowed_user
async def spend_item_pick(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip_save":
        await _save_spend(callback.message, state, note=None)
        return
    if val == "skip":
        # No item — continue to the note step
        await state.update_data(item_id=None)
        await _ask_note_step(callback.message, state)
        return
    if val == "new":
        # Ask for the name as a fresh text prompt
        await state.update_data(item_new_name=None)
        await callback.message.answer(
            "New item — name? (e.g. <code>Water bottle</code>)"
        )
        # Re-use the search state to receive the name as a free-text reply
        await state.set_state(SpendStates.item)
        await state.update_data(awaiting_item_name=True)
        return
    if val == "create_item":
        data = await state.get_data()
        query = (data.get("item_query") or "").strip()
        if not query:
            await callback.message.answer("Lost the search query — type the item name.")
            await state.update_data(awaiting_item_name=True)
            return
        await state.update_data(item_new_name=query, awaiting_item_name=False)
        await state.set_state(SpendStates.item_new_size)
        await callback.message.answer(
            f"Got <b>{html.escape(query)}</b>. Size? (e.g. <code>500ml</code>)",
            reply_markup=skip_kb("spend_isize"),
        )
        return

    # Existing item picked
    try:
        await state.update_data(item_id=int(val))
    except ValueError:
        return
    await _ask_note_step(callback.message, state)


@router.message(SpendStates.item, NOT_COMMAND)
@require_allowed_user
async def spend_item_search_or_name(message: Message, state: FSMContext) -> None:
    """In item state, free text either:
    - if awaiting_item_name=True → treat as the new-item name → go to size step
    - else → fuzzy search and reshow keyboard
    """
    text = (message.text or "").strip()
    if not text:
        return

    data = await state.get_data()
    if data.get("awaiting_item_name"):
        await state.update_data(item_new_name=text, awaiting_item_name=False)
        await state.set_state(SpendStates.item_new_size)
        await message.answer(
            f"Got <b>{html.escape(text)}</b>. Size? (e.g. <code>500ml</code>)",
            reply_markup=skip_kb("spend_isize"),
        )
        return

    await state.update_data(item_query=text)
    choices = await items_db.all_search_choices()
    matches = fuzzy_rank(text, choices, limit=8, cutoff=50)
    await message.answer(
        f"Matches for <b>{html.escape(text)}</b>:",
        reply_markup=search_results_kb(
            matches, prefix="spend_i", create_query=text, create_callback="create_item"
        ),
    )


@router.callback_query(SpendStates.item_new_size, F.data.startswith("spend_isize:"))
@require_allowed_user
async def spend_item_size_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await state.update_data(item_new_size=None)
        await state.set_state(SpendStates.item_new_unit)
        await callback.message.answer(
            "Unit? (e.g. <code>bottle</code>, <code>piece</code>)",
            reply_markup=skip_kb("spend_iunit"),
        )


@router.message(SpendStates.item_new_size, NOT_COMMAND)
@require_allowed_user
async def spend_item_size_text(message: Message, state: FSMContext) -> None:
    size = (message.text or "").strip()
    if len(size) > 30:
        await message.answer("Size too long (max 30 chars).")
        return
    await state.update_data(item_new_size=size or None)
    await state.set_state(SpendStates.item_new_unit)
    await message.answer(
        "Unit? (e.g. <code>bottle</code>)",
        reply_markup=skip_kb("spend_iunit"),
    )


@router.callback_query(SpendStates.item_new_unit, F.data.startswith("spend_iunit:"))
@require_allowed_user
async def spend_item_unit_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _create_item_and_continue(callback.message, state, unit=None)


@router.message(SpendStates.item_new_unit, NOT_COMMAND)
@require_allowed_user
async def spend_item_unit_text(message: Message, state: FSMContext) -> None:
    unit = (message.text or "").strip()
    if len(unit) > 30:
        await message.answer("Unit too long (max 30 chars).")
        return
    await _create_item_and_continue(message, state, unit=unit or None)


async def _create_item_and_continue(
    message: Message, state: FSMContext, unit: Optional[str]
) -> None:
    data = await state.get_data()
    name = data.get("item_new_name", "").strip()
    size = data.get("item_new_size")
    default_cat = data.get("category_id") or data.get("parent_category_id")
    item_id = await items_db.create(
        canonical_name_en=name,
        size=size,
        unit=unit,
        default_category_id=default_cat,
    )
    await state.update_data(item_id=item_id)
    await _ask_note_step(message, state)


# ---------- Note step (final) ----------

async def _ask_note_step(message: Message, state: FSMContext) -> None:
    await state.set_state(SpendStates.note)
    await message.answer(
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
        item_id=data.get("item_id"),
        place_id=data.get("place_id"),
    )
    if data.get("item_id") and data.get("place_id"):
        await item_prices_db.insert(
            item_id=data["item_id"],
            place_id=data["place_id"],
            price_cents=data["amount"],
            transaction_id=tx_id,
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
