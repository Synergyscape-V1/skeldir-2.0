"""B2.6-P2 follow-up: tenant RLS conformance for the supersession ledger.

The B0.4 phase-4 probe requires RLS + FORCE RLS + full policy coverage
on every tenant_id-bearing table. The verdict supersession ledger was
owner-custodied without RLS (zero runtime privileges; owner-context
DEFINER readers only). Tenant FORCE RLS is a frozen requirement, and no
exemption is taken: this revision brings the ledger into conformance
without changing any principal's effective access.

The single FOR ALL policy names no role at all (applies to PUBLIC),
following the owner-agnostic law of 202609270003: lanes whose migrations
run under a lane-owner role (R7's r7_admin, R3's r3 owner, ...) create
the ledger and its SECURITY DEFINER trigger owned by that role, and
inside the DEFINER trigger current_user IS the lane owner. A TO
migration_owner clause would apply on canonical lanes only; on every
other lane FORCE RLS with no applicable policy would default-deny the
trigger's own INSERT and break verdict corrections, and worse, Postgres
refuses CREATE POLICY naming a nonexistent role, so the migration
itself fails on lanes without a migration_owner login (R7 R4a).

Runtime roles hold no privileges on the table at all, so they remain
denied exactly as before; before/after effective-privilege probing is
byte-identical (grants stay the authority mechanism, as on every other
table). TRUNCATE is privilege-checked, not RLS-filtered, and remains  # CI:DESTRUCTIVE_OK - prose-only mention; this revision executes no TRUNCATE (CREATE POLICY + ENABLE/FORCE RLS only)
owner-only. The ledger immutability triggers are untouched. The
maintenance trust boundary is unchanged: the owner can still alter its
own table, and that alteration remains detectable only through the beat
observations plus the committed anchor, exactly as documented.

Downgrade removes the policy and disables RLS, restoring the 300005
posture exactly.
"""

from __future__ import annotations

from alembic import op

revision = "202609300006"
down_revision = "202609300005"


def upgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS b26_p2_supersession_ledger_owner_all"
        " ON public.b26_p2_verdict_supersession_ledger"
    )
    op.execute(
        "CREATE POLICY b26_p2_supersession_ledger_owner_all"
        " ON public.b26_p2_verdict_supersession_ledger"
        " FOR ALL USING (true) WITH CHECK (true)"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
        " ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_verdict_supersession_ledger"
        " FORCE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS b26_p2_supersession_ledger_owner_all"
        " ON public.b26_p2_verdict_supersession_ledger"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_verdict_supersession_ledger"
        " NO FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
        " DISABLE ROW LEVEL SECURITY"
    )
