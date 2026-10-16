"""B2.6-P2 XXI-P3: index the provider lineage lookup.

The auth root resolves redelivered arrivals to their already-authenticated
lineage with a per-request join over
(public.webhook_ingress_identities JOIN b26_p2_provider_auth_consequence)
filtered on (tenant_id, body_sha256, provider_event_reference) with a
per-candidate-row current-authority predicate and LIMIT 1. The consequence
table carried no index on that filter, so every request scanned the whole
table and evaluated the authority function once per row (for unique
arrivals: every row). Under EG3_4 burst overlap this dominated sidecar DB
time (585 intra-leg holder samples on a 19k-row lane) and drained the
sidecar QueuePool into 503s.

This revision adds a composite btree on
(tenant_id, body_sha256, provider_event_reference) covering
webhook_ingress_identity_id. The query text is untouched: the planner
serves the same predicate from the index (1 row, authority evaluated
once). Downgrade drops the index; the lookup keeps working, slower.
"""

from __future__ import annotations

from alembic import op

revision = "202609300010"
down_revision = "202609300009"


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_p3_lineage_lookup ON
        public.b26_p2_provider_auth_consequence
        (tenant_id, body_sha256, provider_event_reference)
        INCLUDE (webhook_ingress_identity_id)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.ix_p3_lineage_lookup"
    )
