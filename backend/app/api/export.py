"""Human-authorized, non-authoritative compatibility export routes."""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO, StringIO
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    Security,
    status,
)
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db_session
from app.privacy.output_redaction import (
    find_output_leaks,
    output_forbidden_key_set,
    sanitize_output_payload,
)
from app.security.auth import AuthContext, get_auth_context
from app.trust.export_projection import build_display_projection, project_display_rows


router = APIRouter()

EXPORT_ROW_ALLOWLIST = (
    "date",
    "channel",
    "revenue_minor",
    "revenue_display",
    "conversions",
    "confidence_display",
)
EXPORT_TOP_LEVEL_ALLOWLIST = (
    "projection_authority",
    "projection_schema_version",
    "tenant_id_hash",
    "generated_at",
    "date_range",
    "rows",
)
EXPORT_DATE_RANGE_ALLOWLIST = ("start", "end")
CSV_COLUMNS = ("date", "channel", "revenue", "conversions", "confidence")

LEGACY_EXPORT_MAX_DATE_SPAN_DAYS = 31
LEGACY_EXPORT_MAX_ROWS = 1_000
LEGACY_EXPORT_MAX_BYTES = 1_048_576
LEGACY_EXPORT_MAX_CHANNELS = 32
LEGACY_EXPORT_MAX_CHANNEL_LENGTH = 256
_LEGACY_ROW_BYTE_ESTIMATE = 512
_EXPORT_FORBIDDEN_KEYS = output_forbidden_key_set()


class LegacyExportLimitExceeded(ValueError):
    """Raised before unbounded legacy export work can occur."""


def _resolve_date_range(
    *,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    today = datetime.now(timezone.utc).date()
    start = start_date or today
    end = end_date or start
    if start > end:
        start, end = end, start
    span_days = (end - start).days + 1
    if span_days > LEGACY_EXPORT_MAX_DATE_SPAN_DAYS:
        raise LegacyExportLimitExceeded("legacy_export_date_span_exceeded")
    return start, end


def _admit_legacy_export(
    *,
    start: date,
    end: date,
    channels: list[str] | None,
) -> list[str]:
    """Reject impossible row/byte envelopes before opening the SQL result."""
    normalized = [
        value.strip().lower() for value in (channels or []) if value and value.strip()
    ]
    if len(normalized) > LEGACY_EXPORT_MAX_CHANNELS:
        raise LegacyExportLimitExceeded("legacy_export_channel_count_exceeded")
    if any(len(value) > LEGACY_EXPORT_MAX_CHANNEL_LENGTH for value in normalized):
        raise LegacyExportLimitExceeded("legacy_export_channel_length_exceeded")
    span_days = (end - start).days + 1
    admitted_channel_count = len(normalized) or LEGACY_EXPORT_MAX_CHANNELS
    admitted_rows = span_days * admitted_channel_count
    if admitted_rows > LEGACY_EXPORT_MAX_ROWS:
        raise LegacyExportLimitExceeded("legacy_export_row_admission_exceeded")
    if admitted_rows * _LEGACY_ROW_BYTE_ESTIMATE > LEGACY_EXPORT_MAX_BYTES:
        raise LegacyExportLimitExceeded("legacy_export_byte_admission_exceeded")
    return normalized


def _csv_from_rows(rows: list[dict[str, object]]) -> str:
    stream = StringIO(newline="")
    writer = csv.writer(
        stream, dialect="excel", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n"
    )
    writer.writerow(CSV_COLUMNS)
    for row in rows:
        _enforce_export_row_no_leak(row)
        writer.writerow(
            (
                row["date"],
                row["channel"],
                row["revenue_display"],
                row["conversions"],
                row["confidence_display"],
            )
        )
    rendered = stream.getvalue()
    if len(rendered.encode("utf-8")) > LEGACY_EXPORT_MAX_BYTES:
        raise LegacyExportLimitExceeded("legacy_export_byte_budget_exceeded")
    return rendered


def _xlsx_from_projection(payload: dict[str, object]) -> bytes:
    _enforce_export_payload_no_leak(payload)
    workbook = Workbook(write_only=False)
    worksheet = workbook.active
    worksheet.title = "Export"
    worksheet.append(CSV_COLUMNS)
    rows = payload["rows"]
    if not isinstance(rows, list):
        raise ValueError("export payload rows must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("export payload row must be an object")
        _enforce_export_row_no_leak(row)
        worksheet.append(
            (
                row["date"],
                row["channel"],
                row["revenue_display"],
                row["conversions"],
                row["confidence_display"],
            )
        )

    metadata = workbook.create_sheet("Metadata")
    metadata.append(("projection_authority", payload["projection_authority"]))
    metadata.append(("projection_schema_version", payload["projection_schema_version"]))
    metadata.append(("tenant_id_hash", payload["tenant_id_hash"]))
    metadata.append(("generated_at", payload["generated_at"]))
    date_range = payload["date_range"]
    if not isinstance(date_range, dict):
        raise ValueError("export payload date_range must be an object")
    metadata.append(("date_range_start", date_range["start"]))
    metadata.append(("date_range_end", date_range["end"]))

    stream = BytesIO()
    workbook.save(stream)
    body = stream.getvalue()
    if len(body) > LEGACY_EXPORT_MAX_BYTES:
        raise LegacyExportLimitExceeded("legacy_export_byte_budget_exceeded")
    return body


def _export_payload(
    *,
    tenant_id: UUID,
    start: date,
    end: date,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    payload = build_display_projection(
        tenant_id=tenant_id,
        start=start,
        end=end,
        source_rows=rows,
    )
    _enforce_export_payload_no_leak(payload)
    sanitized = sanitize_output_payload(payload, forbidden_keys=_EXPORT_FORBIDDEN_KEYS)
    if not isinstance(sanitized, dict):
        raise ValueError("sanitized export payload must remain an object")
    return sanitized


def _filter_export_row_fields(row: dict[str, object]) -> dict[str, object]:
    return {key: row[key] for key in EXPORT_ROW_ALLOWLIST}


def _enforce_export_row_no_leak(row: dict[str, object]) -> None:
    if set(row.keys()) != set(EXPORT_ROW_ALLOWLIST):
        raise ValueError("export row contains non-allowlisted keys")
    leaks = find_output_leaks(row, forbidden_keys=_EXPORT_FORBIDDEN_KEYS)
    if leaks:
        raise ValueError(f"export row violates no-leak policy at {', '.join(leaks)}")


def _enforce_export_payload_no_leak(payload: dict[str, object]) -> None:
    if set(payload.keys()) != set(EXPORT_TOP_LEVEL_ALLOWLIST):
        raise ValueError("export payload contains non-allowlisted top-level keys")
    if payload.get("projection_authority") != "non_authoritative_display":
        raise ValueError("export projection authority marker missing")
    date_range = payload.get("date_range")
    if not isinstance(date_range, dict) or set(date_range.keys()) != set(
        EXPORT_DATE_RANGE_ALLOWLIST
    ):
        raise ValueError("export payload date_range contains non-allowlisted keys")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("export payload rows must be a list")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("export payload row must be an object")
        _enforce_export_row_no_leak(row)
    leaks = find_output_leaks(payload, forbidden_keys=_EXPORT_FORBIDDEN_KEYS)
    if leaks:
        raise ValueError(
            f"export payload violates no-leak policy at {', '.join(leaks)}"
        )


async def _fetch_reporting_rows(
    *,
    db_session: AsyncSession,
    tenant_id: UUID,
    session_scope: UUID | None,
    start: date,
    end: date,
    channels: list[str] | None = None,
) -> list[dict[str, object]]:
    channel_filter = _admit_legacy_export(start=start, end=end, channels=channels)
    start_ts = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_ts = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    query_params: dict[str, object] = {
        "tenant_id": str(tenant_id),
        "start_ts": start_ts,
        "end_ts": end_ts,
        "channels_is_empty": len(channel_filter) == 0,
        "channels": channel_filter,
        "row_limit": LEGACY_EXPORT_MAX_ROWS + 1,
    }
    if session_scope is None:
        session_join = ""
        session_predicate = ""
    else:
        session_join = """
            JOIN session_authority sa
              ON sa.tenant_id = e.tenant_id
             AND sa.session_id = e.session_id
        """
        session_predicate = """
              AND e.session_id = :session_id
              AND sa.invalidated_at IS NULL
              AND sa.expires_at > :authority_now
        """
        query_params.update(
            {
                "session_id": str(session_scope),
                "authority_now": datetime.now(timezone.utc),
            }
        )
    query = text(
        f"""
        SELECT
            date_trunc('day', e.occurred_at)::date AS export_date,
            aa.channel_code AS channel_code,
            COALESCE(SUM(aa.allocated_revenue_cents), 0)::bigint AS revenue_cents,
            COUNT(DISTINCT aa.event_id)::bigint AS conversion_count,
            COALESCE(AVG(aa.confidence_score), 0)::numeric AS confidence_score
        FROM attribution_allocations aa
        JOIN attribution_events e
          ON e.id = aa.event_id
         AND e.tenant_id = aa.tenant_id
        {session_join}
        WHERE aa.tenant_id = :tenant_id
          AND e.occurred_at >= :start_ts
          AND e.occurred_at < :end_ts
          {session_predicate}
          AND (
                :channels_is_empty
                OR lower(aa.channel_code) = ANY(CAST(:channels AS text[]))
          )
        GROUP BY export_date, aa.channel_code
        ORDER BY export_date ASC, aa.channel_code ASC
        LIMIT :row_limit
        """
    )
    result = await db_session.execute(query, query_params)
    fetched = result.fetchmany(LEGACY_EXPORT_MAX_ROWS + 1)
    if len(fetched) > LEGACY_EXPORT_MAX_ROWS:
        raise LegacyExportLimitExceeded("legacy_export_row_budget_exceeded")
    source_rows = [
        {
            "export_date": export_date,
            "channel_code": str(channel_code),
            "revenue_cents": int(revenue_cents),
            "conversion_count": int(conversion_count),
            "confidence_score": confidence_score,
        }
        for export_date, channel_code, revenue_cents, conversion_count, confidence_score in fetched
    ]
    rows = [_filter_export_row_fields(row) for row in project_display_rows(source_rows)]
    for row in rows:
        _enforce_export_row_no_leak(row)
    return rows


def _limit_error(exc: LegacyExportLimitExceeded) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail={"status": "refused", "reason_code": str(exc)},
    )


async def _projection_for_request(
    *,
    db_session: AsyncSession,
    tenant_id: UUID,
    session_scope: UUID | None,
    start: date,
    end: date,
    channels: list[str] | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = await _fetch_reporting_rows(
        db_session=db_session,
        tenant_id=tenant_id,
        session_scope=session_scope,
        start=start,
        end=end,
        channels=channels,
    )
    payload = _export_payload(tenant_id=tenant_id, start=start, end=end, rows=rows)
    return rows, payload


@router.get("/revenue", operation_id="exportRevenue")
async def export_revenue(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    export_format: Annotated[str, Query(alias="format")] = "csv",
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    channels: list[str] | None = Query(default=None),
    x_attribution_session_id: Annotated[
        UUID | None, Header(alias="X-Attribution-Session-ID")
    ] = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    try:
        start, end = _resolve_date_range(start_date=start_date, end_date=end_date)
        rows, payload = await _projection_for_request(
            db_session=db_session,
            tenant_id=auth_context.tenant_id,
            session_scope=x_attribution_session_id,
            start=start,
            end=end,
            channels=channels,
        )
        normalized_format = export_format.strip().lower()
        if normalized_format == "csv":
            body: str | bytes = _csv_from_rows(rows)
            media_type = "text/csv"
            filename = "skeldir-export-revenue.csv"
        elif normalized_format == "xlsx":
            body = _xlsx_from_projection(payload)
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            filename = "skeldir-export-revenue.xlsx"
        elif normalized_format == "json":
            return payload
        else:
            raise HTTPException(status_code=400, detail="Unsupported export format.")
    except LegacyExportLimitExceeded as exc:
        raise _limit_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export payload rejected by privacy no-leak boundary.",
        ) from exc
    return Response(
        content=body,
        media_type=media_type,
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.get("/csv", operation_id="exportCSV")
async def export_csv(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    x_attribution_session_id: Annotated[
        UUID | None, Header(alias="X-Attribution-Session-ID")
    ] = None,
):
    try:
        start, end = _resolve_date_range(start_date=None, end_date=None)
        rows, _ = await _projection_for_request(
            db_session=db_session,
            tenant_id=auth_context.tenant_id,
            session_scope=x_attribution_session_id,
            start=start,
            end=end,
        )
        body = _csv_from_rows(rows)
    except LegacyExportLimitExceeded as exc:
        raise _limit_error(exc) from exc
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": 'attachment; filename="skeldir-export.csv"',
        },
    )


@router.get("/json", operation_id="exportJSON")
async def export_json(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    x_attribution_session_id: Annotated[
        UUID | None, Header(alias="X-Attribution-Session-ID")
    ] = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    try:
        start, end = _resolve_date_range(start_date=None, end_date=None)
        _, payload = await _projection_for_request(
            db_session=db_session,
            tenant_id=auth_context.tenant_id,
            session_scope=x_attribution_session_id,
            start=start,
            end=end,
        )
        return payload
    except LegacyExportLimitExceeded as exc:
        raise _limit_error(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export payload rejected by privacy no-leak boundary.",
        ) from exc


@router.get("/excel", operation_id="exportExcel")
async def export_excel(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    try:
        start, end = _resolve_date_range(start_date=None, end_date=None)
        _, payload = await _projection_for_request(
            db_session=db_session,
            tenant_id=auth_context.tenant_id,
            session_scope=None,
            start=start,
            end=end,
        )
        body = _xlsx_from_projection(payload)
    except LegacyExportLimitExceeded as exc:
        raise _limit_error(exc) from exc
    return Response(
        content=body,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": 'attachment; filename="skeldir-export.xlsx"',
        },
    )
