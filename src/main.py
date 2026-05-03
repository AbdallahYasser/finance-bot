"""
finance-bot entrypoint.

M1: init DB, register routers (start, wallets, transactions, networth),
    pass MemoryStorage to Dispatcher for FSM, poll.
"""
import asyncio
import logging

from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from src.config import BOT_TOKEN, LOG_LEVEL
from src.bot_instance import bot
from src.db.schema import init_db, seed_allowed_users
from src.handlers import start as start_handler
from src.handlers import wallets as wallets_handler
from src.handlers import transactions as transactions_handler
from src.handlers import networth as networth_handler
from src.handlers import places as places_handler
from src.handlers import items as items_handler

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

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(start_handler.router)
    dp.include_router(wallets_handler.router)
    dp.include_router(places_handler.router)
    dp.include_router(items_handler.router)
    dp.include_router(transactions_handler.router)
    dp.include_router(networth_handler.router)

    await bot.set_my_commands([
        BotCommand(command="start",     description="Welcome / first-run setup"),
        BotCommand(command="balance",   description="Net worth and recent transactions"),
        BotCommand(command="spend",     description="Log an expense"),
        BotCommand(command="income",    description="Log income"),
        BotCommand(command="transfer",  description="Move money between wallets"),
        BotCommand(command="wallets",   description="List your wallets"),
        BotCommand(command="addwallet", description="Create a new wallet"),
        BotCommand(command="places",    description="List places"),
        BotCommand(command="addplace",  description="Create a new place"),
        BotCommand(command="items",     description="List items"),
        BotCommand(command="additem",   description="Create a new item"),
        BotCommand(command="cancel",    description="Cancel the current flow"),
        BotCommand(command="ping",      description="Check the bot is alive"),
    ])

    logger.info("finance-bot started. Polling...")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    asyncio.run(main())
