"""
Unit tests for money primitives module.

Tests the canonical money conversion and arithmetic operations
with strict edge case coverage.
"""

from decimal import Decimal

import pytest

from app.core.money import (
    MoneyCents,
    BasisPoints,
    MoneyParseError,
    MoneyOverflowError,
    to_cents,
    from_cents,
    to_basis_points,
    add_cents,
    subtract_cents,
)


class TestToCents:
    """Tests for to_cents() conversion function."""

    def test_string_whole_number(self):
        """String without decimals converts correctly."""
        assert to_cents("500") == 50000

    def test_string_one_decimal(self):
        """String with one decimal place converts correctly."""
        assert to_cents("500.0") == 50000

    def test_string_two_decimals(self):
        """String with two decimal places converts correctly."""
        assert to_cents("500.00") == 50000

    def test_string_with_cents(self):
        """String with non-zero cents converts correctly."""
        assert to_cents("123.45") == 12345

    def test_string_sub_cent_precision_fails(self):
        """String with sub-cent precision raises error."""
        with pytest.raises(MoneyParseError, match="Sub-cent precision"):
            to_cents("500.005")

    def test_string_trailing_zeros_sub_cent_ok(self):
        """Trailing zeros that resolve to cents are OK."""
        assert to_cents("500.100") == 50010

    def test_negative_without_flag_fails(self):
        """Negative amount without allow_negative raises error."""
        with pytest.raises(MoneyParseError, match="Negative amount"):
            to_cents("-1.00")

    def test_negative_with_flag_succeeds(self):
        """Negative amount with allow_negative=True succeeds."""
        assert to_cents("-1.00", allow_negative=True) == -100

    def test_integer_input(self):
        """Integer input converts correctly (as dollars)."""
        assert to_cents(500) == 50000

    def test_float_input(self):
        """Float input converts correctly."""
        assert to_cents(123.45) == 12345

    def test_decimal_input(self):
        """Decimal input converts correctly."""
        assert to_cents(Decimal("123.45")) == 12345

    def test_zero(self):
        """Zero converts correctly."""
        assert to_cents("0") == 0
        assert to_cents("0.00") == 0
        assert to_cents(0) == 0

    def test_empty_string_fails(self):
        """Empty string raises error."""
        with pytest.raises(MoneyParseError, match="Empty amount"):
            to_cents("")

    def test_whitespace_string_fails(self):
        """Whitespace-only string raises error."""
        with pytest.raises(MoneyParseError, match="Empty amount"):
            to_cents("   ")

    def test_currency_symbol_stripped(self):
        """Currency symbols are stripped."""
        assert to_cents("$500.00") == 50000
        assert to_cents("€100.00") == 10000
        assert to_cents("£50.00") == 5000

    def test_invalid_string_fails(self):
        """Invalid string raises error."""
        with pytest.raises(MoneyParseError, match="Invalid monetary"):
            to_cents("not-a-number")

    def test_unsupported_currency_fails(self):
        """Unsupported currency raises error."""
        with pytest.raises(ValueError, match="Unsupported currency"):
            to_cents("100.00", currency="XYZ")

    def test_supported_currencies(self):
        """All supported currencies work."""
        for currency in ["USD", "EUR", "GBP", "CAD", "AUD", "JPY"]:
            assert to_cents("100.00", currency=currency) == 10000

    def test_large_amount(self):
        """Large but valid amounts work."""
        assert to_cents("1000000000.00") == 100000000000  # $1 billion

    def test_overflow_fails(self):
        """Amounts exceeding MAX_CENTS fail."""
        with pytest.raises(MoneyOverflowError):
            to_cents("100000000000000.00")  # $100 trillion


class TestFromCents:
    """Tests for from_cents() conversion function."""

    def test_positive_amount(self):
        """Positive cents convert to string correctly."""
        assert from_cents(MoneyCents(50000)) == "500.00"

    def test_amount_with_cents(self):
        """Amount with non-zero cents converts correctly."""
        assert from_cents(MoneyCents(12345)) == "123.45"

    def test_negative_amount(self):
        """Negative cents convert correctly."""
        assert from_cents(MoneyCents(-100)) == "-1.00"

    def test_zero(self):
        """Zero converts correctly."""
        assert from_cents(MoneyCents(0)) == "0.00"

    def test_small_amount(self):
        """Small amounts (under $1) convert correctly."""
        assert from_cents(MoneyCents(1)) == "0.01"
        assert from_cents(MoneyCents(99)) == "0.99"


class TestToBasisPoints:
    """Tests for to_basis_points() calculation function."""

    def test_fifty_percent(self):
        """50% ratio converts to 5000 basis points."""
        assert to_basis_points(MoneyCents(5000), MoneyCents(10000)) == 5000

    def test_one_hundred_percent(self):
        """100% ratio converts to 10000 basis points."""
        assert to_basis_points(MoneyCents(10000), MoneyCents(10000)) == 10000

    def test_one_hundred_fifty_percent(self):
        """150% ratio (ghost revenue) converts to 15000 basis points."""
        assert to_basis_points(MoneyCents(15000), MoneyCents(10000)) == 15000

    def test_zero_numerator(self):
        """Zero numerator returns 0 basis points."""
        assert to_basis_points(MoneyCents(0), MoneyCents(10000)) == 0

    def test_zero_denominator_fails(self):
        """Zero denominator raises ZeroDivisionError."""
        with pytest.raises(ZeroDivisionError):
            to_basis_points(MoneyCents(5000), MoneyCents(0))

    def test_small_percentage(self):
        """Small percentages calculate correctly."""
        # 1% = 100 basis points
        assert to_basis_points(MoneyCents(100), MoneyCents(10000)) == 100


class TestAddCents:
    """Tests for add_cents() safe addition function."""

    def test_add_two_amounts(self):
        """Two amounts add correctly."""
        assert add_cents(MoneyCents(100), MoneyCents(200)) == 300

    def test_add_multiple_amounts(self):
        """Multiple amounts add correctly."""
        result = add_cents(
            MoneyCents(100),
            MoneyCents(200),
            MoneyCents(300),
            MoneyCents(400),
        )
        assert result == 1000

    def test_add_with_negative(self):
        """Adding negative amounts works correctly."""
        assert add_cents(MoneyCents(500), MoneyCents(-200)) == 300

    def test_add_to_zero(self):
        """Adding to zero works correctly."""
        assert add_cents(MoneyCents(0), MoneyCents(100)) == 100

    def test_empty_sum(self):
        """Empty sum returns zero."""
        assert add_cents() == 0


class TestSubtractCents:
    """Tests for subtract_cents() safe subtraction function."""

    def test_subtract_positive_result(self):
        """Subtraction with positive result works."""
        assert subtract_cents(MoneyCents(500), MoneyCents(200)) == 300

    def test_subtract_negative_result(self):
        """Subtraction with negative result works."""
        assert subtract_cents(MoneyCents(200), MoneyCents(500)) == -300

    def test_subtract_to_zero(self):
        """Subtracting equal amounts returns zero."""
        assert subtract_cents(MoneyCents(500), MoneyCents(500)) == 0


class TestRoundTrip:
    """Tests for round-trip conversions."""

    def test_to_from_cents_round_trip(self):
        """Converting to cents and back preserves value."""
        original = "123.45"
        cents = to_cents(original)
        result = from_cents(cents)
        assert result == original

    def test_idempotent_parsing(self):
        """Parsing the same value twice gives same result."""
        value = "999.99"
        assert to_cents(value) == to_cents(value)
