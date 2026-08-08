"""Display-only spreadsheet formula neutralization for B2.5-P11 exports."""

from __future__ import annotations


_FORMULA_PREFIXES = frozenset({"=", "+", "-", "@", "\t", "\r"})
_DISPLAY_FIELD_PATHS = frozenset(
    {
        "display",
        "rows[].date",
        "rows[].channel",
        "csv.date",
        "csv.channel",
        "xlsx.date",
        "xlsx.channel",
    }
)


class SpreadsheetSafetyError(ValueError):
    """Raised if neutralization is requested outside the display projection."""


def neutralize_spreadsheet_cell(value: str, *, field_path: str = "display") -> str:
    """Prefix spreadsheet-active display text with an apostrophe.

    This transform is deliberately unavailable to machine-authority fields so
    presentation safety can never mutate signed financial truth.
    """
    if field_path not in _DISPLAY_FIELD_PATHS:
        raise SpreadsheetSafetyError(
            f"machine_authority_field_neutralization_forbidden:{field_path}"
        )
    if not isinstance(value, str):
        raise SpreadsheetSafetyError("spreadsheet_display_value_must_be_string")
    if value and value[0] in _FORMULA_PREFIXES:
        return f"'{value}"
    return value
