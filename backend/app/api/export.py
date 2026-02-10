from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from app.security.auth import AuthContext, get_auth_context

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/revenue", operation_id="exportRevenue")
async def export_revenue(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    now = _utcnow_iso()
    return {
        "generated_at": now,
        "date_range": {"start": "2025-11-25", "end": "2025-11-25"},
        "data": [
            {
                "date": "2025-11-25",
                "channel": "Meta",
                "revenue": 0.0,
                "conversions": 0,
                "confidence": 1.0,
            }
        ],
    }


@router.get("/csv", operation_id="exportCSV")
async def export_csv(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    body = "date,channel,revenue,conversions,confidence\n2025-11-25,Meta,0.00,0,1.00\n"
    return Response(
        content=body,
        media_type="text/csv",
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": 'attachment; filename="skeldir-export-2025-11-26.csv"',
        },
    )


@router.get("/json", operation_id="exportJSON")
async def export_json(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    now = _utcnow_iso()
    return {
        "generated_at": now,
        "date_range": {"start": "2025-11-25", "end": "2025-11-25"},
        "data": [
            {
                "date": "2025-11-25",
                "channel": "Meta",
                "revenue": 0.0,
                "conversions": 0,
                "confidence": 1.0,
            }
        ],
    }


@router.get("/excel", operation_id="exportExcel")
async def export_excel(
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    payload = b"PK\x03\x04SKELDIR-MOCK-XLSX"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "X-Correlation-ID": str(x_correlation_id),
            "Content-Disposition": 'attachment; filename="skeldir-export-2025-11-26.xlsx"',
        },
    )
