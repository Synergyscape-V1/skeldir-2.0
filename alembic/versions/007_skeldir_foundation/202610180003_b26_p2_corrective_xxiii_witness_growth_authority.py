"""B2.6-P2 Corrective XXIII: witness growth, universe binding, money authority.

Revision ID: 202610180003
Revises: 202610180002

Closes the XXIII falsifiers:

* the signed history witness accepts lawful ledger growth (anchored to the
  exact previous tip) instead of refusing every append as a prefix
  divergence;
* every checkpoint is bound to one database-minted authority universe and
  the observer reads state, prefix, violations, and universe in one
  snapshot;
* source-money conservation refuses a verdict whose source ingress (or the
  first ledger predecessor source) is missing instead of skipping it;
* the B2.3 worker may not author verdict money: an update must continue the
  authenticated source or a bound gross-capture correction event, and the
  net must be the deterministic recomputation.
"""

from __future__ import annotations

from alembic import op

revision = "202610180003"
down_revision = "202610180002"
branch_labels = None
depends_on = None


def _grant_execute(function: str, roles: tuple[str, ...]) -> None:
    for role in roles:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'GRANT EXECUTE ON"
            " FUNCTION public.%s TO %s'; END IF; END $$;"
            % (role, function, role)
        )


def _revoke_execute(function: str) -> None:
    op.execute("REVOKE ALL ON FUNCTION public.%s FROM PUBLIC" % function)


def upgrade() -> None:
    # ------------------------------------------------------------------
    # XXIII-1. Authority universe. A UUID minted once per database cluster
    # and readable only through a DEFINER surface. Cloned databases mint a
    # different universe, so a checkpoint signed for one deployment cannot
    # be replayed as evidence for another.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_authority_universe (
            id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
            universe uuid NOT NULL DEFAULT gen_random_uuid(),
            created_at timestamptz NOT NULL DEFAULT clock_timestamp()
        )
        """
    )
    op.execute(
        "INSERT INTO public.b26_p2_authority_universe (id)"
        " VALUES (1) ON CONFLICT (id) DO NOTHING"
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_authority_universe FROM PUBLIC"
    )
    for role in (
        "app_user",
        "app_worker",
        "app_beat",
        "app_trust_issuer",
        "app_trust_signer",
        "app_ingress",
        "app_relay",
    ):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'REVOKE ALL ON TABLE"
            " public.b26_p2_authority_universe FROM %s'; END IF; END $$;"
            % (role, role)
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_authority_universe()
        RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$ SELECT universe FROM public.b26_p2_authority_universe
              WHERE id = 1 $$
        """
    )
    _revoke_execute("b26_p2_authority_universe()")
    _grant_execute(
        "b26_p2_authority_universe()",
        ("app_user", "app_worker", "app_beat", "app_trust_issuer"),
    )

    # ------------------------------------------------------------------
    # XXIII-2. One coherent history snapshot. State, prefix digest,
    # violations, universe, and the previous anchor entry are read under a
    # single statement snapshot; separate READ COMMITTED reads can
    # interleave with a lawful append and manufacture a false divergence.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_snapshot(
            p_prior_tip_seq bigint DEFAULT NULL
        )
        RETURNS TABLE (
            n bigint,
            tip_seq bigint,
            tip_hash text,
            prefix_digest text,
            violations text,
            authority_universe uuid,
            prior_tip_hash text
        )
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
            SELECT state.n,
                   state.tip_seq,
                   state.tip_hash,
                   public.b26_p2_read_history_prefix_digest(),
                   public.b26_p2_read_history_violations(),
                   public.b26_p2_authority_universe(),
                   CASE
                       WHEN p_prior_tip_seq IS NULL THEN NULL
                       ELSE public.b26_p2_read_history_entry_hash(
                           p_prior_tip_seq)
                   END
              FROM public.b26_p2_read_history_witness_state() AS state
        $$
        """
    )
    _revoke_execute("b26_p2_read_history_snapshot(bigint)")
    _grant_execute(
        "b26_p2_read_history_snapshot(bigint)",
        ("app_user", "app_worker", "app_beat", "app_trust_issuer"),
    )

    # ------------------------------------------------------------------
    # XXIII-3. Continuity is the hash chain, not sequence contiguity.
    # BIGSERIAL values are consumed by rolled-back transactions, so a gap
    # is not evidence of tampering (and must not poison the observer).
    # The chain still catches middle-row deletion, reordering, and a
    # deleted genesis (the first surviving row would carry a predecessor
    # hash). Suffix deletion is caught by the signed checkpoint count/tip.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_verify_history_continuity()
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.entry_hash IS NULL
                    OR l.entry_hash !~ '^[0-9a-f]{64}$'
            ) THEN
                violation := 'supersession_chain_unchained_row';
                RETURN NEXT;
            END IF;
            IF EXISTS (
                WITH ordered AS (
                    SELECT l.seq,
                           l.prev_entry_hash,
                           lag(l.entry_hash) OVER (ORDER BY l.seq) AS prior
                      FROM public.b26_p2_verdict_supersession_ledger AS l
                )
                SELECT 1 FROM ordered
                 WHERE (prior IS NULL AND prev_entry_hash IS NOT NULL)
                    OR (prior IS NOT NULL
                        AND prev_entry_hash IS DISTINCT FROM prior)
            ) THEN
                violation := 'supersession_chain_broken';
                RETURN NEXT;
            END IF;
            RETURN;
        END $$;
        """
    )
    _revoke_execute("b26_p2_verify_history_continuity()")

    # ------------------------------------------------------------------
    # XXIII-4. Conservation refuses missing source authority. The XXII
    # function skipped every check when both the verdict source and the
    # first ledger predecessor source were NULL, so a fully invented but
    # internally coherent 99,999 world passed.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b26_p2_verify_source_money_conservation(
                p_tenant_id uuid,
                p_verdict_id uuid
            )
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _ingress uuid;
            _verified integer;
            _attributed integer;
            _row record;
            _prev record;
            _first record;
            _ingress_amount integer;
            _count bigint;
        BEGIN
            SELECT v.webhook_ingress_identity_id,
                   v.verified_amount_minor,
                   v.attributed_amount_minor
              INTO _ingress, _verified, _attributed
              FROM public.b23_match_verdicts AS v
             WHERE v.tenant_id = p_tenant_id
               AND v.id = p_verdict_id;
            IF NOT FOUND THEN
                violation := 'conservation_verdict_missing';
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT count(*) INTO _count
              FROM public.b26_p2_verdict_supersession_ledger AS l
             WHERE l.tenant_id = p_tenant_id
               AND l.verdict_id = p_verdict_id;

            IF _count = 0 THEN
                IF _ingress IS NULL THEN
                    IF _verified IS DISTINCT FROM 0
                       OR _attributed IS DISTINCT FROM 0 THEN
                        violation :=
                            'conservation_source_ingress_missing';
                        RETURN NEXT;
                    END IF;
                    RETURN;
                END IF;
                SELECT i.verified_amount_minor INTO _ingress_amount
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = p_tenant_id;
                IF NOT FOUND THEN
                    violation := 'conservation_source_unresolved';
                    RETURN NEXT;
                    RETURN;
                END IF;
                IF _verified IS DISTINCT FROM _ingress_amount THEN
                    -- A gross-capture correction may bind a provider
                    -- event whose authenticated ingress carries the new
                    -- amount. Nothing else may diverge from the source.
                    IF NOT EXISTS (
                        SELECT 1
                          FROM public.b23_revenue_events AS e
                          JOIN public.webhook_ingress_identities AS i
                            ON i.tenant_id = e.tenant_id
                           AND i.provider = e.provider
                           AND i.provider_native_event_reference =
                               e.provider_native_event_reference
                         WHERE e.tenant_id = p_tenant_id
                           AND e.match_verdict_id = p_verdict_id
                           AND e.is_gross_capture_correction = true
                           AND e.captured_amount_minor = _verified
                           AND i.verified_amount_minor = _verified
                           AND public.b26_p2_ingress_has_current_authority(
                                   i.id)
                    ) THEN
                        violation := 'conservation_source_amount_diverged';
                        RETURN NEXT;
                    END IF;
                END IF;
                RETURN;
            END IF;

            IF _ingress IS NULL THEN
                violation := 'conservation_source_ingress_missing';
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT l.* INTO _first
              FROM public.b26_p2_verdict_supersession_ledger AS l
             WHERE l.tenant_id = p_tenant_id
               AND l.verdict_id = p_verdict_id
             ORDER BY l.seq ASC
             LIMIT 1;

            IF _first.prior_source_ingress IS NULL THEN
                violation := 'conservation_first_prior_source_missing';
                RETURN NEXT;
                RETURN;
            END IF;

            SELECT i.verified_amount_minor INTO _ingress_amount
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = _first.prior_source_ingress
               AND i.tenant_id = p_tenant_id;
            IF NOT FOUND THEN
                violation := 'conservation_source_unresolved';
                RETURN NEXT;
                RETURN;
            END IF;
            IF _first.prior_verified_amount_minor
                   IS DISTINCT FROM _ingress_amount THEN
                violation := 'conservation_first_prior_not_source';
                RETURN NEXT;
            END IF;

            _prev := NULL;
            FOR _row IN
                SELECT l.*
                  FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.tenant_id = p_tenant_id
                   AND l.verdict_id = p_verdict_id
                 ORDER BY l.seq ASC
            LOOP
                IF _prev IS NOT NULL THEN
                    IF _row.prior_verified_amount_minor
                           IS DISTINCT FROM _prev.new_verified_amount_minor
                       OR _row.prior_attributed_amount_minor
                           IS DISTINCT FROM _prev.new_attributed_amount_minor
                       OR _row.prior_source_ingress
                           IS DISTINCT FROM _prev.new_source_ingress THEN
                        violation := 'conservation_chain_discontinuous';
                        RETURN NEXT;
                    END IF;
                END IF;
                _prev := _row;
            END LOOP;

            IF _prev.new_verified_amount_minor IS DISTINCT FROM _verified
               OR _prev.new_attributed_amount_minor IS DISTINCT FROM _attributed
               OR _prev.new_source_ingress IS DISTINCT FROM _ingress THEN
                violation := 'conservation_ledger_not_current';
                RETURN NEXT;
            END IF;

            SELECT i.verified_amount_minor INTO _ingress_amount
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = _ingress
               AND i.tenant_id = p_tenant_id;
            IF NOT FOUND THEN
                violation := 'conservation_source_unresolved';
                RETURN NEXT;
                RETURN;
            END IF;
            IF _verified IS DISTINCT FROM _ingress_amount THEN
                IF NOT EXISTS (
                    SELECT 1
                      FROM public.b23_revenue_events AS e
                      JOIN public.webhook_ingress_identities AS i
                        ON i.tenant_id = e.tenant_id
                       AND i.provider = e.provider
                       AND i.provider_native_event_reference =
                           e.provider_native_event_reference
                     WHERE e.tenant_id = p_tenant_id
                       AND e.match_verdict_id = p_verdict_id
                       AND e.is_gross_capture_correction = true
                       AND e.captured_amount_minor = _verified
                       AND i.verified_amount_minor = _verified
                       AND public.b26_p2_ingress_has_current_authority(i.id)
                ) THEN
                    violation := 'conservation_source_amount_diverged';
                    RETURN NEXT;
                END IF;
            END IF;
            RETURN;
        END $$;
        """
    )
    _revoke_execute(
        "b26_p2_verify_source_money_conservation(uuid, uuid)"
    )
    _grant_execute(
        "b26_p2_verify_source_money_conservation(uuid, uuid)",
        ("app_user", "app_trust_issuer"),
    )

    # ------------------------------------------------------------------
    # XXIII-4. Verdict money authority. The B2.3 worker may persist only
    # money that continues an authenticated source, or (capture
    # corrections) a gross-capture event bound to an authenticated
    # ingress. The net must be the deterministic recomputation. This
    # closes the arbitrary 99,999 update that also forged a supersession
    # ledger row.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b26_p2_enforce_verdict_money_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _money_changed boolean;
            _attribution_changed boolean;
            _verified_changed boolean;
            _net_changed boolean;
            _attribution_amount integer;
            _source_amount integer;
            _source_ok boolean := false;
            _net integer;
            _owner oid;
        BEGIN
            IF session_user = 'postgres'
               OR pg_catalog.pg_has_role(
                      session_user, 'migration_owner', 'USAGE') THEN
                RETURN NEW;
            END IF;
            SELECT relowner INTO _owner
              FROM pg_catalog.pg_class
             WHERE oid = TG_RELID;
            IF _owner IS NOT NULL
               AND pg_catalog.pg_has_role(session_user, _owner, 'USAGE') THEN
                RETURN NEW;
            END IF;
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION
                    'b26_p2_verdict_money_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                _money_changed :=
                    OLD.attributed_amount_minor
                        IS DISTINCT FROM NEW.attributed_amount_minor
                    OR OLD.verified_amount_minor
                        IS DISTINCT FROM NEW.verified_amount_minor
                    OR OLD.canonical_expected_gross_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_expected_gross_amount_minor
                    OR OLD.canonical_captured_gross_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_captured_gross_amount_minor
                    OR OLD.canonical_net_verified_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_net_verified_amount_minor;
                _attribution_changed :=
                    OLD.attributed_amount_minor
                        IS DISTINCT FROM NEW.attributed_amount_minor
                    OR OLD.canonical_expected_gross_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_expected_gross_amount_minor;
                _verified_changed :=
                    OLD.verified_amount_minor
                        IS DISTINCT FROM NEW.verified_amount_minor
                    OR OLD.canonical_captured_gross_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_captured_gross_amount_minor;
                _net_changed :=
                    OLD.canonical_net_verified_amount_minor
                        IS DISTINCT FROM
                           NEW.canonical_net_verified_amount_minor;
            ELSE
                _money_changed :=
                    COALESCE(NEW.attributed_amount_minor, 0) <> 0
                    OR COALESCE(NEW.canonical_expected_gross_amount_minor, 0)
                        <> 0
                    OR COALESCE(NEW.verified_amount_minor, 0) <> 0
                    OR COALESCE(NEW.canonical_captured_gross_amount_minor, 0)
                        <> 0
                    OR COALESCE(NEW.canonical_net_verified_amount_minor, 0)
                        <> 0;
                _attribution_changed :=
                    COALESCE(NEW.attributed_amount_minor, 0) <> 0
                    OR COALESCE(NEW.canonical_expected_gross_amount_minor, 0)
                        <> 0;
                _verified_changed :=
                    COALESCE(NEW.verified_amount_minor, 0) <> 0
                    OR COALESCE(NEW.canonical_captured_gross_amount_minor, 0)
                        <> 0;
                _net_changed :=
                    COALESCE(NEW.canonical_net_verified_amount_minor, 0) <> 0;
            END IF;
            IF NOT _money_changed THEN
                RETURN NEW;
            END IF;

            IF NEW.canonical_captured_gross_amount_minor
                   IS DISTINCT FROM NEW.verified_amount_minor THEN
                RAISE EXCEPTION
                    'b26_p2_verdict_money_authority_refused:'
                    'captured_verified_diverged'
                    USING ERRCODE = '42501';
            END IF;

            IF _attribution_changed THEN
                IF NEW.attribution_event_id IS NULL THEN
                    RAISE EXCEPTION
                        'b26_p2_verdict_money_authority_refused:'
                        'attribution_source_missing'
                        USING ERRCODE = '42501';
                END IF;
                SELECT COALESCE(ae.conversion_value_cents,
                                ae.revenue_cents, 0)
                  INTO _attribution_amount
                  FROM public.attribution_events AS ae
                 WHERE ae.id = NEW.attribution_event_id
                   AND ae.tenant_id = NEW.tenant_id;
                IF NOT FOUND THEN
                    RAISE EXCEPTION
                        'b26_p2_verdict_money_authority_refused:'
                        'attribution_source_unresolved'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.attributed_amount_minor
                       IS DISTINCT FROM _attribution_amount
                   OR NEW.canonical_expected_gross_amount_minor
                       IS DISTINCT FROM _attribution_amount THEN
                    RAISE EXCEPTION
                        'b26_p2_verdict_money_authority_refused:'
                        'attribution_source_diverged'
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            IF _verified_changed THEN
                IF NEW.webhook_ingress_identity_id IS NOT NULL THEN
                    SELECT i.verified_amount_minor INTO _source_amount
                      FROM public.webhook_ingress_identities AS i
                     WHERE i.id = NEW.webhook_ingress_identity_id
                       AND i.tenant_id = NEW.tenant_id;
                    IF FOUND
                       AND _source_amount
                           IS NOT DISTINCT FROM NEW.verified_amount_minor
                       AND public.b26_p2_ingress_has_current_authority(
                               NEW.webhook_ingress_identity_id) THEN
                        _source_ok := true;
                    END IF;
                END IF;
                IF NOT _source_ok THEN
                    SELECT true INTO _source_ok
                      FROM public.b23_revenue_events AS e
                      JOIN public.webhook_ingress_identities AS i
                        ON i.tenant_id = e.tenant_id
                       AND i.provider = e.provider
                       AND i.provider_native_event_reference =
                           e.provider_native_event_reference
                     WHERE e.tenant_id = NEW.tenant_id
                       AND e.match_verdict_id = NEW.id
                       AND e.is_gross_capture_correction = true
                       AND e.captured_amount_minor =
                           NEW.canonical_captured_gross_amount_minor
                       AND i.verified_amount_minor =
                           NEW.canonical_captured_gross_amount_minor
                       AND public.b26_p2_ingress_has_current_authority(
                               i.id)
                     LIMIT 1;
                END IF;
                IF NOT COALESCE(_source_ok, false) THEN
                    RAISE EXCEPTION
                        'b26_p2_verdict_money_authority_refused:'
                        'verified_source_missing'
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            IF _net_changed THEN
                SELECT GREATEST(
                           0::bigint,
                           NEW.canonical_captured_gross_amount_minor::bigint
                           + COALESCE(SUM(
                               CASE
                                   WHEN e.is_gross_capture_correction
                                       THEN 0
                                   WHEN e.event_type IN
                                       ('partial_refund', 'full_refund')
                                       THEN -COALESCE(
                                           e.refund_amount_minor, 0)
                                   WHEN e.event_type = 'chargeback_lost'
                                       THEN -COALESCE(
                                           e.chargeback_amount_minor, 0)
                                   WHEN e.event_type = 'chargeback_won'
                                       THEN COALESCE(
                                           e.chargeback_amount_minor, 0)
                                   WHEN e.event_type = 'reversal'
                                       THEN COALESCE(
                                           e.reversal_amount_minor, 0)
                                   ELSE 0
                               END), 0))
                  INTO _net
                  FROM public.b23_revenue_events AS e
                 WHERE e.tenant_id = NEW.tenant_id
                   AND e.match_verdict_id = NEW.id;
                IF NEW.canonical_net_verified_amount_minor
                       IS DISTINCT FROM _net THEN
                    RAISE EXCEPTION
                        'b26_p2_verdict_money_authority_refused:'
                        'net_not_recomputed'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    # The trigger function executes as the table owner when the trigger
    # fires; no runtime role needs direct EXECUTE. Leaving the default
    # PUBLIC grant would make every runtime principal an apparent
    # authority surface in topology capability coverage.
    _revoke_execute("b26_p2_enforce_verdict_money_authority()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_money_authority"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_money_authority
        BEFORE UPDATE OF
            attributed_amount_minor,
            verified_amount_minor,
            canonical_expected_gross_amount_minor,
            canonical_captured_gross_amount_minor,
            canonical_net_verified_amount_minor
        ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_verdict_money_authority()
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_verify_history_continuity()
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                HAVING count(*) > 0
                   AND max(l.seq) - min(l.seq) + 1 <> count(*)
            ) THEN
                violation := 'supersession_sequence_gap';
                RETURN NEXT;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.entry_hash IS NULL
            ) THEN
                violation := 'supersession_chain_unchained_row';
                RETURN NEXT;
            END IF;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_verify_history_continuity()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_money_authority"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_enforce_verdict_money_authority()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_read_history_snapshot(bigint)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_authority_universe()"
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_authority_universe"
    )
    # Restore the XXII conservation function shape (NULL-skipping) so the
    # downgrade is a true inverse of the upgrade body.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b26_p2_verify_source_money_conservation(
                p_tenant_id uuid,
                p_verdict_id uuid
            )
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _ingress uuid;
            _verified integer;
            _attributed integer;
            _row record;
            _prev record;
            _first record;
            _ingress_amount integer;
            _count bigint;
        BEGIN
            SELECT v.webhook_ingress_identity_id,
                   v.verified_amount_minor,
                   v.attributed_amount_minor
              INTO _ingress, _verified, _attributed
              FROM public.b23_match_verdicts AS v
             WHERE v.tenant_id = p_tenant_id
               AND v.id = p_verdict_id;
            IF NOT FOUND THEN
                violation := 'conservation_verdict_missing';
                RETURN NEXT;
                RETURN;
            END IF;
            SELECT count(*) INTO _count
              FROM public.b26_p2_verdict_supersession_ledger AS l
             WHERE l.tenant_id = p_tenant_id
               AND l.verdict_id = p_verdict_id;
            IF _count = 0 THEN
                IF _ingress IS NOT NULL THEN
                    SELECT i.verified_amount_minor INTO _ingress_amount
                      FROM public.webhook_ingress_identities AS i
                     WHERE i.id = _ingress
                       AND i.tenant_id = p_tenant_id;
                    IF _ingress_amount IS NOT NULL
                       AND _verified IS DISTINCT FROM _ingress_amount THEN
                        violation :=
                            'conservation_initial_amount_not_source';
                        RETURN NEXT;
                    END IF;
                END IF;
                RETURN;
            END IF;
            SELECT l.* INTO _first
              FROM public.b26_p2_verdict_supersession_ledger AS l
             WHERE l.tenant_id = p_tenant_id
               AND l.verdict_id = p_verdict_id
             ORDER BY l.seq ASC
             LIMIT 1;
            IF _first.prior_source_ingress IS NOT NULL THEN
                SELECT i.verified_amount_minor INTO _ingress_amount
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _first.prior_source_ingress
                   AND i.tenant_id = p_tenant_id;
                IF _ingress_amount IS NOT NULL
                   AND _first.prior_verified_amount_minor
                       IS DISTINCT FROM _ingress_amount THEN
                    violation :=
                        'conservation_first_prior_not_source';
                    RETURN NEXT;
                END IF;
            ELSIF _ingress IS NOT NULL THEN
                SELECT i.verified_amount_minor INTO _ingress_amount
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = p_tenant_id;
                IF _ingress_amount IS NOT NULL
                   AND _first.prior_verified_amount_minor
                       IS DISTINCT FROM _ingress_amount THEN
                    violation :=
                        'conservation_first_prior_not_source';
                    RETURN NEXT;
                END IF;
            END IF;
            _prev := NULL;
            FOR _row IN
                SELECT l.*
                  FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.tenant_id = p_tenant_id
                   AND l.verdict_id = p_verdict_id
                 ORDER BY l.seq ASC
            LOOP
                IF _prev IS NOT NULL THEN
                    IF _row.prior_verified_amount_minor
                           IS DISTINCT FROM _prev.new_verified_amount_minor
                       OR _row.prior_attributed_amount_minor
                           IS DISTINCT FROM _prev.new_attributed_amount_minor
                       OR _row.prior_source_ingress
                           IS DISTINCT FROM _prev.new_source_ingress THEN
                        violation := 'conservation_chain_discontinuous';
                        RETURN NEXT;
                    END IF;
                END IF;
                _prev := _row;
            END LOOP;
            IF _prev.new_verified_amount_minor IS DISTINCT FROM _verified
               OR _prev.new_attributed_amount_minor IS DISTINCT FROM _attributed
               OR _prev.new_source_ingress IS DISTINCT FROM _ingress THEN
                violation := 'conservation_ledger_not_current';
                RETURN NEXT;
            END IF;
            RETURN;
        END $$;
        """
    )
