"""User-facing date helpers — Africa/Cairo display, UTC storage."""
import re
from datetime import datetime, timedelta

import pytz

from src import config


def _local_tz():
    return pytz.timezone(config.TIMEZONE)


def now_utc_iso() -> str:
    """UTC ISO 8601 'now' for storage."""
    return datetime.now(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def days_ago_utc_iso(n: int) -> str:
    """N calendar days ago at the user's local clock time, returned as UTC ISO."""
    tz = _local_tz()
    local_now = datetime.now(tz)
    target_local = local_now - timedelta(days=n)
    return target_local.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


_DATE_RE_ISO = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_DATE_RE_DMY = re.compile(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$")
_DATE_RE_DM  = re.compile(r"^(\d{1,2})[-/](\d{1,2})$")


def parse_user_date(text: str) -> str:
    """Parse a user-typed date and return UTC ISO at noon Cairo time.

    Accepts:
        today, now            → today's date
        yesterday             → today - 1 day
        YYYY-MM-DD            → ISO
        DD-MM-YYYY, DD/MM/YYYY → day-month-year
        DD-MM, DD/MM          → day-month, current year

    Raises ValueError on bad input.
    """
    if text is None:
        raise ValueError("empty date")
    s = text.strip().lower()
    if not s:
        raise ValueError("empty date")

    tz = _local_tz()
    today_local = datetime.now(tz).date()

    if s in ("today", "now"):
        target = today_local
    elif s == "yesterday":
        target = today_local - timedelta(days=1)
    else:
        m = _DATE_RE_ISO.match(s)
        if m:
            y, mo, d = (int(x) for x in m.groups())
        else:
            m = _DATE_RE_DMY.match(s)
            if m:
                d, mo, y = (int(x) for x in m.groups())
            else:
                m = _DATE_RE_DM.match(s)
                if m:
                    d, mo = (int(x) for x in m.groups())
                    y = today_local.year
                else:
                    raise ValueError(f"could not parse date: {text!r}")
        try:
            target = datetime(y, mo, d).date()
        except ValueError as e:
            raise ValueError(f"invalid date: {text!r}") from e

    # Noon Cairo on the target calendar day → UTC ISO
    naive = datetime(target.year, target.month, target.day, 12, 0)
    local_dt = tz.localize(naive)
    return local_dt.astimezone(pytz.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso_to_utc(iso: str) -> datetime:
    """Parse a stored timestamp ('YYYY-MM-DDTHH:MM:SSZ' or
    'YYYY-MM-DD HH:MM:SS') and return a UTC-aware datetime."""
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        dt = datetime.strptime(iso, "%Y-%m-%d %H:%M:%S")
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(pytz.UTC)


def format_date_relative(iso_utc: str, lang: str = "en") -> str:
    """Format a stored ISO UTC timestamp as a short user-facing date.

    Returns: 'today HH:MM' / 'yesterday' / 'N days ago' / 'YYYY-MM-DD'.
    """
    if not iso_utc:
        return "—"
    try:
        dt_utc = _parse_iso_to_utc(iso_utc)
    except ValueError:
        return iso_utc[:10]

    tz = _local_tz()
    local = dt_utc.astimezone(tz)
    today_local = datetime.now(tz).date()
    delta_days = (today_local - local.date()).days

    if delta_days == 0:
        return f"today {local.strftime('%H:%M')}"
    if delta_days == 1:
        return "yesterday"
    if 2 <= delta_days <= 6:
        return f"{delta_days} days ago"
    if delta_days < 0:
        return local.strftime("%Y-%m-%d")  # future-dated
    return local.strftime("%Y-%m-%d")
