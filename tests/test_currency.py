"""parse_amount + format_amount_cents — Western digits only in M1."""
import pytest

from src.utils.currency import parse_amount, format_amount_cents


def test_plain_integer():
    assert parse_amount("250") == 25000


def test_zero():
    assert parse_amount("0") == 0


def test_one_cent():
    assert parse_amount("0.01") == 1


def test_dot_decimal_one_digit():
    assert parse_amount("250.5") == 25050


def test_dot_decimal_two_digits():
    assert parse_amount("250.50") == 25050


def test_comma_decimal_eu_style():
    assert parse_amount("250,5") == 25050


def test_thousands_separator_with_decimal():
    assert parse_amount("1,234.50") == 123450


def test_thousands_separator_no_decimal():
    assert parse_amount("1,234") == 123400


def test_large_thousands():
    assert parse_amount("1,234,567") == 123456700


def test_strips_whitespace():
    assert parse_amount("  250  ") == 25000


@pytest.mark.parametrize("bad", ["", "  ", "abc", "-5", "5.5.5", "5e2", "1.234.50"])
def test_rejects(bad):
    with pytest.raises(ValueError):
        parse_amount(bad)


# ---------- Tolerant parsing (new) ----------

def test_strips_egp_suffix():
    assert parse_amount("250 EGP") == 25000
    assert parse_amount("250egp") == 25000


def test_strips_le_suffix():
    assert parse_amount("250 LE") == 25000


def test_strips_pound_suffix():
    assert parse_amount("250 pound") == 25000
    assert parse_amount("250 pounds") == 25000


def test_strips_arabic_currency_suffix():
    assert parse_amount("250 جنيه") == 25000
    assert parse_amount("250 ج.م") == 25000
    assert parse_amount("250 ج") == 25000


def test_leading_plus_sign():
    assert parse_amount("+250") == 25000
    assert parse_amount("+ 250") == 25000


def test_arabic_indic_digits():
    assert parse_amount("٢٥٠") == 25000
    assert parse_amount("١٢٣٤٫٥٠") == 123450  # ٫ is Arabic decimal sep


def test_persian_digits():
    assert parse_amount("۲۵۰") == 25000


def test_space_as_thousand_separator():
    assert parse_amount("1 234") == 123400
    assert parse_amount("1 234.50") == 123450


def test_truncates_extra_decimals():
    # 0.123 → 0.12 (truncated, no rounding)
    assert parse_amount("0.123") == 12
    assert parse_amount("250.999") == 25099


def test_combined_currency_and_decimal():
    assert parse_amount("1,234.50 EGP") == 123450
    assert parse_amount("+1,234 ج.م") == 123400


def test_format_basic():
    assert format_amount_cents(25000) == "250.00 EGP"


def test_format_with_thousands():
    assert format_amount_cents(1234500) == "12,345.00 EGP"


def test_format_zero():
    assert format_amount_cents(0) == "0.00 EGP"


def test_format_negative():
    assert format_amount_cents(-25000) == "-250.00 EGP"


def test_roundtrip():
    for s, cents in [("250", 25000), ("250.50", 25050), ("1,234.50", 123450)]:
        assert parse_amount(s) == cents
        # format then re-parse — should match
        formatted = format_amount_cents(cents).replace(" EGP", "")
        assert parse_amount(formatted) == cents
