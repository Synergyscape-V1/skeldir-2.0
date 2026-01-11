"""
Value Trace 04: Registry-to-Reality matview inventory check.

Compares the view registry against pg_matviews and emits a diff artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from app.matviews.registry import list_names
from app.db.session import engine

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_04_summary.json")
EVIDENCE_MD = Path("docs/forensics/evidence/value_traces/value_04_registry_trace.md")

REGISTRY = list_names()


@pytest.mark.asyncio
async def test_value_trace_registry_matches_pg_matviews():
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT matviewname
                FROM pg_matviews
                ORDER BY matviewname
                """
            )
        )
        matviews = sorted(result.scalars().all())

    registry_sorted = sorted(REGISTRY)
    diff_missing = [m for m in registry_sorted if m not in matviews]
    diff_extra = [m for m in matviews if m not in registry_sorted]

    summary = {
        "registry": registry_sorted,
        "pg_matviews": matviews,
        "diff_missing": diff_missing,
        "diff_extra": diff_extra,
    }
    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 04 – Registry vs pg_matviews\n\n")
        fh.write(f"- registry: {registry_sorted}\n")
        fh.write(f"- pg_matviews: {matviews}\n")
        fh.write(f"- diff_missing: {diff_missing}\n")
        fh.write(f"- diff_extra: {diff_extra}\n")

    assert not diff_missing and not diff_extra, "Registry and pg_matviews must match"
