import logging

from fastapi import APIRouter, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.db.session import engine
from uuid import uuid4

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    checks = {}
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            # Verify RLS policies exist on core tables
            rls_check = await conn.execute(
                text("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'attribution_events'")
            )
            rls_row = rls_check.first()
            if not rls_row or not (rls_row[0] and rls_row[1]):
                raise RuntimeError("RLS not enforced on attribution_events")

            # Ensure tenant context setting works (set_config) and is honored
            tenant_probe = str(uuid4())
            await conn.execute(text("SELECT set_config('app.current_tenant_id', :tid, false)"), {"tid": tenant_probe})
            cur = await conn.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
            current_tid = cur.scalar_one_or_none()
            if current_tid != tenant_probe:
                raise RuntimeError("Tenant context GUC not set correctly")

        checks["database"] = "ok"
        status_code = status.HTTP_200_OK
    except Exception as exc:
        logger.error("readiness_failed", exc_info=True)
        checks["database"] = f"error: {exc}"
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    response.status_code = status_code
    return {"status": "ready" if status_code == status.HTTP_200_OK else "unhealthy", "checks": checks}


@router.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
