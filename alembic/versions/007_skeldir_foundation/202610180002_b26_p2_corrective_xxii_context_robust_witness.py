"""B2.6-P2 Corrective XXII: independent witness, chronology, conservation.

This revision adds the database half of the XXII corrective:

* witness read surfaces so the out-of-database observer can sign a
  checkpoint over exactly (count, tip seq, tip hash) without holding
  ledger table rights;
* a source-to-money conservation oracle for Trust issuance;
* chronology guards for history observations and ingress event clocks;
* a strict Shopify creation chronology at the database minting seam.

The signed journal itself lives outside PostgreSQL (see
``app.trust.history_witness``); no table here can substitute for it.

Revision ID: 202610180002
Revises: 202610180001
"""

from __future__ import annotations

from alembic import op

revision = "202610180002"
down_revision = "202610180001"
branch_labels = None
depends_on = None

_RUNTIME_ROLES = (
    "app_user",
    "app_ingress",
    "app_worker",
    "app_relay",
    "app_beat",
    "app_trust_issuer",
)


def _grant_execute(function: str, roles: tuple[str, ...]) -> None:
    for role in roles:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'GRANT EXECUTE ON"
            " FUNCTION public.%s TO %s'; END IF; END $$;"
            % (role, function, role)
        )


def _revoke_execute(function: str) -> None:
    op.execute(
        "REVOKE ALL ON FUNCTION public.%s FROM PUBLIC" % function
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # XXII-1. Witness read surfaces. The observer runs as a runtime
    # principal with no ledger rights. These DEFINER functions expose
    # only what a signed checkpoint needs: the live count, tip sequence,
    # tip hash, a single entry hash by sequence, and violations.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_witness_state()
        RETURNS TABLE (n bigint, tip_seq bigint, tip_hash text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            SELECT count(*),
                   max(l.seq),
                   (SELECT entry_hash
                      FROM public.b26_p2_verdict_supersession_ledger
                     ORDER BY seq DESC LIMIT 1)
              INTO n, tip_seq, tip_hash
              FROM public.b26_p2_verdict_supersession_ledger AS l;
            RETURN NEXT;
            RETURN;
        END $$;
        """
    )
    _revoke_execute("b26_p2_read_history_witness_state()")
    _grant_execute(
        "b26_p2_read_history_witness_state()",
        ("app_user", "app_worker", "app_beat"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_prefix_digest()
        RETURNS text
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        SELECT encode(
            digest(
                coalesce(
                    string_agg(
                        l.seq::text || ':' || l.entry_hash,
                        '|' ORDER BY l.seq
                    ),
                    ''
                ),
                'sha256'
            ),
            'hex'
        )
          FROM public.b26_p2_verdict_supersession_ledger AS l
        $$
        """
    )
    _revoke_execute("b26_p2_read_history_prefix_digest()")
    _grant_execute(
        "b26_p2_read_history_prefix_digest()",
        ("app_user", "app_worker", "app_beat"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_entry_hash(
            p_seq bigint
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _hash text;
        BEGIN
            SELECT entry_hash INTO _hash
              FROM public.b26_p2_verdict_supersession_ledger
             WHERE seq = p_seq;
            RETURN _hash;
        END $$;
        """
    )
    _revoke_execute("b26_p2_read_history_entry_hash(bigint)")
    _grant_execute(
        "b26_p2_read_history_entry_hash(bigint)",
        ("app_user", "app_worker", "app_beat"),
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_violations()
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _viol text := '';
            _v text;
        BEGIN
            FOR _v IN SELECT violation
                        FROM public.b26_p2_verify_history_protection()
            LOOP
                _viol := _viol || _v || ';';
            END LOOP;
            FOR _v IN SELECT violation
                        FROM public.b26_p2_verify_history_continuity()
            LOOP
                _viol := _viol || _v || ';';
            END LOOP;
            RETURN _viol;
        END $$;
        """
    )
    _revoke_execute("b26_p2_read_history_violations()")
    _grant_execute(
        "b26_p2_read_history_violations()",
        ("app_user", "app_worker", "app_beat"),
    )

    # ------------------------------------------------------------------
    # XXII-2. Source-to-money conservation for one verdict. This is not
    # a parallel ledger oracle: it reads the same supersession rows and
    # the authenticated ingress amount, then refuses when the current
    # money state is not the lawful continuation of that source. A
    # coherent rewrite of the internal chain is still caught by the
    # independent signed checkpoint; this function catches a rewrite
    # that leaves the signed chain count/tip untouched.
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
    _revoke_execute(
        "b26_p2_verify_source_money_conservation(uuid, uuid)"
    )
    _grant_execute(
        "b26_p2_verify_source_money_conservation(uuid, uuid)",
        ("app_user", "app_trust_issuer"),
    )

    # ------------------------------------------------------------------
    # XXII-3. Observation chronology. Future-dated observations are not
    # evidence about a present ledger; they are refused at the table so
    # no caller can seed a "fresh" observation from a clock it chooses.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b26_p2_enforce_observation_chronology()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NEW.observed_at > clock_timestamp()
                   + interval '120 seconds' THEN
                RAISE EXCEPTION 'b26_p2_observation_future_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_observation_chronology"
        " ON public.b26_p2_history_integrity_observations"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_observation_chronology
        BEFORE INSERT ON public.b26_p2_history_integrity_observations
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_observation_chronology()
        """
    )

    # ------------------------------------------------------------------
    # XXII-4. Ingress event-clock plausibility. A provider event cannot
    # be authoritative for a future instant; the authenticated clock is
    # bounded by the receipt clock. Delayed delivery stays lawful
    # because only the future direction is refused.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b26_p2_enforce_ingress_event_chronology()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NEW.event_timestamp > clock_timestamp()
                   + interval '300 seconds' THEN
                RAISE EXCEPTION 'b26_p2_ingress_event_future_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_event_chronology"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_ingress_event_chronology
        BEFORE INSERT ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_ingress_event_chronology()
        """
    )

    # ------------------------------------------------------------------
    # XXII-5. Strict Shopify creation chronology at the mint seam. The
    # prior 60s absolute-delta law admitted near-creation updates and
    # reversed chronology. Positive creation evidence now requires the
    # update instant to equal the creation instant and never precede
    # it. Unknown/missing evidence still refuses at mint.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_lifecycle_admission(
            p_provider text,
            p_family text,
            p_financial_status text,
            p_cancelled_at timestamptz,
            p_refunds_present boolean,
            p_created_at timestamptz,
            p_updated_at timestamptz,
            p_require_creation_proof boolean
        )
        RETURNS void
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF p_cancelled_at IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(p_refunds_present, false) THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, '')))
                   = 'shopify'
               AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
                   = 'orders.create' THEN
                IF p_require_creation_proof THEN
                    IF p_financial_status IS NULL
                       OR lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                    IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                        RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    IF p_financial_status IS NOT NULL
                       AND lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid', 'voided', 'refunded',
                                  'partially_refunded') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL THEN
                    IF p_updated_at < p_created_at THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_reversed_chronology'
                            USING ERRCODE = '42501';
                    END IF;
                    IF p_updated_at <> p_created_at THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_not_creation_moment'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
            END IF;
            RETURN;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_lifecycle_admission(
            p_provider text,
            p_family text,
            p_financial_status text,
            p_cancelled_at timestamptz,
            p_refunds_present boolean,
            p_created_at timestamptz,
            p_updated_at timestamptz,
            p_require_creation_proof boolean
        )
        RETURNS void
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF p_cancelled_at IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(p_refunds_present, false) THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, '')))
                   = 'shopify'
               AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
                   = 'orders.create' THEN
                IF p_require_creation_proof THEN
                    IF p_financial_status IS NULL
                       OR lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                    IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                        RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                            USING ERRCODE = '42501';
                    END IF;
                    IF abs(extract(epoch FROM
                           (p_updated_at - p_created_at))) > 60 THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_not_creation_moment'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    IF p_financial_status IS NOT NULL
                       AND lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid', 'voided', 'refunded',
                                  'partially_refunded') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                    IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL
                       AND abs(extract(epoch FROM
                           (p_updated_at - p_created_at))) > 60 THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_not_creation_moment'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
            END IF;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_event_chronology"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_enforce_ingress_event_chronology()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_observation_chronology"
        " ON public.b26_p2_history_integrity_observations"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_enforce_observation_chronology()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_verify_source_money_conservation(uuid, uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_read_history_violations()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_read_history_entry_hash(bigint)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_read_history_prefix_digest()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_read_history_witness_state()"
    )
