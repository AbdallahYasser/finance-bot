"""
Authorization gate for the bot.

Single-user bot: only IDs in ALLOWED_USERS can interact. Everyone else
is silently ignored (no error message, no DB read or write).
"""
import logging
from functools import wraps
from typing import Callable

from aiogram.types import Message, CallbackQuery

from src import state

logger = logging.getLogger(__name__)


def is_allowed(user_id: int) -> bool:
    return user_id in state.allowed_users


def require_allowed_user(handler: Callable) -> Callable:
    """Decorator for aiogram handlers — silently drops events from non-allowed users."""

    @wraps(handler)
    async def wrapper(event, *args, **kwargs):
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user is None or not is_allowed(user.id):
            logger.info("Dropped event from unauthorized user %s", user.id if user else "?")
            return None

        return await handler(event, *args, **kwargs)

    return wrapper
