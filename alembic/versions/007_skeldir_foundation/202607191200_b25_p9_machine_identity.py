"""B2.5-P9 machine-caller identity, scopes, replay, and rate-limit substrate.

Revision ID: 202607191200
Revises: 202607011200
Create Date: 2026-07-19 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202607191200"
down_revision = "202607011200"
branch_labels = None
depends_on = None


P9_TABLES = (
    "agent_clients",
    "agent_service_credentials",
    "agent_scope_grants",
    "agent_token_revocations",
    "trust_request_nonces",
    "trust_rate_limit_state",
)

# Scopes permitted under Design Partner Mode. B5.2 action scopes are physically
# banned from issuance by the ck_agent_scope_grants_scope_value CHECK constraint
# and the trust_action_scope_insert_reject trigger below.
DESIGN_PARTNER_SCOPES = (
    "trust.envelope.read",
    "trust.envelope.verify",
    "trust.audit.read",
    "trust.keys.read",
)

RESERVED_ACTION_SCOPES = (
    "trust.action.propose",
    "trust.action.execute",
    "trust.action.approve",
    "trust.action.reject",
    "auto_executable_within_policy",
)

RLS_SQL_BY_TABLE = {
    "agent_clients": (
        "ALTER TABLE public.agent_clients ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.agent_clients FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_agent_clients ON public.agent_clients",
        """
        CREATE POLICY tenant_isolation_policy_agent_clients
        ON public.agent_clients
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "agent_service_credentials": (
        "ALTER TABLE public.agent_service_credentials ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.agent_service_credentials FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_agent_service_credentials ON public.agent_service_credentials",
        """
        CREATE POLICY tenant_isolation_policy_agent_service_credentials
        ON public.agent_service_credentials
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "agent_scope_grants": (
        "ALTER TABLE public.agent_scope_grants ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.agent_scope_grants FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_agent_scope_grants ON public.agent_scope_grants",
        """
        CREATE POLICY tenant_isolation_policy_agent_scope_grants
        ON public.agent_scope_grants
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "agent_token_revocations": (
        "ALTER TABLE public.agent_token_revocations ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.agent_token_revocations FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_agent_token_revocations ON public.agent_token_revocations",
        """
        CREATE POLICY tenant_isolation_policy_agent_token_revocations
        ON public.agent_token_revocations
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "trust_request_nonces": (
        "ALTER TABLE public.trust_request_nonces ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_request_nonces FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_request_nonces ON public.trust_request_nonces",
        """
        CREATE POLICY tenant_isolation_policy_trust_request_nonces
        ON public.trust_request_nonces
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """,
    ),
    "trust_rate_limit_state": (
        "ALTER TABLE public.trust_rate_limit_state ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE public.trust_rate_limit_state FORCE ROW LEVEL SECURITY",
        "DROP POLICY IF EXISTS tenant_isolation_policy_trust_rate_limit_state ON public.trust_rate_limit_state",
        """
        CREATE POLICY tenant_isolation_policy_trust_rate_limit_state
        ON public.trust_rate_limit_state
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
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.{table} TO app_rw",
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
    # --- agent_clients --------------------------------------------------------
    op.execute(
        """
        CREATE TABLE public.agent_clients (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            client_name text NOT NULL,
            client_display_hash text NOT NULL,
            audience text NOT NULL,
            status text NOT NULL DEFAULT 'active',
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz,
            CONSTRAINT ck_agent_clients_status CHECK (status IN ('active', 'revoked', 'suspended')),
            CONSTRAINT ck_agent_clients_audience_not_empty CHECK (length(btrim(audience)) > 0),
            CONSTRAINT ck_agent_clients_display_hash CHECK (
                client_display_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT uq_agent_clients_tenant_name UNIQUE (tenant_id, client_name)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_agent_clients_tenant_status
            ON public.agent_clients (tenant_id, status, created_at DESC)
        """
    )

    # --- agent_service_credentials -------------------------------------------
    # CSPRNG-generated plaintext machine tokens are hashed-at-rest with SHA-256.
    # The first 8 chars of the plaintext are stored as token_prefix to enable
    # O(1) index lookup without exposing the secret. Bcrypt/argon2 are BANNED
    # for machine tokens (high-entropy => slow KDFs become CPU-exhaustion DoS
    # vectors and timing oracles). See H-P9-02.
    op.execute(
        """
        CREATE TABLE public.agent_service_credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL REFERENCES public.agent_clients(id) ON DELETE CASCADE,
            token_prefix text NOT NULL,
            token_hash text NOT NULL,
            hash_algorithm text NOT NULL DEFAULT 'sha256',
            status text NOT NULL DEFAULT 'active',
            issued_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz,
            revoked_at timestamptz,
            CONSTRAINT ck_agent_service_credentials_status CHECK (status IN ('active', 'revoked', 'expired')),
            CONSTRAINT ck_agent_service_credentials_hash_algorithm CHECK (
                hash_algorithm = 'sha256'
            ),
            CONSTRAINT ck_agent_service_credentials_prefix_len CHECK (
                length(token_prefix) = 8
            ),
            CONSTRAINT ck_agent_service_credentials_token_hash CHECK (
                token_hash ~ '^[0-9a-f]{64}$'
            ),
            CONSTRAINT uq_agent_service_credentials_prefix UNIQUE (tenant_id, token_prefix)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_agent_service_credentials_lookup
            ON public.agent_service_credentials (tenant_id, token_prefix, status)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_agent_service_credentials_client
            ON public.agent_service_credentials (tenant_id, agent_client_id, issued_at DESC)
        """
    )

    # --- agent_scope_grants ---------------------------------------------------
    # Governed scope registry. B5.2 action scopes are physically un-issuable at
    # the DB level via a CHECK constraint AND a trigger (defense in depth).
    # See H-P9-06 and Remediation D.
    op.execute(
        """
        CREATE TABLE public.agent_scope_grants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL REFERENCES public.agent_clients(id) ON DELETE CASCADE,
            scope_value text NOT NULL,
            granted_at timestamptz NOT NULL DEFAULT now(),
            revoked_at timestamptz,
            CONSTRAINT ck_agent_scope_grants_scope_value CHECK (
                scope_value IN (
                    'trust.envelope.read',
                    'trust.envelope.verify',
                    'trust.audit.read',
                    'trust.keys.read'
                )
                AND scope_value NOT IN (
                    'trust.action.propose',
                    'trust.action.execute',
                    'trust.action.approve',
                    'trust.action.reject',
                    'auto_executable_within_policy'
                )
            ),
            CONSTRAINT uq_agent_scope_grants_client_scope
                UNIQUE (tenant_id, agent_client_id, scope_value)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_agent_scope_grants_lookup
            ON public.agent_scope_grants (tenant_id, agent_client_id, scope_value)
        """
    )
    # Defense-in-depth trigger: reject reserved action scopes even if a future
    # migration weakens the CHECK constraint. The trigger fires before the
    # constraint and raises a typed exception.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.reject_reserved_trust_action_scope()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.scope_value IN (
                'trust.action.propose',
                'trust.action.execute',
                'trust.action.approve',
                'trust.action.reject',
                'auto_executable_within_policy'
            ) THEN
                RAISE EXCEPTION 'reserved_trust_action_scope_rejected:%', NEW.scope_value
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_agent_scope_grants_reject_reserved
        BEFORE INSERT OR UPDATE OF scope_value ON public.agent_scope_grants
        FOR EACH ROW
        EXECUTE FUNCTION public.reject_reserved_trust_action_scope()
        """
    )

    # --- agent_token_revocations ----------------------------------------------
    op.execute(
        """
        CREATE TABLE public.agent_token_revocations (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL REFERENCES public.agent_clients(id) ON DELETE CASCADE,
            token_prefix text NOT NULL,
            reason_code text NOT NULL,
            revoked_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_agent_token_revocations_prefix_len CHECK (
                length(token_prefix) = 8
            ),
            CONSTRAINT uq_agent_token_revocations_prefix UNIQUE (tenant_id, token_prefix)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_agent_token_revocations_lookup
            ON public.agent_token_revocations (tenant_id, token_prefix)
        """
    )

    # --- trust_request_nonces -------------------------------------------------
    # Anti-TOCTOU replay protection. The UNIQUE constraint makes insertion the
    # atomic primitive: INSERT ... ON CONFLICT DO NOTHING; if rowcount == 0,
    # the request is a replay. This eliminates the exists()->insert() race that
    # allows 50 parallel requests to pass the exists check before the first
    # commit. See H-P9-03 and Remediation B.
    op.execute(
        """
        CREATE TABLE public.trust_request_nonces (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL REFERENCES public.agent_clients(id) ON DELETE CASCADE,
            nonce_value text NOT NULL,
            request_identity_hash text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL,
            CONSTRAINT ck_trust_request_nonces_hashes CHECK (
                request_identity_hash ~ '^sha256:[0-9a-f]{64}$'
            ),
            CONSTRAINT ck_trust_request_nonces_nonce_not_empty CHECK (
                length(btrim(nonce_value)) > 0
            ),
            CONSTRAINT uq_trust_request_nonces_tenant_nonce
                UNIQUE (tenant_id, nonce_value)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_request_nonces_tenant_expires
            ON public.trust_request_nonces (tenant_id, expires_at)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_request_nonces_tenant_created
            ON public.trust_request_nonces (tenant_id, created_at DESC)
        """
    )

    # --- trust_rate_limit_state ----------------------------------------------
    # Skeleton rate-limit ledger. Tracks request counts per agent_client_id over
    # a rolling window. The middleware fails closed with rate_limited when the
    # budget is exceeded. This is a skeleton (not a token-bucket/LRU) per the
    # directive; the full policy engine belongs to a later phase.
    op.execute(
        """
        CREATE TABLE public.trust_rate_limit_state (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            agent_client_id uuid NOT NULL REFERENCES public.agent_clients(id) ON DELETE CASCADE,
            window_started_at timestamptz NOT NULL,
            window_ended_at timestamptz NOT NULL,
            request_count integer NOT NULL DEFAULT 0,
            request_limit integer NOT NULL,
            last_request_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_trust_rate_limit_state_non_negative CHECK (
                request_count >= 0 AND request_limit > 0
            ),
            CONSTRAINT uq_trust_rate_limit_state_client_window
                UNIQUE (tenant_id, agent_client_id, window_started_at, window_ended_at)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_trust_rate_limit_state_lookup
            ON public.trust_rate_limit_state (tenant_id, agent_client_id, window_ended_at)
        """
    )

    for table in P9_TABLES:
        _enable_force_rls(table)
        _grant_table(table)


def downgrade() -> None:
    for table in reversed(P9_TABLES):
        _revoke_table(table)
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_policy_{table} ON public.{table}"
        )
    op.execute("DROP INDEX IF EXISTS public.idx_trust_rate_limit_state_lookup")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_request_nonces_tenant_created")
    op.execute("DROP INDEX IF EXISTS public.idx_trust_request_nonces_tenant_expires")
    op.execute("DROP INDEX IF EXISTS public.idx_agent_token_revocations_lookup")
    op.execute("DROP INDEX IF EXISTS public.idx_agent_scope_grants_lookup")
    op.execute("DROP INDEX IF EXISTS public.idx_agent_service_credentials_client")
    op.execute("DROP INDEX IF EXISTS public.idx_agent_service_credentials_lookup")
    op.execute("DROP INDEX IF EXISTS public.idx_agent_clients_tenant_status")
    op.execute("DROP TRIGGER IF EXISTS trg_agent_scope_grants_reject_reserved ON public.agent_scope_grants")
    op.execute("DROP FUNCTION IF EXISTS public.reject_reserved_trust_action_scope()")
    for table in reversed(P9_TABLES):
        op.execute(f"DROP TABLE IF EXISTS public.{table}")  # CI:DESTRUCTIVE_OK - rollback removes B2.5-P9 machine identity substrate.