"""/places list and /addplace standalone FSM."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src.auth import require_allowed_user
from src.db import places as places_db
from src.utils.keyboards import skip_kb

router = Router()

NOT_COMMAND = F.text & ~F.text.startswith("/")


class AddPlaceStates(StatesGroup):
    branch = State()
    chain = State()


@router.message(Command("places"))
@require_allowed_user
async def cmd_places(message: Message) -> None:
    ps = await places_db.list_active()
    if not ps:
        await message.answer("No places yet. Use /addplace or pick during /spend.")
        return
    lines = ["<b>Your places:</b>", ""]
    for p in ps[:20]:
        lines.append(f"📍 {places_db.label(p)}")
    if len(ps) > 20:
        lines.append(f"\n…and {len(ps) - 20} more.")
    lines.append("")
    lines.append("/addplace to add another")
    await message.answer("\n".join(lines))


@router.message(Command("addplace"))
@require_allowed_user
async def cmd_addplace(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(AddPlaceStates.branch)
    await message.answer(
        "New place — branch name? (e.g. <code>7-Eleven Maadi</code>)"
    )


@router.message(AddPlaceStates.branch, NOT_COMMAND)
@require_allowed_user
async def addplace_branch(message: Message, state: FSMContext) -> None:
    branch = (message.text or "").strip()
    if not branch or len(branch) > 80:
        await message.answer("Send a branch name (1-80 characters).")
        return
    await state.update_data(branch=branch)
    await state.set_state(AddPlaceStates.chain)
    await message.answer(
        "Chain name? (optional — e.g. <code>7-Eleven</code>)",
        reply_markup=skip_kb("addplace_chain"),
    )


@router.callback_query(AddPlaceStates.chain, F.data.startswith("addplace_chain:"))
@require_allowed_user
async def addplace_chain_skip(callback: CallbackQuery, state: FSMContext) -> None:
    val = callback.data.split(":", 1)[1]
    await callback.answer()
    if val == "cancel":
        await state.clear()
        await callback.message.answer("Cancelled.")
        return
    if val == "skip":
        await _save_place(callback.message, state, chain=None)


@router.message(AddPlaceStates.chain, NOT_COMMAND)
@require_allowed_user
async def addplace_chain_text(message: Message, state: FSMContext) -> None:
    chain = (message.text or "").strip()
    if len(chain) > 80:
        await message.answer("Chain name too long (max 80 characters).")
        return
    await _save_place(message, state, chain=chain or None)


async def _save_place(message, state: FSMContext, chain) -> None:
    data = await state.get_data()
    branch = data["branch"]
    await state.clear()
    try:
        place_id = await places_db.create(branch_name=branch, chain_name=chain)
        msg = f"✅ Created place: 📍 <b>{branch}</b>"
        if chain:
            msg += f" (chain: <i>{chain}</i>)"
        await message.answer(msg)
    except Exception:
        existing = await places_db.get_by_branch_chain(branch, chain)
        if existing:
            await message.answer(
                f"That place already exists: 📍 <b>{places_db.label(existing)}</b>"
            )
        else:
            await message.answer("Couldn't create place. Try again.")
