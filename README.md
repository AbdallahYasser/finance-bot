# finance-bot

Personal-finance Telegram bot — tracks spending, savings, debts, and gold-as-asset for a single user, with bilingual UI (Arabic + English) and SMS-import support via iOS Shortcuts.

## Features (v1 scope)

- Multi-wallet ledger: cash, banks, e-wallets, gold (grams + karat)
- Categories + subcategories, branch-level Places, canonical Items with size/unit
- Per-(item, place) price memory with change alerts and cross-place comparison
- Fixed bills with reminders (mark paid / skipped / late)
- Budgets per category (calendar month)
- Debts: lend / borrow / repay / forgive
- Reconciliation (manual + automatic from bank SMS balance line)
- SMS auto-import from CIB via iOS Shortcut → bot parses, you add details
- Bilingual UI (AR + EN), single user, EGP only

## Tech stack

- Python 3.12, aiogram 3.13 (async Telegram)
- aiosqlite (SQLite with WAL mode)
- APScheduler (recurring reminders)
- rapidfuzz (item search), Babel (i18n), python-dateutil (recurrence)
- Deployed via Coolify on AWS EC2

## Local development

```bash
cp .env.example .env
# Fill in BOT_TOKEN
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

Run tests:
```bash
pytest
```

## Deploy

Auto-deployed to Coolify on push to `main`. See `docs/deploy.md` for setup. Telegram deploy notifications fire pre/post deploy.

## Documentation

- `docs/architecture.md` — components and data flow
- `docs/data-model.md` — full schema with invariants
- `docs/ios-shortcut-setup.md` — how to set up the SMS forwarding shortcut on iPhone
- `docs/cib-sms-format.md` — CIB SMS regex template and edge cases
- `docs/corner-cases.md` — known risks and how each is mitigated
- `docs/deploy.md` — Coolify-specific deploy steps
- `docs/user-guide.md` — end-user how-to (EN + AR)
