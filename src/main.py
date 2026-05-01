"""
finance-bot entrypoint.

M0: minimal — init DB, load allowed users, register /start + /ping handlers, poll.
APScheduler, real handlers, and webhook server land in later milestones.
"""
import asyncio
import logging

from aiogram import Dispatcher
from aiogram.types import BotCommand

from src.config import BOT_TOKEN, LOG_LEVEL
from src.bot_instance import bot
from src.db.schema import init_db, seed_allowed_users
from src.handlers import start as start_handler

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")

    await init_db()
    await seed_allowed_users()

    dp = Dispatcher()
    dp.include_router(start_handler.router)

    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="ping",  description="Check the bot is alive"),
    ])

    logger.info("finance-bot started. Polling...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
