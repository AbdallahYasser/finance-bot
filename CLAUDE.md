# CLAUDE.md — finance-bot

Repo conventions and gotchas for future Claude Code sessions on this codebase.

## What this is

Personal-finance Telegram bot. Single user (chat_id 5904148250). EGP only. Bilingual AR + EN. Deployed via Coolify on AWS EC2 (same pipeline as prayer-bot).

## Stack

- aiogram 3.13 (async Telegram, Dispatcher + Routers)
- aiosqlite + raw SQL (no ORM) — match prayer-bot pattern
- APScheduler AsyncIOScheduler — same loop as the bot
- python-dateutil for recurrence, Babel for i18n, rapidfuzz for item search
- Python 3.12-slim Docker base + curl injected for deploy notifications

## Conventions

- **All amounts stored as INTEGER cents.** 1 EGP = 100 cents. Never floats.
- **All timestamps stored as UTC ISO 8601 strings.** Display layer converts to Africa/Cairo.
- **Soft delete** via `deleted_at TEXT NULL`. Never `DELETE` financial rows.
- **Auth gate**: every handler must check `from_user.id in ALLOWED_USERS`. Use `@require_allowed_user` decorator from `src/auth.py`.
- **Bilingual entities**: `name_ar` and `name_en` columns; user enters one, display falls back to the other when empty.
- **Migrations**: list of `ALTER TABLE` statements wrapped in try/except (matches prayer-bot pattern in `src/db/schema.py`). Add new migrations to the end of the list — never modify existing ones.

## Layout

```
src/
  main.py            entrypoint (init_db, scheduler, dispatcher, polling)
  config.py          env loading
  bot_instance.py    Bot() singleton (separate to avoid circular imports)
  auth.py            require_allowed_user decorator
  state.py           in-memory state (active draft sessions, etc.)
  localization.py    STRINGS["en"|"ar"][key] + t() + format_currency
  scheduler.py       APScheduler job builders
  db/                CRUD per table, raw SQL
  handlers/          one router per feature area
  services/          business logic (sms_parser, recurrence, reports, dedup)
  utils/             currency/numbers/dates/keyboards/fuzzy helpers
  webhook/           reserved for v2 (HTTPS SMS endpoint) — empty in v1
tests/               pytest + pytest-asyncio (asyncio_mode=auto)
docs/                architecture, data-model, ios-shortcut, cib-sms, corner-cases, deploy, user-guide
```

## SMS-import path (v1 = Path B, Telegram-based)

iOS Shortcut opens `https://t.me/<bot>?text=<sms_text>` → user taps Send → bot's normal message handler parses with `services/sms_parser.py` → creates draft Transaction → asks for category/item/place via inline keyboard. **No HTTPS endpoint, no aiohttp server, no webhook secret in v1.** Path A (silent webhook) reserved for v2.

## Coolify deploy

See `docs/deploy.md` and the parent `/Users/abdullahwafik/Downloads/projects/COOLIFY_DEPLOY_GUIDE.md`. Watch paths: `src/**\nrequirements.txt\nDockerfile`. Always set `is_preview: false` on env vars. `docker_compose_location` must be patched to `/docker-compose.yml`.

## Things that have killed the project (would, if not handled)

See `docs/corner-cases.md`. The 15 corners enumerated there are required design constraints, not nice-to-haves. Don't merge work that breaks any of them.

## Testing

- `pytest.ini` has `asyncio_mode = auto`
- In-memory aiosqlite via fixture in `tests/conftest.py`
- Critical tests: `test_sms_parser_cib`, `test_dedup`, `test_recurrence`, `test_dst`, `test_reconciliation`, `test_debt_lifecycle`, `test_refund`, `test_net_worth`, `test_i18n_fallback`, `test_auth_handler`

## Don't

- Don't store amounts as floats.
- Don't use `DELETE FROM transactions` — soft-delete only.
- Don't auto-merge transactions silently — always prompt user.
- Don't leak BOT_TOKEN, ALLOWED_USERS, or any DB content into git (repo is public).
- Don't bypass the auth gate on any handler.
