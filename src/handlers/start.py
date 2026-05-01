"""
M0: minimal /start handler. Confirms the bot is alive and the auth gate works.
Real first-run wizard lands in M1.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.auth import require_allowed_user

router = Router()


@router.message(Command("start"))
@require_allowed_user
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 <b>finance-bot is alive.</b>\n\n"
        "M0 deployed. Wallets, transactions, SMS-import, and reports land in upcoming milestones.\n\n"
        "Run /ping to verify the bot is responding."
    )


@router.message(Command("ping"))
@require_allowed_user
async def cmd_ping(message: Message) -> None:
    await message.answer("pong 🏓")
