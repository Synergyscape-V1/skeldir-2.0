"""Pure non-authoritative legacy export projection for B2.5-P11."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from uuid import UUID

from app.trust.refusal import tenant_hash
from app.trust.spreadsheet_safety import neutralize_spreadsheet_cell


PROJECTION_AUTHORITY_NON_AUTHORITATIVE = "non_authoritative_display"
PROJECTION_SCHEMA_VERSION = "b25-p11-display-v1"
_CENT = Decimal("0.01")


class ExportProjectionError(ValueError):
    """Raised when a legacy row cannot be projected without inventing truth."""


def _utc_second(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ExportProjectionError("generated_at_timezone_required")
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _minor_display(value: int) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ExportProjectionError("revenue_minor_must_be_integer")
    return format((Decimal(value) / Decimal(100)).quantize(_CENT), ".2f")


def _confidence_display(value: object) -> str:
    if isinstance(value, float):
        raise ExportProjectionError("display_confidence_float_forbidden")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ExportProjectionError("display_confidence_invalid") from exc
    if not decimal_value.is_finite():
        raise ExportProjectionError("display_confidence_non_finite")
    rendered = format(decimal_value.quantize(_CENT), "f")
    return rendered.rstrip("0").rstrip(".") or "0"


def project_display_rows(
    source_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Project and deterministically order display-only channel/day rows."""
    rows: list[dict[str, object]] = []
    for source in source_rows:
        raw_date = source.get("date", source.get("export_date"))
        date_text = (
            raw_date.isoformat() if isinstance(raw_date, date) else str(raw_date)
        )
        channel_text = str(source.get("channel", source.get("channel_code", "")))
        raw_minor = source.get("revenue_minor", source.get("revenue_cents"))
        if isinstance(raw_minor, bool) or not isinstance(raw_minor, int):
            raise ExportProjectionError("revenue_minor_must_be_integer")
        raw_conversions = source.get("conversions", source.get("conversion_count"))
        if isinstance(raw_conversions, bool) or not isinstance(raw_conversions, int):
            raise ExportProjectionError("conversions_must_be_integer")
        raw_confidence = source.get(
            "confidence_display",
            source.get("confidence_score", Decimal(0)),
        )
        rows.append(
            {
                "date": neutralize_spreadsheet_cell(
                    date_text, field_path="rows[].date"
                ),
                "channel": neutralize_spreadsheet_cell(
                    channel_text, field_path="rows[].channel"
                ),
                "revenue_minor": raw_minor,
                "revenue_display": _minor_display(raw_minor),
                "conversions": raw_conversions,
                "confidence_display": _confidence_display(raw_confidence),
            }
        )
    return sorted(rows, key=lambda row: (str(row["date"]), str(row["channel"])))


def build_display_projection(
    *,
    tenant_id: UUID,
    start: date,
    end: date,
    source_rows: Iterable[Mapping[str, object]],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the closed, explicitly non-authoritative JSON display shape."""
    return {
        "projection_authority": PROJECTION_AUTHORITY_NON_AUTHORITATIVE,
        "projection_schema_version": PROJECTION_SCHEMA_VERSION,
        "tenant_id_hash": tenant_hash(tenant_id),
        "generated_at": _utc_second(generated_at or datetime.now(timezone.utc)),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "rows": project_display_rows(source_rows),
    }
