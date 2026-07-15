"""Exact base-unit conversions without binary floating point."""

from decimal import Decimal, InvalidOperation, ROUND_DOWN, localcontext


def to_base_units(amount: str | int | Decimal, decimals: int) -> int:
    if not isinstance(decimals, int) or decimals < 0:
        raise ValueError("decimals must be a non-negative integer")
    try:
        with localcontext() as context:
            context.prec = max(80, len(str(amount)) + decimals + 4)
            return int((Decimal(str(amount)) * (Decimal(10) ** decimals)).to_integral_value(rounding=ROUND_DOWN))
    except InvalidOperation as error:
        raise ValueError("amount must be a finite decimal value") from error


def from_base_units(amount: str | int, decimals: int) -> str:
    if not isinstance(decimals, int) or decimals < 0:
        raise ValueError("decimals must be a non-negative integer")
    value = int(amount)
    if decimals == 0:
        return str(value)
    sign = "-" if value < 0 else ""
    digits = str(abs(value)).rjust(decimals + 1, "0")
    whole, fraction = digits[:-decimals], digits[-decimals:].rstrip("0")
    return sign + whole + (f".{fraction}" if fraction else "")
