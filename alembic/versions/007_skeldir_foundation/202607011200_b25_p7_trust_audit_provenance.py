"""B2.5-P7 trust provenance audit substrate.

Revision ID: 202607011200
Revises: 202606201430
Create Date: 2026-07-01 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202607011200"
down_revision = "202606201430"
branch_labels = None
depends_on = None


TRUST_AUDIT_TABLES = (
    "trust_access_log",
    "trust_envelope_issuance_log",
    "trust_replay_events",
    "trust_scope_denial_events",
)
RLS_SQL_BY_TABLE = {
    "trust_access_log": (
        "ALTER TABLE public.trust_access_log ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_access_log ON public.trust_access_log",
        """
        CREATE POLICY tenant_isolation_policy_trust_access_log
        ON public.trust_access_log
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "trust_envelope_issuance_log": (
        "ALTER TABLE public.trust_envelope_issuance_log ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_envelope_issuance_log FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_envelope_issuance_log ON public.trust_envelope_issuance_log",
        """
        CREATE POLICY tenant_isolation_policy_trust_envelope_issuance_log
        ON public.trust_envelope_issuance_log
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "trust_replay_events": (
        "ALTER TABLE public.trust_replay_events ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_replay_events FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_replay_events ON public.trust_replay_events",
        """
        CREATE POLICY tenant_isolation_policy_trust_replay_events
        ON public.trust_replay_events
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "trust_scope_denial_events": (
        "ALTER TABLE public.trust_scope_denial_events ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_scope_denial_events FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_scope_denial_events ON public.trust_scope_denial_events",
        """
        CREATE POLICY tenant_isolation_policy_trust_scope_denial_events
        ON public.trust_scope_denial_events
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
}


def _grant_if_role_exists(role: str, statement: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE {statement!r};
            END IF;
        END $$;
        """
    )


def _revoke_if_role_exists(role: str, statement: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE {statement!r};
            END IF;
        END $$;
        """
    )


def _enable_force_rls(table: str) -> None:
    for statement in RLS_SQL_BY_TABLE[table]:
        op.execute(statement)


def _grant_table(table: str) -> None:
    _grant_if_role_exists(
        "app_user",
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.{table} TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        f"GRANT SELECT ON TABLE public.{table} TO app_ro",
    )


def _revoke_table(table: str) -> None:
    for role in ("app_ro", "app_rw", "app_user"):
        _revoke_if_role_exists(
            role,
            f"REVOKE ALL ON TABLE public.{table} FROM {role}",
        )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.trust_access_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            event_type text NOT NULL,
            status text NOT NULL,
            request_identity_hash text NOT NULL,
            idempotency_key_hash text NOT NULL,
            subject_type text NOT NULL,
            subject_ref_hash text,
            envelope_hash text,
            semantic_truth_hash text,
            policy_state text NOT NULL,
            reason_code text,
            audit_ref text NOT NULL,
            audit_hash text NOT NULL,
            evidence_refs_allowed boolean NOT NULL DEFAULT true,
            replay_count integer NOT NULL DEFAULT 0,
            last_replayed_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_trust_access_log_event_type CHECK (
                event_type IN ('issuance', 'refusal', 'scope_denial', 'replay')
            ),
            CONSTRAINT ck_trust_access_log_status CHECK (
                status IN ('success', 'refused', 'degraded', 'replayed')
            ),
            CONSTRAINT ck_trust_access_log_hashes CHECK (
                request_identity_hash ~ '^sha256:[0-9a-f]{64}$'
                AND idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'
                AND audit_hash ~ '^sha256:[0-9a-f]{64}$'
                AND (subject_ref_hash IS NULL OR subject_ref_hash ~ '^sha256:[0-9a-f]{64}$')
                AND (envelope_hash IS NULL OR envelope_hash ~ '^sha256:[0-9a-f]{64}$')
                AND (semantic_truth_hash IS NULL OR semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$')
            ),
            CONSTRAINT ck_trust_access_log_audit_ref CHECK (
                audit_ref ~ '^urn:skeldir:audit:[A-Za-z0-9._:-]+$'
            ),
            CONSTRAINT ck_trust_access_log_refusal_no_evidence CHECK (
                event_type NOT IN ('refusal', 'scope_denial')
                OR evidence_refs_allowed = false
            ),
            CONSTRAINT uq_trust_access_log_idempotency UNIQUE (
                tenant_id, event_type, idempotency_key_hash
            ),
            CONSTRAINT uq_trust_access_log_audit_ref UNIQUE (tenant_id, audit_ref)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.trust_envelope_issuance_log (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            access_audit_ref text NOT NULL,
            idempotency_key_hash text NOT NULL,
            subject_type text NOT NULL,
            subject_ref_hash text NOT NULL,
            envelope_hash text NOT NULL,
            semantic_truth_hash text NOT NULL,
            policy_state text NOT NULL,
            audit_ref text NOT NULL,
            audit_hash text NOT NULL,
            status text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_trust_issuance_status CHECK (status = 'success'),
            CONSTRAINT ck_trust_issuance_hashes CHECK (
                idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'
                AND subject_ref_hash ~ '^sha256:[0-9a-f]{64}$'
                AND envelope_hash ~ '^sha256:[0-9a-f]{64}$'
                AND semantic_truth_hash ~ '^sha256:[0-9a-f]{64}$'
                AND audit_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT uq_trust_issuance_idempotency UNIQUE (
                tenant_id, idempotency_key_hash
            ),
            CONSTRAINT uq_trust_issuance_envelope UNIQUE (tenant_id, envelope_hash)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.trust_replay_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            request_identity_hash text NOT NULL,
            idempotency_key_hash text NOT NULL,
            original_audit_ref text NOT NULL,
            replay_status text NOT NULL,
            audit_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_trust_replay_status CHECK (
                replay_status IN ('idempotent_replay')
            ),
            CONSTRAINT ck_trust_replay_hashes CHECK (
                request_identity_hash ~ '^sha256:[0-9a-f]{64}$'
                AND idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'
                AND audit_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT uq_trust_replay_event UNIQUE (
                tenant_id, idempotency_key_hash, original_audit_ref
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE public.trust_scope_denial_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            request_identity_hash text NOT NULL,
            idempotency_key_hash text NOT NULL,
            subject_type text NOT NULL,
            subject_ref_hash text,
            status text NOT NULL,
            reason_code text NOT NULL,
            evidence_refs_leaked boolean NOT NULL DEFAULT false,
            audit_ref text NOT NULL,
            audit_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_trust_scope_denial_status CHECK (status = 'refused'),
            CONSTRAINT ck_trust_scope_denial_reason CHECK (
                reason_code IN ('scope_denied', 'tenant_mismatch')
            ),
            CONSTRAINT ck_trust_scope_denial_no_evidence_leak CHECK (
                evidence_refs_leaked = false AND subject_ref_hash IS NULL
            ),
            CONSTRAINT ck_trust_scope_denial_hashes CHECK (
                request_identity_hash ~ '^sha256:[0-9a-f]{64}$'
                AND idempotency_key_hash ~ '^sha256:[0-9a-f]{64}$'
                AND audit_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT uq_trust_scope_denial_idempotency UNIQUE (
                tenant_id, idempotency_key_hash
            )
        )
        """
    )

    op.execute(
        """
        CREATE INDEX idx_trust_access_log_subject
            ON public.trust_access_log (tenant_id, subject_type, subject_ref_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_access_log_created
            ON public.trust_access_log (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_issuance_subject
            ON public.trust_envelope_issuance_log (tenant_id, subject_type, subject_ref_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_replay_created
            ON public.trust_replay_events (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_scope_denial_created
            ON public.trust_scope_denial_events (tenant_id, created_at DESC)
        """
    )

    for table in TRUST_AUDIT_TABLES:
        _enable_force_rls(table)
        _grant_table(table)


def downgrade() -> None:
    for table in reversed(TRUST_AUDIT_TABLES):
        _revoke_table(table)
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_policy_{table} ON public.{table}"
        )
    op.execute("DROP INDEX IF EXISTS public.idx_trust_scope_denial_created")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_replay_created")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_issuance_subject")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_access_log_created")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_access_log_subject")
    for table in reversed(TRUST_AUDIT_TABLES):
        op.execute(
            f"DROP TABLE IF EXISTS public.{table}"
        )  # CI:DESTRUCTIVE_OK - rollback removes B2.5-P7 trust audit substrate.
