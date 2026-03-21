from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response, Security
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db_session
from app.security.auth import AuthContext, get_auth_context

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    return start, end


def _csv_from_rows(rows: list[dict[str, object]]) -> str:
    lines = ["date,channel,revenue,conversions,confidence"]
    for row in rows:
        lines.append(
            ",".join(
                [
                    str(row["date"]),
                    str(row["channel"]),
                    f"{float(row['revenue']):.2f}",
                    str(int(row["conversions"])),
                    f"{float(row['confidence']):.2f}",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def _export_payload(
    *,
    start: date,
    end: date,
    rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "generated_at": _utcnow_iso(),
        "date_range": {"start": start.isoformat(), "end": end.isoformat()},
        "data": rows,
    }


async def _fetch_reporting_rows(
    *,
    db_session: AsyncSession,
    tenant_id: UUID,
    session_scope: UUID | None,
    start: date,
    end: date,
    channels: list[str] | None = None,
) -> list[dict[str, object]]:
    start_ts = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_ts = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)
    channel_filter = [value.strip().lower() for value in (channels or []) if value and value.strip()]

    query = text(
        """
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
        JOIN session_authority sa
          ON sa.tenant_id = e.tenant_id
         AND sa.session_id = e.session_id
        WHERE aa.tenant_id = :tenant_id
          AND (
                :session_scope_missing
                OR e.session_id = :session_id
          )
          AND e.occurred_at >= :start_ts
          AND e.occurred_at < :end_ts
          AND sa.invalidated_at IS NULL
          AND sa.expires_at > :authority_now
          AND (
                :channels_is_empty
                OR lower(aa.channel_code) = ANY(CAST(:channels AS text[]))
          )
        GROUP BY export_date, aa.channel_code
        ORDER BY export_date ASC, aa.channel_code ASC
        """
    )
    result = await db_session.execute(
        query,
        {
            "tenant_id": str(tenant_id),
            "session_scope_missing": session_scope is None,
            "session_id": str(session_scope) if session_scope is not None else None,
            "start_ts": start_ts,
            "end_ts": end_ts,
            "authority_now": datetime.now(timezone.utc),
            "channels_is_empty": len(channel_filter) == 0,
            "channels": channel_filter,
        },
    )

    rows: list[dict[str, object]] = []
    for export_date, channel_code, revenue_cents, conversion_count, confidence_score in result.fetchall():
        rows.append(
            {
                "date": export_date.isoformat(),
                "channel": str(channel_code),
                "revenue": float(int(revenue_cents) / 100.0),
                "conversions": int(conversion_count),
                "confidence": float(confidence_score),
            }
        )
    return rows


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
    x_attribution_session_id: Annotated[UUID | None, Header(alias="X-Attribution-Session-ID")] = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    start, end = _resolve_date_range(start_date=start_date, end_date=end_date)
    rows = await _fetch_reporting_rows(
        db_session=db_session,
        tenant_id=auth_context.tenant_id,
        session_scope=x_attribution_session_id,
        start=start,
        end=end,
        channels=channels,
    )
    payload = _export_payload(start=start, end=end, rows=rows)

    normalized_format = export_format.strip().lower()
    if normalized_format == "csv":
        body = _csv_from_rows(rows)
        return Response(
            content=body,
            media_type="text/csv",
            headers={
                "X-Correlation-ID": str(x_correlation_id),
                "Content-Disposition": 'attachment; filename="skeldir-export-revenue.csv"',
            },
        )
    if normalized_format == "xlsx":
        return Response(
            content=b"PK\x03\x04SKELDIR-MOCK-XLSX",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "X-Correlation-ID": str(x_correlation_id),
                "Content-Disposition": 'attachment; filename="skeldir-export-revenue.xlsx"',
            },
        )
    return payload


@router.get("/csv", operation_id="exportCSV")
async def export_csv(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    x_attribution_session_id: Annotated[UUID | None, Header(alias="X-Attribution-Session-ID")] = None,
):
    start, end = _resolve_date_range(start_date=None, end_date=None)
    rows = await _fetch_reporting_rows(
        db_session=db_session,
        tenant_id=auth_context.tenant_id,
        session_scope=x_attribution_session_id,
        start=start,
        end=end,
    )
    return Response(
        content=_csv_from_rows(rows),
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
    x_attribution_session_id: Annotated[UUID | None, Header(alias="X-Attribution-Session-ID")] = None,
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    start, end = _resolve_date_range(start_date=None, end_date=None)
    rows = await _fetch_reporting_rows(
        db_session=db_session,
        tenant_id=auth_context.tenant_id,
        session_scope=x_attribution_session_id,
        start=start,
        end=end,
    )
    return _export_payload(start=start, end=end, rows=rows)


@router.get("/excel", operation_id="exportExcel")
async def export_excel(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
):
    payload = b"PK\x03\x04SKELDIR-MOCK-XLSX"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": 'attachment; filename="skeldir-export.xlsx"',
        },
    )
