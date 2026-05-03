"""/items list and /additem standalone FSM."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.auth import require_allowed_user
from src.db import items as items_db
from src.db import categories as categories_db
from src.utils.keyboards import skip_kb, categories_kb

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")


class AddItemStates(StatesGroup):
    name = State()
    size = State()
    unit = State()
    category = State()


@router.message(Command("items"))
@require_allowed_user
async def cmd_items(message: Message) -> None:
    its = await items_db.list_active()
    if not its:
        await message.answer("No items yet. Use /additem or pick during /spend.")
        return
    lines = ["<b>Your items:</b>", ""]
    for it in its[:30]:
        lines.append(f"📦 {items_db.label(it)}")
    if len(its) > 30:
        lines.append(f"\n…and {len(its) - 30} more.")
    lines.append("")
    lines.append("/additem to add another")
    await message.answer("\n".join(lines))


@router.message(Command("additem"))
@require_allowed_user
async def cmd_additem(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddItemStates.name)
    await message.answer(
        "New item — name? (e.g. <code>Water bottle</code>)"
    )


@router.message(AddItemStates.name, NOT_COMMAND)
@require_allowed_user
async def additem_name(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if not name or len(name) > 80:
        await message.answer("Send a name (1-80 chars).")
        return
    await state.update_data(name=name)
    await state.set_state(AddItemStates.size)
    await message.answer(
        "Size? (e.g. <code>500ml</code>)",
        reply_markup=skip_kb("additem_size"),
    )


@router.callback_query(AddItemStates.size, F.data.startswith("additem_size:"))
@require_allowed_user
async def additem_size_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await state.update_data(size=None)
        await _ask_unit(callback.message, state)


@router.message(AddItemStates.size, NOT_COMMAND)
@require_allowed_user
async def additem_size_text(message: Message, state: FSMContext) -> None:
    size = (message.text or "").strip()
    if len(size) > 30:
        await message.answer("Too long (max 30 chars).")
        return
    await state.update_data(size=size or None)
    await _ask_unit(message, state)


async def _ask_unit(message, state: FSMContext) -> None:
    await state.set_state(AddItemStates.unit)
    await message.answer(
        "Unit? (e.g. <code>bottle</code>, <code>piece</code>)",
        reply_markup=skip_kb("additem_unit"),
    )


@router.callback_query(AddItemStates.unit, F.data.startswith("additem_unit:"))
@require_allowed_user
async def additem_unit_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await state.update_data(unit=None)
        await _ask_category(callback.message, state)


@router.message(AddItemStates.unit, NOT_COMMAND)
@require_allowed_user
async def additem_unit_text(message: Message, state: FSMContext) -> None:
    unit = (message.text or "").strip()
    if len(unit) > 30:
        await message.answer("Too long (max 30 chars).")
        return
    await state.update_data(unit=unit or None)
    await _ask_category(message, state)


async def _ask_category(message, state: FSMContext) -> None:
    await state.set_state(AddItemStates.category)
    cats = await categories_db.list_top_level("expense")
    await message.answer(
        "Default category for this item?",
        reply_markup=categories_kb(cats, "additem_cat"),
    )


@router.callback_query(AddItemStates.category, F.data.startswith("additem_cat:"))
@require_allowed_user
async def additem_category(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    data = await state.get_data()
    await state.clear()
    item_id = await items_db.create(
        canonical_name_en=data["name"],
        size=data.get("size"),
        unit=data.get("unit"),
        default_category_id=int(val),
    )
    await callback.message.answer(
        f"✅ Created item: 📦 <b>{items_db.label({'canonical_name_en': data['name'], 'size': data.get('size')})}</b>"
    )
