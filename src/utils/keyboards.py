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


def subcategories_kb(children: list[dict], prefix: str, parent_id: int) -> InlineKeyboardMarkup:
    """Subcategory picker. Includes a 'Skip subcategory' option that
    saves with the parent category only."""
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, c in enumerate(children, start=1):
        icon = c.get('icon') or '•'
        name = c.get('name_en') or c.get('name_ar') or 'Sub'
        row.append(InlineKeyboardButton(
            text=f"{icon} {name}",
            callback_data=f"{prefix}:{c['id']}",
        ))
        if i % 3 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⏭ Skip subcategory",
                                      callback_data=f"{prefix}:none:{parent_id}")])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def places_kb(places: list[dict], prefix: str, allow_skip_save: bool = True) -> InlineKeyboardMarkup:
    """Place picker with recents + new + optional 'Skip & save now'."""
    from src.db.places import label as place_label
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, p in enumerate(places, start=1):
        row.append(InlineKeyboardButton(
            text=f"📍 {place_label(p)}",
            callback_data=f"{prefix}:{p['id']}",
        ))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➕ New place", callback_data=f"{prefix}:new")])
    if allow_skip_save:
        rows.append([
            InlineKeyboardButton(text="⏭ Skip & save now",
                                 callback_data=f"{prefix}:skip_save"),
        ])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def items_kb(items: list[dict], prefix: str, allow_skip_save: bool = True) -> InlineKeyboardMarkup:
    """Item picker with recents + new + optional 'Skip & save now'."""
    from src.db.items import label as item_label
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for i, it in enumerate(items, start=1):
        row.append(InlineKeyboardButton(
            text=f"📦 {item_label(it)}",
            callback_data=f"{prefix}:{it['id']}",
        ))
        if i % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="➕ New item", callback_data=f"{prefix}:new")])
    if allow_skip_save:
        rows.append([
            InlineKeyboardButton(text="⏭ Skip & save now",
                                 callback_data=f"{prefix}:skip_save"),
        ])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def search_results_kb(
    matches: list[tuple[str, int, float]],
    prefix: str,
    create_query: str,
    create_callback: str = "create",
) -> InlineKeyboardMarkup:
    """Keyboard built from fuzzy-search matches plus a 'Create '<query>'' row."""
    rows: list[list[InlineKeyboardButton]] = []
    for label, cid, _score in matches[:8]:
        rows.append([InlineKeyboardButton(
            text=f"📍 {label}" if create_callback == "create_place" else f"📦 {label}",
            callback_data=f"{prefix}:{cid}",
        )])
    rows.append([InlineKeyboardButton(
        text=f"➕ Create '{create_query[:40]}'",
        callback_data=f"{prefix}:{create_callback}",
    )])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
