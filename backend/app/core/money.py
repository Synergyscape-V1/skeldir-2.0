"""
Money primitives for penny-perfect financial operations.

This module provides the canonical representation and operations for monetary
values throughout the Skeldir system. All internal calculations use integer
cents to eliminate floating-point precision issues.

Design Principles:
- All money stored/computed as integer cents (MoneyCents)
- Strict parsing with explicit quantization
- No implicit float conversions
- Fail-fast on invalid inputs

Usage:
    from app.core.money import to_cents, from_cents, MoneyCents

    # Parse string amount to cents
    cents = to_cents("500.00")  # Returns 50000

    # Convert cents back to display string
    display = from_cents(50000)  # Returns "500.00"
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import NewType, Union

# Canonical type alias for monetary values in cents
MoneyCents = NewType("MoneyCents", int)

# Basis points type for percentage calculations (avoid floats)
BasisPoints = NewType("BasisPoints", int)

# Maximum allowed cents (prevents overflow, ~$10 trillion)
MAX_CENTS = 10**15

# Supported currencies (ISO 4217)
SUPPORTED_CURRENCIES = frozenset({"USD", "EUR", "GBP", "CAD", "AUD", "JPY"})


class MoneyParseError(ValueError):
    """Raised when a monetary value cannot be parsed."""
    pass


class MoneyOverflowError(ValueError):
    """Raised when a monetary value exceeds safe bounds."""
    pass


def to_cents(
    amount: Union[str, int, float, Decimal],
    *,
    allow_negative: bool = False,
    currency: str = "USD",
) -> MoneyCents:
    """
    Convert a monetary amount to integer cents with strict validation.

    This is the ONLY approved entry point for converting external monetary
    values into the internal cents representation.

    Args:
        amount: The monetary amount as string, int, float, or Decimal.
                Strings are preferred for precision (e.g., "500.00").
        allow_negative: If True, allows negative values (for refunds).
                       Defaults to False for safety.
        currency: ISO 4217 currency code. Used for validation.

    Returns:
        MoneyCents: The amount in integer cents.

    Raises:
        MoneyParseError: If the amount cannot be parsed or has too many decimals.
        MoneyOverflowError: If the amount exceeds safe bounds.
        ValueError: If currency is not supported.

    Examples:
        >>> to_cents("500")
        50000
        >>> to_cents("500.0")
        50000
        >>> to_cents("500.00")
        50000
        >>> to_cents("500.005")  # Raises MoneyParseError (sub-cent precision)
        >>> to_cents("-1.00")  # Raises MoneyParseError (negative without flag)
        >>> to_cents("-1.00", allow_negative=True)
        -100
    """
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError(f"Unsupported currency: {currency}. Supported: {SUPPORTED_CURRENCIES}")

    # Convert to Decimal for precise arithmetic
    try:
        if isinstance(amount, str):
            # Strip whitespace and currency symbols
            cleaned = amount.strip().lstrip("$€£¥")
            if not cleaned:
                raise MoneyParseError("Empty amount string")
            decimal_amount = Decimal(cleaned)
        elif isinstance(amount, float):
            # Convert float through string to avoid precision issues
            decimal_amount = Decimal(str(amount))
        elif isinstance(amount, int):
            decimal_amount = Decimal(amount)
        elif isinstance(amount, Decimal):
            decimal_amount = amount
        else:
            raise MoneyParseError(f"Unsupported type: {type(amount).__name__}")
    except InvalidOperation as e:
        raise MoneyParseError(f"Invalid monetary amount: {amount!r}") from e

    # Check for negative values
    if decimal_amount < 0 and not allow_negative:
        raise MoneyParseError(
            f"Negative amount {amount!r} not allowed. Use allow_negative=True for refunds."
        )

    # Quantize to 2 decimal places (cents)
    quantized = decimal_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Verify no sub-cent precision was lost
    if quantized != decimal_amount:
        raise MoneyParseError(
            f"Sub-cent precision not allowed: {amount!r} -> {quantized}"
        )

    # Convert to integer cents
    cents = int(quantized * 100)

    # Overflow check
    if abs(cents) > MAX_CENTS:
        raise MoneyOverflowError(
            f"Amount {amount!r} exceeds maximum ({MAX_CENTS} cents)"
        )

    return MoneyCents(cents)


def from_cents(cents: MoneyCents, *, currency: str = "USD") -> str:
    """
    Convert integer cents to a display string.

    Args:
        cents: The amount in integer cents.
        currency: ISO 4217 currency code (for future formatting).

    Returns:
        A string representation of the amount (e.g., "500.00").

    Examples:
        >>> from_cents(50000)
        "500.00"
        >>> from_cents(-100)
        "-1.00"
    """
    decimal_amount = Decimal(cents) / Decimal(100)
    return str(decimal_amount.quantize(Decimal("0.01")))


def to_basis_points(numerator: MoneyCents, denominator: MoneyCents) -> BasisPoints:
    """
    Calculate basis points (hundredths of a percent) without floats.

    basis_points = (numerator / denominator) * 10000

    This avoids floating-point division for percentage calculations.

    Args:
        numerator: The numerator in cents.
        denominator: The denominator in cents.

    Returns:
        BasisPoints: The ratio expressed in basis points (0-10000 for 0-100%).

    Raises:
        ZeroDivisionError: If denominator is zero.

    Examples:
        >>> to_basis_points(5000, 10000)  # 50%
        5000
        >>> to_basis_points(10000, 10000)  # 100%
        10000
        >>> to_basis_points(15000, 10000)  # 150%
        15000
    """
    if denominator == 0:
        raise ZeroDivisionError("Cannot calculate basis points with zero denominator")

    # Integer arithmetic: (numerator * 10000) // denominator
    return BasisPoints((numerator * 10000) // denominator)


def add_cents(*amounts: MoneyCents) -> MoneyCents:
    """
    Safely add multiple cent amounts with overflow protection.

    Args:
        *amounts: Variable number of MoneyCents values to add.

    Returns:
        MoneyCents: The sum of all amounts.

    Raises:
        MoneyOverflowError: If the sum exceeds safe bounds.
    """
    total = sum(amounts)
    if abs(total) > MAX_CENTS:
        raise MoneyOverflowError(f"Sum {total} exceeds maximum ({MAX_CENTS} cents)")
    return MoneyCents(total)


def subtract_cents(minuend: MoneyCents, subtrahend: MoneyCents) -> MoneyCents:
    """
    Safely subtract cent amounts with overflow protection.

    Args:
        minuend: The amount to subtract from.
        subtrahend: The amount to subtract.

    Returns:
        MoneyCents: The difference (minuend - subtrahend).

    Raises:
        MoneyOverflowError: If the result exceeds safe bounds.
    """
    result = minuend - subtrahend
    if abs(result) > MAX_CENTS:
        raise MoneyOverflowError(f"Difference {result} exceeds maximum ({MAX_CENTS} cents)")
    return MoneyCents(result)
