"""
Module-level Bot instance shared by main.py, scheduler, and handlers.
Kept in its own file to avoid circular imports.
"""
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.config import BOT_TOKEN

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
