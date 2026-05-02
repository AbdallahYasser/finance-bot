import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DB_PATH: str = os.getenv("DB_PATH", "/app/data/finance_bot.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
TIMEZONE: str = os.getenv("TIMEZONE", "Africa/Cairo")
DEFAULT_LANGUAGE: str = os.getenv("DEFAULT_LANGUAGE", "en")

_raw = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS: set[int] = {int(x.strip()) for x in _raw.split(",") if x.strip().isdigit()}

# Note: DB directory creation moved to db.schema.init_db() so that imports
# don't have side effects on the host filesystem (matters for tests).
