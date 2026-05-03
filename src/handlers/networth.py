"""/balance and /networth (alias) — wallet summary + recent transactions."""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.auth import require_allowed_user
from src.db import wallets as wallets_db
from src.db import transactions as tx_db
from src.utils.currency import format_amount_cents
from src.utils.dates import format_date_relative

router = Router()


_TYPE_ICON = {'cash': '💵', 'bank': '🏦', 'e_wallet': '📱', 'asset_gold': '🥇'}


@router.message(Command(commands=["balance", "networth"]))
@require_allowed_user
async def cmd_balance(message: Message) -> None:
    ws = await wallets_db.list_active()
    if not ws:
        await message.answer("No wallets yet. Send /start to set up your first wallet.")
        return

    net = await wallets_db.get_net_worth_cents()
    lines = [f"💰 <b>Net Worth: {format_amount_cents(net)}</b>", "", "<b>Wallets:</b>"]
    for w in ws:
        bal = await wallets_db.get_balance_cents(w['id'])
        icon = _TYPE_ICON.get(w['type'], '•')
        name = w.get('name_en') or w.get('name_ar') or f"Wallet {w['id']}"
        lines.append(f"{icon} {name}: {format_amount_cents(bal)}")

    recent = await tx_db.recent(5)
    if recent:
        lines.append("")
        lines.append("<b>Recent:</b>")
        for t in recent:
            sign = ""
            if t['type'] == 'spend':
                sign = "−"
            elif t['type'] in ('income', 'refund'):
                sign = "+"
            elif t['type'] == 'transfer':
                sign = "↔"
            cat = t.get('category_name') or '—'
            extras = ""
            if t.get('item_name'):
                item_label = t['item_name']
                if t.get('item_size'):
                    item_label = f"{item_label} ({t['item_size']})"
                extras += f" · {item_label}"
            if t.get('place_branch'):
                extras += f" @ {t['place_branch']}"
            note = f" — {t['note']}" if t.get('note') else ""
            date = format_date_relative(t.get('occurred_at') or '')
            lines.append(
                f"  {sign}{format_amount_cents(t['amount_cents'])} · {cat}{extras}{note} "
                f"<i>({date})</i>"
            )

    await message.answer("\n".join(lines))
