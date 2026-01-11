"""
Value Trace 02: Constraint enforcement trace.

Asserts bypass attempts fail while the approved builder path succeeds with required columns populated.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.tests.builders.core_builders import build_tenant
from app.db.session import engine

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_02_summary.json")
EVIDENCE_MD = Path("docs/forensics/evidence/value_traces/value_02_constraint_trace.md")


@pytest.mark.asyncio
async def test_value_trace_constraint_guard_blocks_bypass_allows_builder():
    tenant_id = uuid4()
    bypass_failed = False
    builder_succeeded = False
    required_columns = []

    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )
        try:
            # RAW_SQL_ALLOWLIST: intentional bypass attempt for value trace
            await conn.execute(
                text("INSERT INTO tenants (id, name) VALUES (:id, 'Bypass Tenant')"),
                {"id": str(tenant_id)},
            )
        except IntegrityError:
            bypass_failed = True

    tenant_record = await build_tenant()
    if tenant_record.get("tenant_id"):
        builder_succeeded = True

    async with engine.begin() as conn:
        cols = await conn.execute(
            text(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name='tenants' AND is_nullable='NO'
                """
            )
        )
        required_columns = sorted(cols.scalars().all())

    summary = {
        "bypass_failed": bypass_failed,
        "builder_succeeded": builder_succeeded,
        "required_columns": required_columns,
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 02 – Constraint Guard\n\n")
        fh.write(f"- bypass_failed: {bypass_failed}\n")
        fh.write(f"- builder_succeeded: {builder_succeeded}\n")
        fh.write(f"- required_columns: {', '.join(required_columns)}\n")

    assert bypass_failed, "Raw insert without required columns must fail"
    assert builder_succeeded, "Builder path must succeed"
