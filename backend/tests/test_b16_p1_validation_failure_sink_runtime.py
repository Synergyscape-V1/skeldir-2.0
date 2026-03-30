from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text

from app.core.identity import SYSTEM_USER_ID
from app.db.session import engine, get_session
from app.models.llm import LLMValidationFailure
from app.services.llm_validation_failures import LLMValidationFailureService


@pytest.mark.asyncio
async def test_b16_p1_validation_failure_sink_runtime_write_path(test_tenant: UUID) -> None:
    service = LLMValidationFailureService()
    request_id = f"b16-p1-validation-failure-{uuid4().hex[:8]}"

    async with get_session(tenant_id=test_tenant, user_id=SYSTEM_USER_ID) as session:
        row_id = await service.record_failure(
            session,
            tenant_id=test_tenant,
            endpoint="app.tasks.llm.investigation",
            validation_error="validation_schema_mismatch",
            request_payload={"request_id": request_id, "prompt": {"q": "test"}},
            response_payload={"output_text": "bad payload"},
        )
        row = (
            await session.execute(
                select(LLMValidationFailure).where(
                    LLMValidationFailure.tenant_id == test_tenant,
                    LLMValidationFailure.id == row_id,
                )
            )
        ).scalars().one()

    assert str(row.id) == str(row_id)
    assert row.endpoint == "app.tasks.llm.investigation"
    assert row.validation_error == "validation_schema_mismatch"


@pytest.mark.asyncio
async def test_b16_p1_validation_failure_sink_app_rw_grant_contract() -> None:
    async with engine.begin() as conn:
        role_exists = bool(
            (
                await conn.execute(
                    text("SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname = 'app_rw')")
                )
            ).scalar_one()
        )
        if not role_exists:
            pytest.skip("app_rw role not present in this runtime")

        grants = (
            await conn.execute(
                text(
                    """
                    SELECT privilege_type
                    FROM information_schema.role_table_grants
                    WHERE table_schema = 'public'
                      AND table_name = 'llm_validation_failures'
                      AND grantee = 'app_rw'
                    """
                )
            )
        ).scalars().all()

    normalized = {str(item).upper() for item in grants}
    assert {"SELECT", "INSERT"}.issubset(normalized)


@pytest.mark.asyncio
async def test_b16_p1_validation_failure_sink_is_tenant_scoped(test_tenant_pair: tuple[UUID, UUID]) -> None:
    tenant_a, tenant_b = test_tenant_pair
    service = LLMValidationFailureService()

    async with get_session(tenant_id=tenant_a, user_id=SYSTEM_USER_ID) as session:
        await service.record_failure(
            session,
            tenant_id=tenant_a,
            endpoint="app.tasks.llm.explanation",
            validation_error="validation_numeric_mismatch",
            request_payload={"request_id": str(uuid4())},
            response_payload={"output_text": "42"},
        )

    async with get_session(tenant_id=tenant_b, user_id=SYSTEM_USER_ID) as session:
        count = await session.execute(select(func.count()).select_from(LLMValidationFailure))

    assert count.scalar_one() == 0
