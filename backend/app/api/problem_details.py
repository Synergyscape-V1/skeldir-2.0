from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

AUTH_UNAUTHORIZED_CODE = "AUTH_UNAUTHORIZED"
AUTH_FORBIDDEN_CODE = "AUTH_FORBIDDEN"
DEFAULT_PROBLEM_CODE = "UNSPECIFIED_ERROR"


class ValidationErrorItem(BaseModel):
    field: str | None = None
    message: str | None = None
    code: str | None = None


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    correlation_id: UUID
    timestamp: datetime
    code: str
    errors: list[ValidationErrorItem] | None = None


def _default_code_for_status(status_code: int) -> str:
    if status_code == 401:
        return AUTH_UNAUTHORIZED_CODE
    if status_code == 403:
        return AUTH_FORBIDDEN_CODE
    return DEFAULT_PROBLEM_CODE


def problem_details_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    detail: str,
    correlation_id: UUID,
    type_url: str,
    code: str | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    # Use a URI-safe, path-template-independent instance identifier.
    instance_uri = f"urn:skeldir:error:{correlation_id}"
    payload = {
        "type": type_url,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance_uri,
        "correlation_id": str(correlation_id),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "code": code or _default_code_for_status(status_code),
    }
    if errors is not None:
        payload["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
    )
