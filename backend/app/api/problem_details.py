from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse


def problem_details_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str,
    correlation_id: UUID,
    type_url: str,
) -> JSONResponse:
    payload = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": str(request.url),
        "correlation_id": str(correlation_id),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
    )
