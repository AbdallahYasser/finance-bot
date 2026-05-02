"""Parsing and formatting EGP amounts.

M1: Western digits only. Bilingual (AR-Indic) handling lands in M10
alongside the rest of the localization layer.

Amounts are stored as INTEGER cents (1 EGP = 100 cents) to avoid float drift.
"""
import re

_PATTERNS = [
    # plain integer
    (re.compile(r"^\d+$"), "int"),
    # decimal with .
    (re.compile(r"^\d+\.\d{1,2}$"), "dot"),
    # decimal with , (1-2 fractional digits — distinguishes from thousands sep)
    (re.compile(r"^\d+,\d{1,2}$"), "comma"),
    # thousands sep (one or more `,\d{3}` groups, optional .dd at end)
    (re.compile(r"^\d{1,3}(,\d{3})+(\.\d{1,2})?$"), "thou"),
]


def parse_amount(text: str) -> int:
    """Parse a user-provided amount string into integer cents.

    Accepts:
        "250"        → 25000
        "250.5"      → 25050
        "250.50"     → 25050
        "250,5"      → 25050   (EU-style comma decimal)
        "1,234.50"   → 123450  (thousands sep + decimal)
        "1,234"      → 123400  (thousands sep, no decimal)
        "0.01"       → 1

    Rejects with ValueError:
        "", "abc", "-5", "5.5.5", "5e2", whitespace-only.
    """
    if text is None:
        raise ValueError("empty amount")
    s = text.strip()
    if not s:
        raise ValueError("empty amount")

    for pat, kind in _PATTERNS:
        if pat.match(s):
            if kind == "int":
                return int(s) * 100
            if kind == "dot":
                whole, frac = s.split(".")
                return int(whole) * 100 + int(frac.ljust(2, "0"))
            if kind == "comma":
                whole, frac = s.split(",")
                return int(whole) * 100 + int(frac.ljust(2, "0"))
            if kind == "thou":
                s2 = s.replace(",", "")
                if "." in s2:
                    whole, frac = s2.split(".")
                    return int(whole) * 100 + int(frac.ljust(2, "0"))
                return int(s2) * 100

    raise ValueError(f"could not parse amount: {text!r}")


def format_amount_cents(cents: int, lang: str = "en") -> str:
    """Format integer cents as a currency string.

    M1: always Western digits + 'EGP' suffix. AR formatting lands in M10.
    """
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, frac = divmod(cents, 100)
    return f"{sign}{whole:,}.{frac:02d} EGP"
