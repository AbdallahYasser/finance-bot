"""Inline keyboard builders for FSM flows.

Callback data format: f"{prefix}:{value}" — the value is parsed by the handler.
Reserved values: "cancel" (abort flow), "skip" (skip the current step).
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def wallets_kb(wallets: list[dict], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    type_icons = {'cash': '💵', 'bank': '🏦', 'e_wallet': '📱', 'asset_gold': '🥇'}
    for i, w in enumerate(wallets, start=1):
        icon = type_icons.get(w['type'], '•')
        name = w.get('name_en') or w.get('name_ar') or f"Wallet {w['id']}"
        row.append(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=f"{prefix}:{w['id']}",
        ))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_kb(categories: list[dict], prefix: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, c in enumerate(categories, start=1):
        icon = c.get('icon') or '•'
        name = c.get('name_en') or c.get('name_ar') or 'Category'
        row.append(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=f"{prefix}:{c['id']}",
        ))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def wallet_types_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💵 Cash",     callback_data=f"{prefix}:cash"),
            InlineKeyboardButton(text="🏦 Bank",     callback_data=f"{prefix}:bank"),
        ],
        [
            InlineKeyboardButton(text="📱 E-Wallet", callback_data=f"{prefix}:e_wallet"),
            InlineKeyboardButton(text="🥇 Gold",     callback_data=f"{prefix}:asset_gold"),
        ],
        [InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")],
    ])


def skip_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⏭ Skip",   callback_data=f"{prefix}:skip"),
        InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel"),
    ]])


def language_kb(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇬🇧 English",  callback_data=f"{prefix}:en"),
        InlineKeyboardButton(text="🇪🇬 العربية", callback_data=f"{prefix}:ar"),
    ]])
