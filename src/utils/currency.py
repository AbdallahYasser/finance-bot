"""Parsing and formatting EGP amounts.

Tolerates common shapes of user input:
- Plain integer:           250
- Dot decimal:             250.50    (any precision; truncated to 2)
- Comma decimal (EU):      250,50
- Thousands separator:     1,234.50  /  1,234  /  1 234.50
- Currency suffix:         250 EGP / 250 LE / 250 pound / 250 ج.م / 250 جنيه
- Leading +:               +250
- Arabic-Indic digits:     ٢٥٠         (٠-٩ → 0-9)
- Arabic decimal sep:      ٢٥٠٫٥٠      (٫ → .)
- Arabic thousand sep:     ١٬٢٣٤٫٥٠    (٬ stripped)

Rejects: empty, non-numeric, negatives (no leading -), `5e2`, `5.5.5`.

Amounts are stored as INTEGER cents (1 EGP = 100 cents) to avoid float drift.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

# AR-Indic and Persian-Indic digits → Western
_DIGIT_TRANSLATE = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

_CURRENCY_SUFFIX = re.compile(
    r"\s*(?:EGP|LE|pounds?|جنيه|ج\.م|ج)\s*$",
    re.IGNORECASE,
)

_SPACE_AS_THOU = re.compile(r"^\d{1,3}( \d{3})+(\.\d+)?$")

_PATTERNS = [
    (re.compile(r"^\d+$"),                        "int"),
    (re.compile(r"^\d+\.\d+$"),                   "dot"),
    (re.compile(r"^\d+,\d{1,2}$"),                "comma"),
    (re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$"),   "thou"),
]


def parse_amount(text: str) -> int:
    """Parse a user-provided amount string into integer cents.

    Raises ValueError on bad input.
    """
    if text is None:
        raise ValueError("empty amount")

    # Unicode normalize (NFKC handles fullwidth digits, ZWJs, etc.)
    s = unicodedata.normalize("NFKC", text).strip()
    # Arabic decimal/thousand separators → Western
    s = s.replace("٫", ".").replace("٬", "").replace("،", ",")
    # Arabic-Indic digits → Western
    s = s.translate(_DIGIT_TRANSLATE)
    # Drop a leading plus sign
    if s.startswith("+"):
        s = s[1:].lstrip()
    # Strip a currency suffix (EGP / LE / pound / pounds / ج / ج.م / جنيه)
    s = _CURRENCY_SUFFIX.sub("", s).strip()
    # Space-as-thousand-separator: collapse only if the whole string fits
    if _SPACE_AS_THOU.match(s):
        s = s.replace(" ", "")

    if not s:
        raise ValueError(f"could not parse amount: {text!r}")

    for pat, kind in _PATTERNS:
        if not pat.match(s):
            continue
        if kind == "int":
            return int(s) * 100
        if kind == "dot":
            whole, frac = s.split(".")
            return int(whole) * 100 + int(frac[:2].ljust(2, "0"))
        if kind == "comma":
            whole, frac = s.split(",")
            return int(whole) * 100 + int(frac[:2].ljust(2, "0"))
        if kind == "thou":
            s2 = s.replace(",", "")
            if "." in s2:
                whole, frac = s2.split(".")
                return int(whole) * 100 + int(frac[:2].ljust(2, "0"))
            return int(s2) * 100

    raise ValueError(f"could not parse amount: {text!r}")


def format_amount_cents(cents: int, lang: str = "en") -> str:
    """Format integer cents as a currency string. M1: Western digits + ' EGP'."""
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole, frac = divmod(cents, 100)
    return f"{sign}{whole:,}.{frac:02d} EGP"
