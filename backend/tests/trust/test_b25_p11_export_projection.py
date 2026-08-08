"""B2.5-P11 display honesty, format validity, and injection proofs."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator
from openpyxl import load_workbook

from app.api.export import (
    CSV_COLUMNS,
    EXPORT_ROW_ALLOWLIST,
    _csv_from_rows,
    _enforce_export_payload_no_leak,
    _xlsx_from_projection,
)
from app.trust.export_projection import (
    PROJECTION_AUTHORITY_NON_AUTHORITATIVE,
    PROJECTION_SCHEMA_VERSION,
    build_display_projection,
    project_display_rows,
)
from app.trust.spreadsheet_safety import (
    SpreadsheetSafetyError,
    neutralize_spreadsheet_cell,
)


ROOT = Path(__file__).resolve().parents[3]


def _walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _projection(channels: list[str] | None = None) -> tuple[object, dict[str, object]]:
    tenant_id = uuid4()
    values = channels or ["Zulu", "Alpha"]
    source_rows = [
        {
            "export_date": date(2026, 8, 8),
            "channel_code": value,
            "revenue_cents": 12_505 + index,
            "conversion_count": index + 1,
            "confidence_score": Decimal("0.92"),
        }
        for index, value in enumerate(values)
    ]
    payload = build_display_projection(
        tenant_id=tenant_id,
        start=date(2026, 8, 1),
        end=date(2026, 8, 8),
        source_rows=reversed(source_rows),
        generated_at=datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc),
    )
    return tenant_id, payload


def test_display_projection_is_closed_honest_tenant_safe_and_float_free() -> None:
    tenant_id, payload = _projection()
    schema = json.loads(
        (ROOT / "contracts/trust-api/export-projection.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(payload)
    _enforce_export_payload_no_leak(payload)
    assert payload["projection_authority"] == PROJECTION_AUTHORITY_NON_AUTHORITATIVE
    assert payload["projection_schema_version"] == PROJECTION_SCHEMA_VERSION
    assert "tenant_id" not in payload
    assert str(tenant_id) not in json.dumps(payload, ensure_ascii=False)
    assert all(not isinstance(value, float) for value in _walk(payload))
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert [row["channel"] for row in rows] == ["Alpha", "Zulu"]
    assert all(set(row) == set(EXPORT_ROW_ALLOWLIST) for row in rows)
    assert rows[0]["revenue_display"] == "125.06"
    assert rows[0]["confidence_display"] == "0.92"


def test_projection_order_is_independent_of_database_result_order() -> None:
    source = [
        {
            "export_date": date(2026, 8, 9),
            "channel_code": "Bravo",
            "revenue_cents": 2,
            "conversion_count": 1,
            "confidence_score": Decimal("0.50"),
        },
        {
            "export_date": date(2026, 8, 8),
            "channel_code": "Zulu",
            "revenue_cents": 1,
            "conversion_count": 1,
            "confidence_score": Decimal("0.50"),
        },
        {
            "export_date": date(2026, 8, 8),
            "channel_code": "Alpha",
            "revenue_cents": 3,
            "conversion_count": 1,
            "confidence_score": Decimal("0.50"),
        },
    ]
    assert project_display_rows(source) == project_display_rows(reversed(source))


def test_csv_round_trip_handles_adversarial_text_without_column_drift() -> None:
    channels = [
        "comma,value",
        'quote"value',
        "line\nvalue",
        "carriage\rvalue",
        "東京-Café",
        "",
        "x" * 256,
    ]
    _, payload = _projection(channels)
    rows = payload["rows"]
    assert isinstance(rows, list)
    rendered = _csv_from_rows(rows)
    parsed = list(csv.reader(StringIO(rendered, newline="")))
    assert tuple(parsed[0]) == CSV_COLUMNS
    assert len(parsed) == len(rows) + 1
    assert [record[1] for record in parsed[1:]] == [str(row["channel"]) for row in rows]
    assert rendered.endswith("\r\n")


def test_formula_prefixes_are_text_in_csv_and_real_xlsx() -> None:
    formulas = [
        "=1+1",
        "+SUM(A1:A2)",
        "-1+2",
        "@SUM(A1:A2)",
        '=HYPERLINK("https://invalid.example","x")',
        "\t=1+1",
        "\r=1+1",
    ]
    tenant_id, payload = _projection(formulas)
    rows = payload["rows"]
    assert isinstance(rows, list)
    assert all(str(row["channel"]).startswith("'") for row in rows)

    parsed = list(csv.reader(StringIO(_csv_from_rows(rows), newline="")))
    assert all(record[1].startswith("'") for record in parsed[1:])

    workbook_bytes = _xlsx_from_projection(payload)
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False)
    assert workbook.sheetnames == ["Export", "Metadata"]
    export_sheet = workbook["Export"]
    assert tuple(cell.value for cell in export_sheet[1]) == CSV_COLUMNS
    for cell in export_sheet["B"][1:]:
        assert isinstance(cell.value, str) and cell.value.startswith("'")
        assert cell.data_type != "f"
    metadata_values = [cell.value for row in workbook["Metadata"] for cell in row]
    assert PROJECTION_AUTHORITY_NON_AUTHORITATIVE in metadata_values
    assert PROJECTION_SCHEMA_VERSION in metadata_values
    assert str(tenant_id) not in "|".join(str(value) for value in metadata_values)


def test_spreadsheet_transform_refuses_machine_authority_field_paths() -> None:
    assert neutralize_spreadsheet_cell("=1+1") == "'=1+1"
    try:
        neutralize_spreadsheet_cell(
            "=1+1",
            field_path="envelopes[].verified_revenue_minor",
        )
    except SpreadsheetSafetyError as exc:
        assert "machine_authority_field_neutralization_forbidden" in str(exc)
    else:
        raise AssertionError("machine-authority spreadsheet mutation was accepted")
