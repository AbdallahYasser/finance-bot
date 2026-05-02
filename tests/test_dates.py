"""Date parsing + relative formatting helpers."""
import re
from datetime import datetime, timedelta

import pytz
import pytest

from src import config
from src.utils import dates as d


def test_now_utc_iso_format():
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", d.now_utc_iso())


def test_days_ago_utc_iso_offset():
    s_now = d.now_utc_iso()
    s_yes = d.days_ago_utc_iso(1)
    now = datetime.strptime(s_now, "%Y-%m-%dT%H:%M:%SZ")
    yes = datetime.strptime(s_yes, "%Y-%m-%dT%H:%M:%SZ")
    delta = now - yes
    # close to 24 hours (allow 1 minute slack)
    assert timedelta(hours=23, minutes=59) <= delta <= timedelta(hours=24, minutes=1)


def test_parse_today_yesterday():
    today_iso = d.parse_user_date("today")
    yesterday_iso = d.parse_user_date("yesterday")
    tz = pytz.timezone(config.TIMEZONE)
    today_local = datetime.now(tz).date()
    assert today_iso[:10] == today_local.strftime("%Y-%m-%d")
    yest_local = today_local - timedelta(days=1)
    assert yesterday_iso[:10] == yest_local.strftime("%Y-%m-%d") or \
           yesterday_iso[:10] == today_local.strftime("%Y-%m-%d")  # near tz boundary


def test_parse_iso_format():
    iso = d.parse_user_date("2026-05-01")
    assert iso.startswith("2026-05-01") or iso.startswith("2026-04-30")  # tz-dependent


def test_parse_dmy_with_dash():
    iso = d.parse_user_date("01-05-2026")
    assert "2026" in iso
    assert "05-01" in iso or "04-30" in iso


def test_parse_dmy_with_slash():
    iso = d.parse_user_date("1/5/2026")
    assert "2026" in iso


def test_parse_dm_uses_current_year():
    tz = pytz.timezone(config.TIMEZONE)
    this_year = datetime.now(tz).year
    iso = d.parse_user_date("01/05")
    assert str(this_year) in iso


@pytest.mark.parametrize("bad", ["", "  ", "abc", "13/13/2026", "0/0/2026", "tomorrow"])
def test_parse_rejects_bad(bad):
    with pytest.raises(ValueError):
        d.parse_user_date(bad)


def test_format_today():
    s = d.format_date_relative(d.now_utc_iso())
    assert s.startswith("today ")


def test_format_yesterday():
    s = d.format_date_relative(d.days_ago_utc_iso(1))
    assert s == "yesterday"


def test_format_n_days_ago():
    assert d.format_date_relative(d.days_ago_utc_iso(3)) == "3 days ago"
    assert d.format_date_relative(d.days_ago_utc_iso(6)) == "6 days ago"


def test_format_old_date_uses_iso():
    s = d.format_date_relative(d.days_ago_utc_iso(30))
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", s)


def test_format_empty_or_invalid():
    assert d.format_date_relative("") == "—"
    assert d.format_date_relative(None) == "—"


def test_format_handles_sqlite_datetime():
    """SQLite default 'datetime(now)' returns 'YYYY-MM-DD HH:MM:SS' (no T, no Z)."""
    sqlite_now = datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")
    s = d.format_date_relative(sqlite_now)
    # Either 'today HH:MM' or a date string — never error
    assert s and s != "—"
