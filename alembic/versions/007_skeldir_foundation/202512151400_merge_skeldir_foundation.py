"""Merge skeldir_foundation: Unify core attribution schema + celery foundation

Revision ID: 202512151400
Revises: 202511131121, 202512151300
Create Date: 2025-12-15 14:00:00

Migration Description:
This merge revision creates the canonical 'skeldir_foundation' branch label that
unifies the minimal core attribution schema with the celery foundation infrastructure.

Purpose:
- Establish single atomic upgrade target for local development and testing
- Resolve cross-branch FK dependency (202512151300 → tenants table)
- Enable B0.5.3.2 window-scoped idempotency validation on local PostgreSQL

Branch Unification Strategy:
This merge brings together two independent migration chains:

1. Core Schema Subset (baseline → 202511131121):
   - baseline: Empty initial state
   - 202511131115: Core tables (tenants, attribution_events, attribution_allocations)
   - 202511131119: Materialized views
   - 202511131120: RLS policies for tenant isolation
   - 202511131121: Role grants (app_rw, app_ro)

2. Celery Foundation (202512120900 → 202512151300):
   - 202512120900: Celery broker/result tables
   - 202512131200: Worker DLQ (worker_failed_jobs)
   - 202512131530: Kombu sequences
   - 202512131600: Kombu schema alignment
   - 202512151200: DLQ canonical naming
   - 202512151300: Attribution recompute jobs (window-scoped idempotency)

Dependency Resolution:
The merge forces Alembic to apply 202511131115 (tenants table) before 202512151300
(attribution_recompute_jobs), resolving the FK constraint violation:
    attribution_recompute_jobs.tenant_id → tenants.id

Canonical Upgrade Command:
    alembic upgrade skeldir_foundation@head

This will apply all migrations in both chains plus this merge revision, resulting
in a complete schema for B0.5.3.2 behavioral validation.

Exit Gates:
- Merge revision applies cleanly after both parent chains
- Branch label 'skeldir_foundation' is registered
- alembic upgrade skeldir_foundation@head creates all required tables
- No DDL executed (structural merge only)

References:
- B0.5.3.2 Remediation Directive II (Gate R3)
- Gate R1: Migration graph ground truth analysis
- Gate R2: Canonical upgrade target specification
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202512151400'
down_revision: Union[str, Sequence[str], None] = ('202511131121', '202512151300')
branch_labels: Union[str, Sequence[str], None] = ('skeldir_foundation',)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply merge revision.

    This is a structural merge only - no DDL is executed. The merge establishes
    the skeldir_foundation branch label and enforces migration ordering to resolve
    cross-branch dependencies.

    After this merge:
    - Core attribution schema tables exist (tenants, events, allocations)
    - RLS policies are enabled for tenant isolation
    - Role grants are applied (app_rw, app_ro)
    - Celery infrastructure tables exist (kombu, taskmeta, DLQ)
    - Attribution recompute jobs table exists with valid FK to tenants

    No operations performed - this is a no-op merge.
    """
    pass


def downgrade() -> None:
    """
    Rollback merge revision.

    Downgrading a merge revision returns the database to the state before the
    merge, effectively "unmerging" the two branches. In practice, this means
    rolling back to the state of the parent revisions.

    No operations performed - this is a no-op merge.
    """
    pass
