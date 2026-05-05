import pytest

from stonks.ui.detail_view import format_number


def test_none_returns_placeholder():
    assert format_number(None, "currency") == "--"
    assert format_number(None, "number") == "--"


def test_invalid_value_returns_placeholder():
    assert format_number("not-a-number", "currency") == "--"


def test_currency():
    assert format_number(1234.5, "currency") == "1,234.50"
    assert format_number(0, "currency") == "0.00"


def test_currency_with_prefix():
    assert format_number(1234.5, "currency", prefix="$") == "$1,234.50"
    assert format_number(0, "currency", prefix="£") == "£0.00"


def test_currency_with_suffix():
    assert format_number(1234.5, "currency", suffix="€") == "1,234.50€"
    assert format_number(0, "currency", suffix="kr") == "0.00kr"


def test_percent():
    assert format_number(0.05, "percent") == "5.00%"
    assert format_number(0, "percent") == "0.00%"


def test_decimal():
    assert format_number(32.567, "decimal") == "32.57"


def test_number_raw():
    assert format_number(999, "number") == "999"


def test_number_thousands():
    assert format_number(1_500, "number") == "1.5K"


def test_number_millions():
    assert format_number(2_500_000, "number") == "2.5M"


def test_number_billions():
    assert format_number(1_800_000_000, "number") == "1.80B"


def test_large_number_billions():
    assert format_number(3_100_000_000_000, "large_number") == "3.10T"


def test_large_number_with_prefix():
    assert format_number(3_100_000_000_000, "large_number", prefix="$") == "$3.10T"
    assert format_number(2_500_000_000, "large_number", prefix="£") == "£2.50B"


def test_large_number_with_suffix():
    assert format_number(3_100_000_000_000, "large_number", suffix="€") == "3.10T€"
    assert format_number(2_500_000, "large_number", suffix="€") == "2.5M€"


def test_large_number_millions():
    assert format_number(2_500_000_000, "large_number") == "2.50B"


@pytest.mark.parametrize("fmt_type", ["currency", "percent", "decimal", "number", "large_number"])
def test_integer_input_is_accepted(fmt_type):
    result = format_number(100, fmt_type)
    assert result != "--"
