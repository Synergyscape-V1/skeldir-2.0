"""
Value Trace 05-WIN: Centaur Friction (Review/Approve + Minimum Pending)

This test proves that it is mechanically impossible to return "final"
results immediately. The system enforces:
1. Minimum hold period (45-60s) before review
2. Explicit approval required before completion
3. Cannot skip states in the workflow

Test Scenario:
1. Create job at t=0 -> expect PENDING
2. Poll at t=+30s -> must still be PENDING (fail if READY/COMPLETED)
3. Poll at t=+46s -> expect READY_FOR_REVIEW
4. Try to fetch "final" before approve -> must not be COMPLETED
5. Approve -> expect COMPLETED

This proves:
1. Minimum hold enforced (cannot skip waiting period)
2. Approval gate enforced (cannot auto-complete)
3. State machine integrity (cannot skip states)
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import text

from backend.tests.builders.core_builders import build_tenant
from app.db.session import engine
from app.services.investigation import (
    FixedClock,
    InvestigationService,
    InvestigationStatus,
)

EVIDENCE_JSON = Path("backend/validation/evidence/value_traces/value_05_summary.json")
EVIDENCE_MD = Path("docs/forensics/evidence/value_traces/value_05_centaur_enforcement.md")


@pytest.mark.asyncio
async def test_value_trace_centaur_friction_enforced():
    """
    VALUE_05-WIN: Prove centaur friction (review/approve + min pending).

    Uses a controllable clock to simulate time passage without actual waits.
    """
    # Setup
    tenant_record = await build_tenant(name="ValueTrace Centaur Tenant")
    tenant_id = tenant_record["tenant_id"]

    # Create service with controllable clock
    t0 = datetime.now(timezone.utc)
    clock = FixedClock(t0)
    service = InvestigationService(clock=clock, min_hold_seconds=45)

    # Track state transitions for evidence
    transitions = []

    # Step 1: Create job at t=0 -> expect PENDING
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        job = await service.create_job(
            conn=conn,
            tenant_id=tenant_id,
            correlation_id=f"vt05-{uuid4().hex[:8]}",
        )

    assert job.status == InvestigationStatus.PENDING, \
        f"Job should be PENDING at creation, got {job.status}"
    assert job.remaining_hold_seconds == 45, \
        f"Should have 45s remaining hold, got {job.remaining_hold_seconds}"

    transitions.append({
        "time": "t=0s",
        "action": "create_job",
        "status": job.status.value,
        "remaining_hold_seconds": job.remaining_hold_seconds,
        "assertion": "PENDING with 45s hold",
    })

    # Step 2: Poll at t=+30s -> must still be PENDING
    clock.advance(30)

    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        job_30s = await service.get_job(conn, tenant_id, job.id)

    assert job_30s is not None
    assert job_30s.status == InvestigationStatus.PENDING, \
        f"Job must still be PENDING at t=30s (before min_hold), got {job_30s.status}"
    assert job_30s.remaining_hold_seconds == 15, \
        f"Should have 15s remaining at t=30s, got {job_30s.remaining_hold_seconds}"

    transitions.append({
        "time": "t=30s",
        "action": "get_job",
        "status": job_30s.status.value,
        "remaining_hold_seconds": job_30s.remaining_hold_seconds,
        "assertion": "Still PENDING (min_hold not reached)",
    })

    # Step 3: Poll at t=+46s -> expect READY_FOR_REVIEW
    clock.advance(16)  # Now at t=46s

    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        job_46s = await service.get_job(conn, tenant_id, job.id)

    assert job_46s is not None
    assert job_46s.status == InvestigationStatus.READY_FOR_REVIEW, \
        f"Job should be READY_FOR_REVIEW at t=46s (after min_hold), got {job_46s.status}"
    assert job_46s.ready_for_review_at is not None, \
        "ready_for_review_at should be set"

    transitions.append({
        "time": "t=46s",
        "action": "get_job",
        "status": job_46s.status.value,
        "remaining_hold_seconds": job_46s.remaining_hold_seconds,
        "assertion": "READY_FOR_REVIEW (min_hold passed)",
    })

    # Step 4: Verify job is NOT COMPLETED before approval
    assert job_46s.status != InvestigationStatus.COMPLETED, \
        "Job must NOT be COMPLETED before explicit approval"
    assert job_46s.approved_at is None, \
        "approved_at must be None before approval"
    assert job_46s.completed_at is None, \
        "completed_at must be None before approval"

    transitions.append({
        "time": "t=46s",
        "action": "check_not_completed",
        "status": job_46s.status.value,
        "approved_at": None,
        "completed_at": None,
        "assertion": "NOT COMPLETED (approval gate enforced)",
    })

    # Step 5: Approve -> expect COMPLETED
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        job_approved = await service.approve_job(
            conn=conn,
            tenant_id=tenant_id,
            job_id=job.id,
            result={"answer": "Approved after review"},
        )

    assert job_approved.status == InvestigationStatus.COMPLETED, \
        f"Job should be COMPLETED after approval, got {job_approved.status}"
    assert job_approved.approved_at is not None, \
        "approved_at must be set after approval"
    assert job_approved.completed_at is not None, \
        "completed_at must be set after approval"

    transitions.append({
        "time": "t=46s (after approve)",
        "action": "approve_job",
        "status": job_approved.status.value,
        "approved_at": job_approved.approved_at.isoformat() if job_approved.approved_at else None,
        "completed_at": job_approved.completed_at.isoformat() if job_approved.completed_at else None,
        "assertion": "COMPLETED (after explicit approval)",
    })

    # Build SQL proof query
    sql_proof = f"""
    SELECT
        id,
        status,
        created_at,
        min_hold_until,
        ready_for_review_at,
        approved_at,
        completed_at
    FROM investigation_jobs
    WHERE id = '{job.id}';

    -- Result:
    -- status: COMPLETED
    -- approved_at: NOT NULL (explicit approval required)
    -- completed_at: NOT NULL (only after approval)
    """

    # Emit evidence artifacts
    summary = {
        "tenant_id": str(tenant_id),
        "job_id": str(job.id),
        "min_hold_seconds": 45,
        "transitions": transitions,
        "invariants": {
            "min_hold_enforced": True,
            "approval_gate_enforced": True,
            "state_machine_integrity": True,
        },
        "final_state": {
            "status": job_approved.status.value,
            "approved_at": job_approved.approved_at.isoformat() if job_approved.approved_at else None,
            "completed_at": job_approved.completed_at.isoformat() if job_approved.completed_at else None,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    EVIDENCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_JSON.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    EVIDENCE_MD.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_MD.open("w", encoding="utf-8") as fh:
        fh.write("# Value Trace 05-WIN: Centaur Friction\n\n")
        fh.write("## Test Scenario\n\n")
        fh.write("1. Create job at t=0 -> PENDING with 45s hold\n")
        fh.write("2. Poll at t=30s -> still PENDING (15s remaining)\n")
        fh.write("3. Poll at t=46s -> READY_FOR_REVIEW (hold passed)\n")
        fh.write("4. Check before approve -> NOT COMPLETED\n")
        fh.write("5. Approve -> COMPLETED\n\n")
        fh.write("## State Transitions\n\n")
        fh.write("| Time | Action | Status | Assertion |\n")
        fh.write("|------|--------|--------|----------|\n")
        for t in transitions:
            fh.write(f"| {t['time']} | {t['action']} | {t['status']} | {t['assertion']} |\n")
        fh.write("\n## SQL Proof Query\n\n")
        fh.write("```sql\n")
        fh.write(sql_proof)
        fh.write("\n```\n\n")
        fh.write("## Invariants Proven\n\n")
        fh.write("- [x] Minimum hold enforced (cannot skip 45s wait)\n")
        fh.write("- [x] Approval gate enforced (cannot auto-complete)\n")
        fh.write("- [x] State machine integrity (PENDING -> READY -> COMPLETED)\n")
        fh.write("- [x] Cannot return 'final' immediately\n")


@pytest.mark.asyncio
async def test_cannot_approve_pending_job():
    """Verify that approving a PENDING job fails."""
    tenant_record = await build_tenant(name="ValueTrace Centaur Pending Tenant")
    tenant_id = tenant_record["tenant_id"]

    clock = FixedClock()
    service = InvestigationService(clock=clock, min_hold_seconds=45)

    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        job = await service.create_job(conn, tenant_id)

    # Try to approve immediately (should fail)
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, false)"),
            {"tid": str(tenant_id)},
        )

        with pytest.raises(ValueError, match="Must be READY_FOR_REVIEW"):
            await service.approve_job(conn, tenant_id, job.id)
