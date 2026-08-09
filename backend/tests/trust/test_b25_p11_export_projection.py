"""B2.5-P11 display honesty, format validity, and injection proofs."""

from __future__ import annotations

import asyncio
import csv
import concurrent.futures
import gc
import json
import threading
import time
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from uuid import uuid4

from jsonschema import Draft202012Validator
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import load_workbook
import psutil
import pytest
import yaml

from app.api import export as export_api
from app.db.deps import get_db_session
from app.security.auth import get_auth_context
from app.api.export import (
    CSV_COLUMNS,
    CSV_SCHEMA_VERSION,
    LEGACY_CSV_COLUMNS,
    LEGACY_CSV_SCHEMA_VERSION,
    EXPORT_ROW_ALLOWLIST,
    LEGACY_EXPORT_MAX_BYTES,
    LEGACY_EXPORT_MAX_ROWS,
    LegacyExportDeadlineExceeded,
    TRACK1_MAX_CONCURRENT_EXPORTS,
    TRACK1_MAX_SERIALIZATION_WORKING_SET_BYTES,
    XLSX_COLUMNS,
    _csv_from_rows,
    _legacy_csv_from_rows,
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
    assert all(
        record[0] == PROJECTION_AUTHORITY_NON_AUTHORITATIVE for record in parsed[1:]
    )
    assert all(record[1] == CSV_SCHEMA_VERSION for record in parsed[1:])
    assert all(len(record) == len(CSV_COLUMNS) for record in parsed)
    assert [record[3] for record in parsed[1:]] == [str(row["channel"]) for row in rows]
    assert rendered.endswith("\r\n")


def test_legacy_csv_default_contract_is_positionally_unchanged() -> None:
    _, payload = _projection(["Meta"])
    rows = payload["rows"]
    assert isinstance(rows, list)
    records = list(csv.reader(StringIO(_legacy_csv_from_rows(rows), newline="")))
    assert tuple(records[0]) == LEGACY_CSV_COLUMNS
    assert records[1] == ["2026-08-08", "Meta", "125.05", "1", "0.92"]
    assert LEGACY_CSV_SCHEMA_VERSION == "legacy-v1"


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
    assert all(record[3].startswith("'") for record in parsed[1:])

    workbook_bytes = _xlsx_from_projection(payload)
    workbook = load_workbook(BytesIO(workbook_bytes), data_only=False)
    assert workbook.sheetnames == ["Export", "Metadata"]
    export_sheet = workbook["Export"]
    assert tuple(cell.value for cell in export_sheet[1]) == XLSX_COLUMNS
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


def test_detached_csv_is_header_first_rectangular_self_identifying_at_1000_rows(
    tmp_path: Path,
) -> None:
    _, payload = _projection([f"channel-{index:04d}" for index in range(1_000)])
    rows = payload["rows"]
    assert isinstance(rows, list) and len(rows) == LEGACY_EXPORT_MAX_ROWS
    body = _csv_from_rows(rows)
    detached = tmp_path / "detached-export.csv"
    detached.write_bytes(body.encode("utf-8"))

    with detached.open("r", encoding="utf-8", newline="") as stream:
        records = list(csv.reader(stream))
    assert tuple(records[0]) == CSV_COLUMNS
    assert all(len(record) == len(CSV_COLUMNS) for record in records)
    assert {record[0] for record in records[1:]} == {
        PROJECTION_AUTHORITY_NON_AUTHORITATIVE
    }
    assert {record[1] for record in records[1:]} == {CSV_SCHEMA_VERSION}
    assert detached.stat().st_size <= LEGACY_EXPORT_MAX_BYTES
    print(
        "\nP11_TRACK1_CSV_METRICS="
        + json.dumps(
            {
                "artifact_bytes": detached.stat().st_size,
                "columns": len(CSV_COLUMNS),
                "header_first": True,
                "projection_authority": PROJECTION_AUTHORITY_NON_AUTHORITATIVE,
                "rectangular": True,
                "rows": len(records) - 1,
                "schema_version": CSV_SCHEMA_VERSION,
            },
            sort_keys=True,
        )
    )


def test_csv_and_xlsx_maximum_concurrent_serialization_stays_in_declared_memory() -> (
    None
):
    _, payload = _projection([f"channel-{index:04d}" for index in range(1_000)])
    rows = payload["rows"]
    assert isinstance(rows, list) and len(rows) == LEGACY_EXPORT_MAX_ROWS

    def serialize_pair() -> tuple[int, int]:
        csv_bytes = _csv_from_rows(rows).encode("utf-8")
        xlsx_bytes = _xlsx_from_projection(payload)
        parsed = load_workbook(BytesIO(xlsx_bytes), read_only=True, data_only=False)
        assert parsed.sheetnames == ["Export", "Metadata"]
        return len(csv_bytes), len(xlsx_bytes)

    gc.collect()
    process = psutil.Process()
    baseline_rss = process.memory_info().rss
    rss_samples = [baseline_rss]
    sampling_done = threading.Event()

    def sample_process_rss() -> None:
        while not sampling_done.wait(0.001):
            rss_samples.append(process.memory_info().rss)

    sampler = threading.Thread(target=sample_process_rss, daemon=True)
    sampler.start()
    started = time.perf_counter()
    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=TRACK1_MAX_CONCURRENT_EXPORTS
        ) as executor:
            sizes = list(
                executor.map(
                    lambda _: serialize_pair(), range(TRACK1_MAX_CONCURRENT_EXPORTS)
                )
            )
    finally:
        sampling_done.set()
        sampler.join(timeout=1)
        rss_samples.append(process.memory_info().rss)
    elapsed_ms = (time.perf_counter() - started) * 1_000
    peak_rss = max(rss_samples)
    peak_rss_delta = peak_rss - baseline_rss

    assert all(
        csv_bytes <= LEGACY_EXPORT_MAX_BYTES and xlsx_bytes <= LEGACY_EXPORT_MAX_BYTES
        for csv_bytes, xlsx_bytes in sizes
    )
    assert peak_rss_delta <= (
        TRACK1_MAX_CONCURRENT_EXPORTS * TRACK1_MAX_SERIALIZATION_WORKING_SET_BYTES
    )
    print(
        "\nP11_TRACK1_SERIALIZATION_METRICS="
        + json.dumps(
            {
                "concurrency": TRACK1_MAX_CONCURRENT_EXPORTS,
                "declared_aggregate_working_set_bytes": (
                    TRACK1_MAX_CONCURRENT_EXPORTS
                    * TRACK1_MAX_SERIALIZATION_WORKING_SET_BYTES
                ),
                "elapsed_ms": elapsed_ms,
                "measurement": "psutil.Process.memory_info().rss",
                "baseline_rss_bytes": baseline_rss,
                "peak_rss_bytes": peak_rss,
                "peak_rss_delta_bytes": peak_rss_delta,
                "rows_per_export": len(rows),
                "sizes": [
                    {"csv_bytes": csv_bytes, "xlsx_bytes": xlsx_bytes}
                    for csv_bytes, xlsx_bytes in sizes
                ],
            },
            sort_keys=True,
        )
    )


@pytest.mark.asyncio
async def test_track1_deadline_includes_saturated_admission_queue(monkeypatch) -> None:
    semaphore = asyncio.Semaphore(TRACK1_MAX_CONCURRENT_EXPORTS)
    for _ in range(TRACK1_MAX_CONCURRENT_EXPORTS):
        await semaphore.acquire()
    monkeypatch.setattr(export_api, "_TRACK1_EXPORT_CONCURRENCY_LIMIT", semaphore)
    monkeypatch.setattr(export_api, "TRACK1_HANDLER_DEADLINE_SECONDS", 0.02)

    projection_called = False

    async def forbidden_projection(**_kwargs):
        nonlocal projection_called
        projection_called = True
        raise AssertionError("saturated request reached database work")

    monkeypatch.setattr(export_api, "_projection_for_request", forbidden_projection)
    try:
        with pytest.raises(
            LegacyExportDeadlineExceeded,
            match="legacy_export_handler_deadline_exceeded",
        ):
            await export_api._run_track1_export(
                db_session=object(),
                tenant_id=uuid4(),
                session_scope=None,
                start=date(2026, 8, 1),
                end=date(2026, 8, 31),
                channels=None,
                export_format="csv",
            )
    finally:
        for _ in range(TRACK1_MAX_CONCURRENT_EXPORTS):
            semaphore.release()
    assert projection_called is False


@pytest.mark.asyncio
async def test_timeout_retains_capacity_until_physical_serializer_finishes(
    monkeypatch,
) -> None:
    semaphore = asyncio.Semaphore(TRACK1_MAX_CONCURRENT_EXPORTS)
    monkeypatch.setattr(export_api, "_TRACK1_EXPORT_CONCURRENCY_LIMIT", semaphore)
    monkeypatch.setattr(export_api, "TRACK1_HANDLER_DEADLINE_SECONDS", 0.03)
    export_api._TRACK1_RETAINED_SERIALIZER_TASKS.clear()
    _, payload = _projection(["Meta"])
    rows = payload["rows"]
    assert isinstance(rows, list)

    async def fast_projection(**_kwargs):
        return rows, payload

    real_serializer = _csv_from_rows
    release_physical_work = threading.Event()
    state_lock = threading.Lock()
    active = 0
    peak_active = 0
    starts = 0

    def blocked_production_serializer(value):
        nonlocal active, peak_active, starts
        with state_lock:
            starts += 1
            active += 1
            peak_active = max(peak_active, active)
        try:
            release_physical_work.wait(timeout=2)
            return real_serializer(value)
        finally:
            with state_lock:
                active -= 1

    monkeypatch.setattr(export_api, "_projection_for_request", fast_projection)
    monkeypatch.setattr(export_api, "_csv_from_rows", blocked_production_serializer)

    async def invoke() -> None:
        with pytest.raises(
            LegacyExportDeadlineExceeded,
            match="legacy_export_handler_deadline_exceeded",
        ):
            await export_api._run_track1_export(
                db_session=object(),
                tenant_id=uuid4(),
                session_scope=None,
                start=date(2026, 8, 1),
                end=date(2026, 8, 1),
                channels=None,
                export_format="csv",
                csv_schema_version=CSV_SCHEMA_VERSION,
            )

    await asyncio.gather(invoke(), invoke())
    assert active == peak_active == starts == TRACK1_MAX_CONCURRENT_EXPORTS
    assert semaphore._value == 0
    assert len(export_api._TRACK1_RETAINED_SERIALIZER_TASKS) == 2

    await invoke()
    assert starts == TRACK1_MAX_CONCURRENT_EXPORTS
    assert active == TRACK1_MAX_CONCURRENT_EXPORTS
    assert semaphore._value == 0

    release_physical_work.set()
    for _ in range(100):
        if active == 0 and semaphore._value == TRACK1_MAX_CONCURRENT_EXPORTS:
            break
        await asyncio.sleep(0.01)
    assert active == 0
    assert semaphore._value == TRACK1_MAX_CONCURRENT_EXPORTS
    assert not export_api._TRACK1_RETAINED_SERIALIZER_TASKS
    print(
        "\nP11_TRACK1_TIMEOUT_SERIALIZER_METRICS="
        + json.dumps(
            {
                "active_after_http_timeout": TRACK1_MAX_CONCURRENT_EXPORTS,
                "capacity_after_http_timeout": 0,
                "capacity_after_physical_completion": semaphore._value,
                "peak_physical_serializers": peak_active,
                "third_serializer_started_while_saturated": False,
            },
            sort_keys=True,
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reason_code",
    [
        "legacy_export_database_deadline_exceeded",
        "legacy_export_handler_deadline_exceeded",
    ],
)
async def test_runtime_503_matches_authoritative_openapi_schema(
    monkeypatch, reason_code: str
) -> None:
    app = FastAPI()
    app.include_router(export_api.router, prefix="/api/export")

    async def fake_auth():
        return type("Auth", (), {"tenant_id": uuid4()})()

    async def fake_db():
        yield object()

    async def deadline(**_kwargs):
        raise LegacyExportDeadlineExceeded(reason_code)

    app.dependency_overrides[get_auth_context] = fake_auth
    app.dependency_overrides[get_db_session] = fake_db
    monkeypatch.setattr(export_api, "_run_track1_export", deadline)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(
            "/api/export/csv",
            headers={"X-Correlation-ID": str(uuid4())},
        )

    assert response.status_code == 503
    contract = yaml.safe_load(
        (ROOT / "api-contracts/openapi/v1/export.yaml").read_text(encoding="utf-8")
    )
    schema = contract["components"]["schemas"]["ExportDeadlineError"]
    Draft202012Validator(schema).validate(response.json())
    assert response.json() == {
        "detail": {"status": "refused", "reason_code": reason_code}
    }
