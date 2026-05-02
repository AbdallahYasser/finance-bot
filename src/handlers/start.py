"""/start (with first-run wizard), /cancel and /ping."""
import html
import logging

import aiosqlite
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from src import config
from src.auth import require_allowed_user
from src.db import wallets as wallets_db
from src.utils.currency import parse_amount, format_amount_cents
from src.utils.keyboards import language_kb, skip_kb

logger = logging.getLogger(__name__)

router = Router()


# Magic filter for "text input that is NOT a slash command".
# Used on every state-bound text-fallback handler so commands always work
# (including escape hatches like /cancel and /start) even mid-flow.
NOT_COMMAND = F.text & ~F.text.startswith("/")


class FirstRunStates(StatesGroup):
    lang = State()
    salary_day = State()
    wallet_balance = State()


_WELCOME_TEXT = (
    "👋 <b>finance-bot</b>\n\n"
    "Commands:\n"
    "• /balance — net worth + recent transactions\n"
    "• /spend — log an expense\n"
    "• /income — log income\n"
    "• /transfer — move money between wallets\n"
    "• /wallets — list your wallets\n"
    "• /addwallet — create a new wallet\n"
    "• /ping — check the bot is alive"
)


@router.message(Command("start"))
@require_allowed_user
async def cmd_start(message: Message, state: FSMContext) -> None:
    # Always clear stale state so /start recovers from a half-finished flow.
    await state.clear()

    if await wallets_db.count_active() == 0:
        await state.set_state(FirstRunStates.lang)
        await message.answer(
            "👋 Welcome to <b>finance-bot</b>!\n\n"
            "I'll help you track money — wallets, spending, debts, item prices, "
            "and CIB SMS auto-import.\n\n"
            "First: which language?",
            reply_markup=language_kb("setup_lang"),
        )
        return
    await message.answer(_WELCOME_TEXT)


@router.message(Command("cancel"))
@require_allowed_user
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    cur = await state.get_state()
    await state.clear()
    if cur:
        await message.answer("✅ Cancelled. Send /start any time.")
    else:
        await message.answer("Nothing to cancel.")


@router.message(Command("ping"))
@require_allowed_user
async def cmd_ping(message: Message) -> None:
    await message.answer("pong 🏓")


# ---------- First-run wizard ----------

@router.callback_query(FirstRunStates.lang, F.data.startswith("setup_lang:"))
@require_allowed_user
async def setup_lang(callback: CallbackQuery, state: FSMContext) -> None:
    lang = callback.data.split(":", 1)[1]
    await callback.answer()
    if lang not in ("en", "ar"):
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET language = ?, updated_at = datetime('now') WHERE user_id = ?",
            (lang, callback.from_user.id),
        )
        await db.commit()
    await state.set_state(FirstRunStates.salary_day)
    await callback.message.answer(
        "Got it. What day of the month do you usually get your salary? "
        "Send a number 1-31, or tap Skip.",
        reply_markup=skip_kb("setup_sd"),
    )


@router.callback_query(FirstRunStates.salary_day, F.data == "setup_sd:skip")
@require_allowed_user
async def setup_salary_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _ask_initial_balance(callback.message, state)


@router.callback_query(FirstRunStates.salary_day, F.data == "setup_sd:cancel")
@require_allowed_user
async def setup_salary_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    await callback.message.answer("Setup cancelled. Send /start again any time.")


@router.message(FirstRunStates.salary_day, NOT_COMMAND)
@require_allowed_user
async def setup_salary_day(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    try:
        day = int(text)
        if not (1 <= day <= 31):
            raise ValueError
    except ValueError:
        await message.answer(
            "Send a number between 1 and 31, or tap Skip.",
            reply_markup=skip_kb("setup_sd"),
        )
        return
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET salary_day = ?, updated_at = datetime('now') WHERE user_id = ?",
            (day, message.from_user.id),
        )
        await db.commit()
    await _ask_initial_balance(message, state)


async def _ask_initial_balance(message: Message, state: FSMContext) -> None:
    await state.set_state(FirstRunStates.wallet_balance)
    await message.answer(
        "Now your <b>Bank (CIB)</b> wallet. What's the current balance? "
        "(e.g. <code>12500</code> or <code>12500.50</code> — send <code>0</code> if empty.)"
    )


@router.message(FirstRunStates.wallet_balance, NOT_COMMAND)
@require_allowed_user
async def setup_balance(message: Message, state: FSMContext) -> None:
    raw = message.text or ""
    try:
        cents = parse_amount(raw)
    except ValueError:
        logger.warning("Wizard: failed to parse balance: %r", raw)
        await message.answer(
            f"Couldn't parse <code>{html.escape(raw)}</code> as an amount.\n"
            "Try <code>12500</code> or <code>12500.50</code> (or /cancel)."
        )
        return
    await wallets_db.create(
        name_en="Bank (CIB)",
        name_ar="بنك (CIB)",
        type="bank",
        initial_balance_cents=cents,
    )
    await state.clear()
    await message.answer(
        f"✅ Setup complete!\n\n"
        f"🏦 <b>Bank (CIB)</b>: {format_amount_cents(cents)}\n\n"
        "Now try:\n"
        "• /spend to log an expense\n"
        "• /balance for your net worth\n"
        "• /addwallet to add another wallet"
    )
