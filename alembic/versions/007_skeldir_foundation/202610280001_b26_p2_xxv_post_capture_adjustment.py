"""B2.6-P2 XXV post-capture adjustment evidence and attestation.

Creation-event family law is unchanged: only the canonical capture families
create current source authority. A provider refund/chargeback/reversal is a
post-capture adjustment against an already-current verdict. It must not
demote or replace the capture source, and it must carry independent signed
evidence of the adjustment amount and direction.

This revision adds:

* ``b26_p2_adjustment_evidence``: one authenticated provider adjustment
  (provider event identity, parent commerce identity, signed provider bytes
  digest, amount/currency/instant, verdict link).
* ``b26_p2_adjustment_attestation``: the authentication root's signature over
  the adjustment identity, amount, direction and verdict link.
* ``b23_revenue_events.b26_p2_adjustment_evidence_id``: the link the reader
  uses to bind a persisted adjustment to its signed evidence.

The adjustment evidence is deliberately not a ``webhook_ingress_identities``
row: it is not a creation source and must never compete with the capture
source for the current-commerce unique identity.
"""

from __future__ import annotations

from alembic import op


revision = "202610280001"
down_revision = "202610270002"
branch_labels = None
depends_on = None


def _grant(sql: str, role: str) -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
        " THEN %s; END IF; END $$;" % (role, sql % role)
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_adjustment_evidence (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            verdict_id uuid NOT NULL REFERENCES public.b23_match_verdicts(id) ON DELETE CASCADE,
            provider text NOT NULL,
            event_type text NOT NULL CHECK (event_type IN (
                'partial_refund', 'full_refund',
                'chargeback_opened', 'chargeback_won', 'chargeback_lost',
                'reversal'
            )),
            provider_native_event_reference text NOT NULL,
            provider_native_commerce_reference text NOT NULL,
            currency_code character(3) NOT NULL,
            amount_minor integer NOT NULL CHECK (amount_minor >= 0),
            event_timestamp timestamptz NOT NULL,
            body_sha256 character(64) NOT NULL,
            signature_header_sha256 character(64),
            recorded_by text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, provider, provider_native_event_reference)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_b26_p2_adjustment_evidence_verdict"
        " ON public.b26_p2_adjustment_evidence (tenant_id, verdict_id, event_timestamp DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_adjustment_attestation (
            adjustment_evidence_id uuid PRIMARY KEY
                REFERENCES public.b26_p2_adjustment_evidence(id) ON DELETE CASCADE,
            tenant_id uuid NOT NULL,
            statement_version integer NOT NULL,
            attested_amount_minor integer NOT NULL,
            attested_amount_currency character(3) NOT NULL,
            attested_amount_scale integer NOT NULL,
            statement jsonb NOT NULL,
            signature text NOT NULL,
            key_id text NOT NULL,
            key_sha256 text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events"
        " ADD COLUMN IF NOT EXISTS b26_p2_adjustment_evidence_id uuid"
        " REFERENCES public.b26_p2_adjustment_evidence(id) ON DELETE SET NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_b23_revenue_events_adjustment_evidence"
        " ON public.b23_revenue_events (tenant_id, b26_p2_adjustment_evidence_id)"
    )
    for table in (
        "public.b26_p2_adjustment_evidence",
        "public.b26_p2_adjustment_attestation",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")
        op.execute(
            f"DROP POLICY IF EXISTS tenant_isolation_{table.split('.')[-1]} ON {table}"
        )
        op.execute(
            f"CREATE POLICY tenant_isolation_{table.split('.')[-1]} ON {table}"
            " USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
            " WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid)"
        )
    _grant(
        "GRANT INSERT, SELECT ON TABLE public.b26_p2_adjustment_evidence TO %s",
        "app_ingress",
    )
    _grant(
        "GRANT INSERT, SELECT ON TABLE public.b26_p2_adjustment_attestation TO %s",
        "app_ingress",
    )
    for role in ("app_user", "app_worker", "app_trust_issuer", "app_ro", "app_relay"):
        _grant(
            "GRANT SELECT ON TABLE public.b26_p2_adjustment_evidence TO %s",
            role,
        )
    for role in ("app_user", "app_worker", "app_trust_issuer", "app_ro", "app_relay"):
        _grant(
            "GRANT SELECT ON TABLE public.b26_p2_adjustment_attestation TO %s",
            role,
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_current_verdict_for_adjustment(
            p_tenant uuid,
            p_provider text,
            p_parent_commerce_reference text
        )
        RETURNS TABLE (
            verdict_id uuid,
            captured_amount_minor integer,
            currency_code character(3),
            commerce_reference text
        )
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _previous text := current_setting('app.current_tenant_id', true);
        BEGIN
            PERFORM set_config('app.current_tenant_id', p_tenant::text, true);
            RETURN QUERY
            SELECT v.id,
                   v.canonical_captured_gross_amount_minor,
                   v.currency_code,
                   v.provider_native_commerce_reference::text
              FROM public.b23_match_verdicts AS v
             WHERE v.tenant_id = p_tenant
               AND v.provider = lower(p_provider)
               AND (
                   v.provider_native_commerce_reference =
                       p_parent_commerce_reference
                   OR v.canonical_commerce_reference =
                       p_parent_commerce_reference
               )
               AND public.b26_p2_ingress_has_current_authority(
                       v.webhook_ingress_identity_id)
             ORDER BY v.last_transition_at DESC, v.id DESC
             LIMIT 1;
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_previous, ''), true
            );
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_current_verdict_for_adjustment(uuid, text, text)"
        " FROM PUBLIC"
    )
    _grant(
        "GRANT EXECUTE ON FUNCTION"
        " public.b26_p2_current_verdict_for_adjustment(uuid, text, text)"
        " TO %s",
        "app_ingress",
    )
    # XXV/R-0021: a genuine provider replay of the retained signed bytes may
    # lift the one-time pre-XXV demotion after the auth root has written the
    # source attestation. The transition is auth-root-only and checks the
    # signed statement's subject, tenant and amount against the retained row;
    # it is not an owner-writable demotion clear.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_lift_pre_xxv_demotion(
            p_tenant uuid,
            p_ingress uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF session_user <> 'app_ingress' THEN
                RAISE EXCEPTION
                    'b26_p2_lift_pre_xxv_demotion_role_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF NOT EXISTS (
                SELECT 1
                  FROM public.webhook_ingress_identities AS i
                  JOIN public.b26_p2_source_money_attestation AS a
                    ON a.webhook_ingress_identity_id = i.id
                   AND a.tenant_id = i.tenant_id
                 WHERE i.id = p_ingress
                   AND i.tenant_id = p_tenant
                   AND i.b26_p2_demotion_reason =
                       'pre_xxv_source_money_unattestable'
                   AND i.b26_p2_provenance_status = 'authenticated_known'
                   AND a.statement->>'webhook_ingress_identity_id' =
                       i.id::text
                   AND a.statement->>'tenant_id' = i.tenant_id::text
                   AND a.attested_amount_minor = i.verified_amount_minor
                   AND upper(a.attested_amount_currency) =
                       upper(i.verified_amount_currency)
            ) THEN
                RETURN false;
            END IF;
            UPDATE public.webhook_ingress_identities AS i
               SET b26_p2_demotion_reason = NULL
             WHERE i.id = p_ingress
               AND i.tenant_id = p_tenant;
            UPDATE public.b23_match_verdicts AS v
               SET b26_p2_source_authority_state =
                   public.b26_p2_derive_verdict_authority(
                       v.webhook_ingress_identity_id
                   )
             WHERE v.tenant_id = p_tenant
               AND v.webhook_ingress_identity_id = p_ingress;
            RETURN true;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_lift_pre_xxv_demotion(uuid, uuid) FROM PUBLIC"
    )
    _grant(
        "GRANT EXECUTE ON FUNCTION"
        " public.b26_p2_lift_pre_xxv_demotion(uuid, uuid) TO %s",
        "app_ingress",
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_lift_pre_xxv_demotion(uuid, uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_current_verdict_for_adjustment(uuid, text, text)"
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events"
        " DROP COLUMN IF EXISTS b26_p2_adjustment_evidence_id"
    )
    op.execute("DROP TABLE IF EXISTS public.b26_p2_adjustment_attestation")
    op.execute("DROP TABLE IF EXISTS public.b26_p2_adjustment_evidence")
