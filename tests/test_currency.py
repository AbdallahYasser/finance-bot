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
