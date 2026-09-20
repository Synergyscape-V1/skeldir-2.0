"""B2.6-P2 Corrective VI: sovereign canonical root, non-self-authenticating
consequence proof, total actionable operational disposition.

Revision ID: 202609200001
Revises: 202609190001

Corrective-V closed child-to-parent coherence but left the authority-root
class open (independent auditors T and N2, 2026-09-20, NOT COMPLETE):

1. FORGEABLE CANONICAL DISPATCH ROOT. dispatches.window carries only
   NOT NULL + order CHECKs. Nothing binds dispatch.window to
   quantize_utc_day(ingress.event_timestamp), and the admission resolver
   is directory-rooted, so a forged parent with coherent children admits
   and drives B2.3 before the P2 tail can refuse. PostgreSQL ACCEPTS a
   wrong-UTC-day / 12-hour / local-time window from the issuer
   credential; B2.3 authors verdicts under attacker-chosen authority.

2. SELF-AUTHENTICATING RECEIPT. app_worker holds direct INSERT on
   conduction receipts with only syntactic CHECKs, and the gate trusts
   receipt existence + any B2.3 verdict (any status, including pending).
   A synthetic receipt (arbitrary scope text, zero/any count, any
   window) plus B2.3-without-P2 conducts. Receipt window/scope/count
   are decorative; the gate proves worker assertion, not consequence.

3. MUTABLE STALENESS CLOCK + UNWIRED SIGNAL. The non-conduction age
   basis is GREATEST(updated_at), which every retry/error metadata
   UPDATE re-stamps; any producer-credential holder keeps stuck work
   forever young. The threshold is caller-controlled (arbitrary values
   suppress the signal). Celery FAILURE without a DLQ row excludes work
   from staleness while the DLQ shows nothing: evidence in no channel.
   The endpoint has no shipping consumer; the relay sweep log line does
   not surface in the deployed relay output.

4. SILENT QUARANTINE + ZOMBIE PARENTS. Quarantine rows are durable but
   have zero production readers. A published dispatch whose outbox twin
   is missing (migration blocker shape) is invisible to staleness,
   health, and relay alike.

5. AUTHORITY-LANE DIVERGENCE. prepare_migration_authority_boundary.py
   installs a default-privilege GRANT SELECT, INSERT ON TABLES TO
   app_user for migration_owner-created tables, so migration-built lanes
   grant app_user INSERT on receipts/quarantine while the canonical
   bootstrap lane does not. The equivalence proof REDs in auditor hands
   where engineering claimed PASS.

Database-physics changes (this migration):

- Sovereign canonical-window functions b26_p2_canonical_day_start/end
  (IMMUTABLE SQL): date_trunc UTC-day quantization, parity-tested
  against app.core.day_window.quantize_utc_day (the sovereign Python
  implementation is composed with, never reimplemented semantically:
  the SQL copy is parity-oracle-tested over the complete input shape,
  tz-aware instants across offsets/DST boundaries).
- Dispatch sovereign trigger b26_p2_enforce_dispatch_sovereign_window
  (BEFORE INSERT OR UPDATE OF the sovereign columns): the stored
  window must equal the canonical UTC day of the ingress event clock,
  and the stored provider must equal the ingress provider. Fail-closed
  when the ingress row is not visible under the writer tenant GUC.
- Ingress custody trigger b26_p2_enforce_ingress_sovereign_custody
  (BEFORE UPDATE OF event_timestamp/tenant_id/provider OR DELETE):
  once a dispatch references the ingress, the sovereign clock/identity
  cannot drift and the ingress cannot disappear (no contradictory
  orphan, no silent cascade erasure of accepted execution authority).
  Pre-authority mutation (no dispatch yet) remains allowed.
- Sovereign admission resolver: b26_p2_resolve_dispatch_authority now
  re-establishes D from E (dispatch joined to ingress under the
  directory-bootstrapped tenant, canonical window recomputed in SQL,
  stored window must equal canonical) and RETURNS THE CANONICAL window
  derived from the ingress clock, never the stored copy. A forged D or
  projection refuses inside the resolver, before B2.3 (B2.3 delta = 0).
- Non-self-authenticating consequence: direct receipt INSERT is revoked
  from app_worker/app_user; the only writer is the SECURITY DEFINER
  b26_p2_record_conduction_receipt() (EXECUTE app_worker), which
  derives tenant/ingress/window server-side from the sovereign tuple,
  refuses forged roots, and enforces 64-hex scope shape. The gate
  b26_p2_mark_conducted() independently re-verifies sovereign window,
  qualifying B2.3 statuses (matched_provisional/matched_confirmed/
  adjusted only -- pending/unmatched never satisfy), receipt-to-tuple
  window binding, and scope shape before the twin transition.
- Immutable progress clock: dispatches.first_published_at (set once at
  the pending_publish -> published transition, immutable thereafter,
  backfilled from dispatched_at in the fail-closed direction).
  b26_p2_stale_unconducted() ages from the immutable anchor (never from
  updated_at), validates threshold bounds (1..86400, default 300;
  absurd suppression refuses instead of silencing), and excludes work
  from the never-consumed signal only when BOTH a DLQ row and a result-
  backend FAILURE row exist (telemetry disagreement stays actionable).
- Total disposition b26_p2_operational_disposition(task): every accepted
  D maps to an explicit state (PENDING_PUBLICATION, PUBLISHED_IN_FLIGHT,
  STALE_UNCONDUCTED, TERMINAL_FAILURE_ACTIONABLE, QUARANTINED_ACTIONABLE,
  CONDUCTED, DIVERGENT_ACTIONABLE, MISSING_CHILD_ACTIONABLE,
  NOT_ACCEPTED). LEFT JOINs keep zombie parents actionable; quarantine
  is a first-class disposition.
- Migration root honesty: before the sovereign law installs, every
  existing dispatch is census-checked against its ingress clock;
  root-invalid dispatches (window/provider/verification drift) are
  quarantined with full provenance (children first, then the root) and
  removed via the governed cascade -- children are never normalized to
  a non-sovereign root. Valid B2.3 verdict history is untouched.
- Authority-lane convergence: explicit REVOKE of app_user INSERT on
  receipts/quarantine, forward-looking REVOKE of the INSERT default
  privilege (SELECT default preserved for runtime readability), so
  migration-built and bootstrap lanes carry identical effective P2
  authority.

No P3/P4/P5/P8 durable reconciliation state is introduced. Receipts,
quarantine rows, staleness output, disposition output, and `conducted`
itself remain operational state. B2.4/B2.13/LLM authority stays zero.
"""

from __future__ import annotations

from alembic import op

revision = "202609200001"
down_revision = "202609190001"
branch_labels = None
depends_on = None

_MIGRATION_IDENTITY = "202609200001"


def upgrade() -> None:
    # 0. Lock ordering (Corrective-IV/V discipline): child tables first in
    # SHARE ROW EXCLUSIVE MODE. The dispatch parent is never locked: a
    # coherent triple writer may hold an uncommitted dispatch row and a
    # parent lock here would deadlock against it (reproduced in IV).
    op.execute(
        "LOCK TABLE public.b26_p2_execution_outbox IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_task_authority_directory IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_conduction_receipts IN SHARE ROW EXCLUSIVE MODE"
    )

    # 1. Sovereign canonical-window functions (IMMUTABLE, pure computation,
    # no table access, no RLS interaction). Parity law: for every tz-aware
    # instant, canonical_day_start/end == quantize_utc_day (UTC midnight
    # half-open day). Proven by scripts/ci/b26_p2_window_oracle.py +
    # the VI oracle extension (offsets, DST boundaries, leap instants).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_canonical_day_start(
            p_event_timestamp timestamp with time zone
        )
        RETURNS timestamp with time zone
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
            SELECT (date_trunc('day', p_event_timestamp AT TIME ZONE 'UTC')
                    AT TIME ZONE 'UTC')
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_canonical_day_end(
            p_event_timestamp timestamp with time zone
        )
        RETURNS timestamp with time zone
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
            SELECT ((date_trunc('day', p_event_timestamp AT TIME ZONE 'UTC')
                     AT TIME ZONE 'UTC') + interval '1 day')
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION public.b26_p2_canonical_day_start(timestamptz) IS "
        "'B2.6-P2 Corrective VI sovereign UTC-day quantization: SQL parity "
        "copy of app.core.day_window.quantize_utc_day (parity-oracle tested).'"
    )
    op.execute(
        "COMMENT ON FUNCTION public.b26_p2_canonical_day_end(timestamptz) IS "
        "'B2.6-P2 Corrective VI sovereign UTC-day quantization end bound.'"
    )

    # 2. Quarantine source CHECK expansion: root-invalid dispatches (and
    # their receipts) are quarantinable provenance alongside the V child
    # projections. The residual-incoherence census below counts only the
    # V child relations (unchanged law); root rows use the new sources.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine"
        " DROP CONSTRAINT IF EXISTS ck_b26_p2_quarantine_source"
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_quarantine
            ADD CONSTRAINT ck_b26_p2_quarantine_source
            CHECK (source_relation IN (
                'b26_p2_execution_outbox',
                'b26_p2_task_authority_directory',
                'b23_match_task_dispatches',
                'b26_p2_conduction_receipts'
            ))
        """
    )

    # 3. Census / root-honest quarantine / immutable-anchor backfill.
    # RLS is transiently disabled exactly as in V (the migrating principal
    # holds no tenant GUC; a bare census would match zero rows SILENTLY)
    # and restored immediately after. The sovereign enforcement triggers
    # (step 5/6) install AFTER this census so legacy forged roots are
    # dispositioned, never normalized.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        DECLARE
            _n_root_invalid integer := 0;
            _n_root_children_q integer := 0;
            _n_root_dir_q integer := 0;
            _n_receipts_q integer := 0;
            _n_roots_q integer := 0;
            _n_roots_removed integer := 0;
            _n_backfilled integer := 0;
            _remaining integer := 0;
        BEGIN
            -- 3a. Root-invalid census: window/provider/verification drift
            -- against the sovereign ingress clock. Every such dispatch is
            -- quarantined with its children (children first so their
            -- provenance names the forged root), then removed through the
            -- governed cascade. B2.3 verdict rows are NEVER touched here:
            -- sovereign financial history is preserved even when the
            -- execution root that admitted it was non-sovereign; the
            -- quarantine row carries the explicit non-sovereign
            -- provenance (H-VI-E05).
            CREATE TEMPORARY TABLE _vi_root_invalid ON COMMIT DROP AS
            SELECT d.task_id AS task_id,
                   d.tenant_id AS tenant_id,
                   d.webhook_ingress_identity_id AS ingress_id,
                   d.window_start AS window_start,
                   d.window_end AS window_end,
                   i.event_timestamp AS event_clock,
                   i.provider AS ingress_provider,
                   d.provider AS dispatch_provider,
                   i.verified_commerce_ingress_state AS ingress_state
            FROM public.b23_match_task_dispatches AS d
            JOIN public.webhook_ingress_identities AS i
              ON i.id = d.webhook_ingress_identity_id
             AND i.tenant_id = d.tenant_id
            WHERE d.window_start IS DISTINCT FROM
                      public.b26_p2_canonical_day_start(i.event_timestamp)
               OR d.window_end IS DISTINCT FROM
                      public.b26_p2_canonical_day_end(i.event_timestamp)
               OR d.provider IS DISTINCT FROM i.provider
               OR i.verified_commerce_ingress_state IS DISTINCT FROM
                      'authenticity_verified';
            -- Dispatches whose ingress row is gone entirely (precludes
            -- the join above; FKs normally prevent this, admin action
            -- aside) are likewise root-invalid.
            INSERT INTO _vi_root_invalid
            SELECT d.task_id, d.tenant_id, d.webhook_ingress_identity_id,
                   d.window_start, d.window_end, NULL, NULL, d.provider, NULL
            FROM public.b23_match_task_dispatches AS d
            WHERE NOT EXISTS (
                SELECT 1 FROM public.webhook_ingress_identities AS i
                WHERE i.id = d.webhook_ingress_identity_id
                  AND i.tenant_id = d.tenant_id
            )
            ON CONFLICT DO NOTHING;
            SELECT count(*) INTO _n_root_invalid FROM _vi_root_invalid;

            -- 3b. Quarantine children of forged roots (outbox, directory,
            -- receipts) with forged-root provenance.
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_vi:root_invalid_forged_dispatch_parent',
                   COALESCE(o.payload, '{}'::jsonb), '202609200001'
            FROM public.b26_p2_execution_outbox AS o
            JOIN _vi_root_invalid AS r
              ON r.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_root_children_q = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_vi:root_invalid_forged_dispatch_parent',
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609200001'
            FROM public.b26_p2_task_authority_directory AS dir
            JOIN _vi_root_invalid AS r
              ON r.task_id = dir.task_id;
            GET DIAGNOSTICS _n_root_dir_q = ROW_COUNT;
            _n_root_children_q := _n_root_children_q + _n_root_dir_q;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_vi:root_invalid_forged_dispatch_parent',
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity
                   ), '202609200001'
            FROM public.b26_p2_conduction_receipts AS rec
            JOIN _vi_root_invalid AS r
              ON r.task_id = rec.task_id;
            GET DIAGNOSTICS _n_receipts_q = ROW_COUNT;

            -- 3c. Quarantine the forged roots themselves, then remove them
            -- through the governed tuple cascade (children already
            -- preserved above; verdicts are ingress-bound and survive).
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', r.task_id, r.tenant_id,
                   r.ingress_id, r.window_start, r.window_end,
                   'corrective_vi:root_window_not_sovereign',
                   jsonb_build_object(
                       'dispatch_provider', r.dispatch_provider,
                       'ingress_provider', r.ingress_provider,
                       'ingress_state', r.ingress_state,
                       'event_clock', r.event_clock::text
                   ), '202609200001'
            FROM _vi_root_invalid AS r;
            GET DIAGNOSTICS _n_roots_q = ROW_COUNT;
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _vi_root_invalid AS r
            WHERE d.task_id = r.task_id;
            GET DIAGNOSTICS _n_roots_removed = ROW_COUNT;

            -- 3d. Immutable progress-clock anchor: new column + backfill.
            -- Fail-closed direction: pre-VI published/conducted rows anchor
            -- at dispatched_at (the earliest governed instant), so no
            -- long-unconsumed execution can appear young after upgrade.
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'b23_match_task_dispatches'
                  AND column_name = 'first_published_at'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD COLUMN first_published_at
                        timestamp with time zone NULL;
            END IF;
            UPDATE public.b23_match_task_dispatches AS d
               SET first_published_at = d.dispatched_at
             WHERE d.delivery_state IN ('published', 'conducted')
               AND d.first_published_at IS NULL;
            GET DIAGNOSTICS _n_backfilled = ROW_COUNT;

            -- 3e. Post-census invariant: no surviving dispatch contradicts
            -- its sovereign ingress clock.
            SELECT count(*) INTO _remaining
            FROM public.b23_match_task_dispatches AS d
            JOIN public.webhook_ingress_identities AS i
              ON i.id = d.webhook_ingress_identity_id
             AND i.tenant_id = d.tenant_id
            WHERE d.window_start IS DISTINCT FROM
                      public.b26_p2_canonical_day_start(i.event_timestamp)
               OR d.window_end IS DISTINCT FROM
                      public.b26_p2_canonical_day_end(i.event_timestamp)
               OR d.provider IS DISTINCT FROM i.provider
               OR i.verified_commerce_ingress_state IS DISTINCT FROM
                      'authenticity_verified';
            RAISE NOTICE 'b26_p2_corrective_vi_census root_invalid=% '
                'root_children_quarantined=% receipts_quarantined=% '
                'roots_quarantined=% roots_removed=% anchor_backfilled=% '
                'residual_root_invalid=%',
                _n_root_invalid, _n_root_children_q, _n_receipts_q,
                _n_roots_q, _n_roots_removed, _n_backfilled, _remaining;
            IF _remaining <> 0 THEN
                RAISE EXCEPTION 'b26_p2_sovereign_vi_residual_root_invalid:%',
                    _remaining;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_outbox FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.webhook_ingress_identities FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_quarantine FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_conduction_receipts FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b23_match_verdicts FORCE ROW LEVEL SECURITY"
    )

    # 4. Dispatch sovereign-window enforcement (BEFORE INSERT OR UPDATE of
    # the sovereign columns). The writer tenant GUC is the visibility
    # root (same pattern as the V directory coherence law): the ingress
    # row for NEW must be visible under it and the stored window/provider
    # must equal the sovereign derivation, else refuse fail-closed.
    # IS DISTINCT FROM keeps NULL (UNKNOWN) from becoming acceptance.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_sovereign_window()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _clock timestamptz;
            _ingress_tenant uuid;
            _ingress_provider varchar(32);
            _ingress_state varchar(64);
            _exp_ws timestamptz;
            _exp_we timestamptz;
        BEGIN
            SELECT i.event_timestamp, i.tenant_id, i.provider,
                   i.verified_commerce_ingress_state
              INTO _clock, _ingress_tenant, _ingress_provider, _ingress_state
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = NEW.webhook_ingress_identity_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _ingress_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_tenant_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            _exp_ws := public.b26_p2_canonical_day_start(_clock);
            _exp_we := public.b26_p2_canonical_day_end(_clock);
            IF NEW.window_start IS DISTINCT FROM _exp_ws
               OR NEW.window_end IS DISTINCT FROM _exp_we THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.provider IS DISTINCT FROM _ingress_provider THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_not_sovereign'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_dispatch_sovereign_window'
            ) THEN
                CREATE TRIGGER trg_b26_p2_dispatch_sovereign_window
                BEFORE INSERT OR UPDATE OF
                    window_start, window_end,
                    webhook_ingress_identity_id, tenant_id, provider
                ON public.b23_match_task_dispatches
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_dispatch_sovereign_window();
            END IF;
        END $$;
        """
    )

    # 5. Ingress sovereign custody: once a dispatch references the ingress,
    # the sovereign clock/identity cannot drift and the ingress cannot be
    # deleted (no contradictory orphan, no silent cascade erasure of
    # accepted execution authority). Pre-authority mutation stays allowed.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_sovereign_custody()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.webhook_ingress_identity_id = OLD.id
                ) THEN
                    RAISE EXCEPTION 'b26_p2_ingress_sovereign_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b23_match_task_dispatches AS d
                WHERE d.webhook_ingress_identity_id = NEW.id
            ) THEN
                IF OLD.event_timestamp IS DISTINCT FROM NEW.event_timestamp THEN
                    RAISE EXCEPTION 'b26_p2_ingress_event_clock_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                    RAISE EXCEPTION 'b26_p2_ingress_tenant_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.provider IS DISTINCT FROM NEW.provider THEN
                    RAISE EXCEPTION 'b26_p2_ingress_provider_immutable'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_ingress_sovereign_custody'
            ) THEN
                CREATE TRIGGER trg_b26_p2_ingress_sovereign_custody
                BEFORE UPDATE OF event_timestamp, tenant_id, provider
                    OR DELETE
                ON public.webhook_ingress_identities
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_ingress_sovereign_custody();
            END IF;
        END $$;
        """
    )

    # 6. Outbox issuance + retry-bound law (BEFORE INSERT / UPDATE).
    # Delivery intent is minted pending_publish only (no minted
    # published/conducted twins bypassing the relay recovery path), and
    # the next-retry horizon is bounded (now + 1h): a far-future
    # next_retry_at would strand accepted intent outside the sweep while
    # remaining invisible to every aggregate except per-task disposition.
    # The relay's own backoff (<=300s) sits far inside the bound, so
    # lawful recovery never trips it.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_outbox_issuance()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF NEW.state IS DISTINCT FROM 'pending_publish' THEN
                RAISE EXCEPTION 'b26_p2_outbox_issuance_state_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.next_retry_at > now() + interval '1 hour' THEN
                RAISE EXCEPTION 'b26_p2_outbox_retry_unbounded'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_outbox_issuance'
            ) THEN
                CREATE TRIGGER trg_b26_p2_outbox_issuance
                BEFORE INSERT ON public.b26_p2_execution_outbox
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_outbox_issuance();
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_outbox_transitions()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF OLD.dispatch_task_id IS DISTINCT FROM NEW.dispatch_task_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_task_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_outbox_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.next_retry_at > now() + interval '1 hour' THEN
                RAISE EXCEPTION 'b26_p2_outbox_retry_unbounded'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.state IS DISTINCT FROM NEW.state THEN
                IF OLD.state = 'pending_publish'
                   AND NEW.state = 'published' THEN
                    NULL;
                ELSIF OLD.state = 'published'
                   AND NEW.state = 'conducted' THEN
                    -- Corrective V: same gate law as dispatch above.
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b26_p2_outbox_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """
    )

    # 7. Dispatch immutability law, VI revision: V law byte-preserved plus
    # the immutable progress-clock anchor. first_published_at is set once
    # by this trigger at the published transition (never by runtime SET:
    # the new column carries no runtime UPDATE grant) and can never move
    # afterwards. Non-progress metadata (attempts, errors, updated_at)
    # keeps flowing without touching the age basis.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_immutability()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.delivery_state IS DISTINCT FROM 'pending_publish'
                   AND NEW.delivery_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_delivery_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.delivery_state = 'conducted' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                        USING ERRCODE = '42501';
                END IF;
                -- The progress anchor is server-derived, never
                -- caller-authored: a future-dated anchor at INSERT would
                -- suppress the non-conduction signal before it starts.
                -- Publication anchors at now(); pre-published rows carry
                -- no anchor.
                IF NEW.delivery_state = 'published' THEN
                    NEW.first_published_at := now();
                ELSE
                    NEW.first_published_at := NULL;
                END IF;
                RETURN NEW;
            END IF;
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_id IS DISTINCT FROM NEW.task_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_id_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_name IS DISTINCT FROM NEW.task_name THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_name_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.queue IS DISTINCT FROM NEW.queue THEN
                RAISE EXCEPTION 'b26_p2_dispatch_queue_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.routing_key IS DISTINCT FROM NEW.routing_key THEN
                RAISE EXCEPTION 'b26_p2_dispatch_routing_key_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider IS DISTINCT FROM NEW.provider THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_event_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_commerce_reference IS DISTINCT FROM NEW.provider_native_commerce_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_commerce_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.normalized_commerce_reference_value IS DISTINCT FROM NEW.normalized_commerce_reference_value THEN
                RAISE EXCEPTION 'b26_p2_dispatch_norm_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.correlation_id IS DISTINCT FROM NEW.correlation_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_correlation_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.dispatched_at IS DISTINCT FROM NEW.dispatched_at THEN
                RAISE EXCEPTION 'b26_p2_dispatch_dispatched_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_start IS DISTINCT FROM NEW.window_start THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.first_published_at IS NOT NULL
               AND NEW.first_published_at IS DISTINCT FROM OLD.first_published_at THEN
                RAISE EXCEPTION 'b26_p2_dispatch_first_published_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_dispatch_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            -- The progress anchor is server-derived on every write, never
            -- caller-preserved: a pre-set (e.g. future-dated) anchor on a
            -- pending row is stripped here, and the publish transition
            -- stamps now() unconditionally. No reachable UPDATE path can
            -- carry a caller-authored anchor into published life.
            IF NEW.delivery_state = 'pending_publish' THEN
                NEW.first_published_at := NULL;
            END IF;
            IF OLD.delivery_state IS DISTINCT FROM NEW.delivery_state THEN
                IF OLD.delivery_state = 'pending_publish'
                   AND NEW.delivery_state = 'published' THEN
                    NEW.first_published_at := now();
                ELSIF OLD.delivery_state = 'published'
                   AND NEW.delivery_state = 'conducted' THEN
                    -- Corrective V gate law preserved: only the conduction
                    -- gate (owner execution context) may assert conducted.
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b26_p2_dispatch_delivery_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            IF NEW.delivery_state IN ('published', 'conducted')
               AND NEW.first_published_at IS NULL THEN
                RAISE EXCEPTION 'b26_p2_dispatch_first_published_missing'
                    USING ERRCODE = '42501';
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_dispatch_immutability'
            ) THEN
                DROP TRIGGER trg_b26_p2_dispatch_immutability
                    ON public.b23_match_task_dispatches;
            END IF;
            CREATE TRIGGER trg_b26_p2_dispatch_immutability
            BEFORE INSERT OR UPDATE ON public.b23_match_task_dispatches
            FOR EACH ROW EXECUTE FUNCTION
                public.b26_p2_enforce_dispatch_immutability();
        END $$;
        """
    )

    # 8. Sovereign admission resolver: same signature, sovereign content.
    # The bearer-keyed directory resolves without a caller GUC; the tenant
    # visibility root is bootstrapped from the canonical tuple; dispatch
    # and ingress are re-established under that tenant; the stored window
    # must equal the canonical UTC day of the authenticated ingress clock;
    # the RETURNED window is the canonical derivation from E, never the
    # stored copy. Any forged D or projection refuses here, before B2.3.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_resolve_dispatch_authority(
            p_task_id text
        )
        RETURNS TABLE (
            tenant_id uuid,
            webhook_ingress_identity_id uuid,
            window_start timestamp with time zone,
            window_end timestamp with time zone
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dir_ws timestamptz;
            _dir_we timestamptz;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                -- V-compatible lookup-miss semantics: no authority row,
                -- no exception. Callers treat the empty set as missing
                -- authority and refuse before B2.3. Sovereign violations
                -- below (forged/unverified/forked) DO raise: a caller must
                -- never mistake a forged root for a merely-missing one.
                RETURN;
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id,
                   dir.window_start, dir.window_end
              INTO _tenant, _ingress, _dir_ws, _dir_we
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end
                  INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_authority_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_ws IS DISTINCT FROM _dir_ws
                   OR _dispatch_we IS DISTINCT FROM _dir_we THEN
                    RAISE EXCEPTION 'b26_p2_directory_forked_authority_refused'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state
                  INTO _clock, _ingress_state
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                tenant_id := _tenant;
                webhook_ingress_identity_id := _ingress;
                window_start := _exp_ws;
                window_end := _exp_we;
                RETURN NEXT;
                RETURN;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )

    # 9. Non-self-authenticating receipt writer: the only server-side path
    # that may create conduction proof. Tenant/ingress/window are derived
    # from the sovereign tuple (never from caller arguments); forged roots
    # refuse before any row exists; scope shape is enforced (64 lowercase
    # hex). The worker supplies only the scope witness string and the
    # batch processed count (operational provenance, never authority).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_conduction_receipt(
            p_task_id text,
            p_scope_identity text,
            p_processed_count integer DEFAULT 0
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _scope text;
            _count integer;
            _tenant uuid;
            _ingress uuid;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_receipt_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            _scope := btrim(COALESCE(p_scope_identity, ''));
            IF _scope !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_scope_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            _count := COALESCE(p_processed_count, 0);
            IF _count < 0 THEN
                RAISE EXCEPTION 'b26_p2_receipt_count_negative'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_receipt_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end
                  INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state
                  INTO _clock, _ingress_state
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                INSERT INTO public.b26_p2_conduction_receipts (
                    task_id, tenant_id, webhook_ingress_identity_id,
                    window_start, window_end,
                    b23_processed_count, p2_scope_identity
                )
                VALUES (_task, _tenant, _ingress,
                        _exp_ws, _exp_we,
                        _count, _scope)
                ON CONFLICT (task_id) DO NOTHING;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN _task;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_conduction_receipt(text, text, integer)"
        " FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_record_conduction_receipt(text, text, integer)
                    TO app_worker;
            END IF;
        END $$;
        """
    )

    # 10. Receipt INSERT authority closure: worker/user synthesis ends here.
    # The owner function above is the only writer; direct INSERT is
    # revoked on every lane (this also converges the default-privilege
    # divergence: the V default grant to app_user is explicitly removed).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts
                    FROM app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_user"
    )
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.b26_p2_execution_quarantine"
        " FROM app_user"
    )
    # Forward-looking lane convergence: the ambient INSERT default that
    # created the V divergence is removed. SELECT default stays: runtime
    # readability of future tables is preserved; future writes require
    # explicit governed GRANTs (the equivalence proof REDs otherwise).
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE migration_owner IN SCHEMA public"
        " REVOKE INSERT ON TABLES FROM app_user"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postgres') THEN
                BEGIN
                    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres'
                        ' IN SCHEMA public REVOKE INSERT ON TABLES FROM app_user';
                EXCEPTION WHEN OTHERS THEN
                    RAISE NOTICE 'b26_p2_vi_default_priv_postgres_skip:%', SQLERRM;
                END;
            END IF;
        END $$;
        """
    )
    # Transport/result telemetry is corroboration, never deterministic
    # truth (H-VI-B02/C03/C04): the issuer credential keeps SELECT
    # observability but loses all result-backend writes. Only the
    # worker/relay/beat transport principals (which own the broker/result
    # lifecycle) may write taskmeta; with producer writes revoked, a
    # producer-credential holder can no longer forge a FAILURE row to
    # terminalize (hide) another execution's stale signal. Kombu DML
    # stays: broker SEND is transport, verified at admission.
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta FROM app_user"
    )
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta FROM app_user"
    )

    # 11. Consequence-bound gate, VI revision: V law preserved (caller,
    # twin-published, idempotence, twin UPDATEs as owner) plus independent
    # re-verification -- sovereign window from the ingress clock,
    # authenticity of the ingress, receipt-to-tuple window binding, 64-hex
    # scope shape, and the NARROW B2.3 prerequisite: only qualifying
    # deterministic consequence statuses (matched_provisional,
    # matched_confirmed, adjusted) satisfy the gate. pending/unmatched
    # verdicts never authorize conduction. Celery result telemetry is
    # never consulted (transport is corroboration, not truth).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_mark_conducted(p_task_id text)
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _outbox_state text;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _receipt_count integer;
            _receipt_ws timestamptz;
            _receipt_we timestamptz;
            _receipt_scope text;
            _verdict_count integer;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_conducted_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_conducted_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state, d.window_start, d.window_end
                  INTO _dispatch_state, _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT o.state INTO _outbox_state
                  FROM public.b26_p2_execution_outbox AS o
                 WHERE o.dispatch_task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_outbox'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_state = 'conducted' AND _outbox_state = 'conducted' THEN
                    PERFORM set_config('app.current_tenant_id',
                                       COALESCE(_prev_guc, ''), true);
                    RETURN 'already_conducted';
                END IF;
                IF _dispatch_state IS DISTINCT FROM 'published'
                   OR _outbox_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_not_published'
                        USING ERRCODE = '42501';
                END IF;
                -- Independent sovereign re-verification (MODE B): the gate
                -- re-establishes D from E instead of trusting the worker
                -- projection. A forged root refuses here even if admission
                -- were ever bypassed.
                SELECT i.event_timestamp, i.verified_commerce_ingress_state
                  INTO _clock, _ingress_state
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                -- Task-specific proof binding: exactly one receipt for this
                -- tuple, carrying the sovereign window and a well-formed
                -- scope witness. Decorative windows/scopes refuse.
                SELECT count(*), max(r.window_start), max(r.window_end),
                       max(r.p2_scope_identity)
                  INTO _receipt_count, _receipt_ws, _receipt_we, _receipt_scope
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task
                   AND r.tenant_id = _tenant
                   AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_receipt'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_ws IS DISTINCT FROM _exp_ws
                   OR _receipt_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_receipt_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_scope !~ '^[0-9a-f]{64}$' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_scope_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                -- Narrow B2.3 prerequisite: only qualifying deterministic
                -- consequence authorizes conduction. pending/unmatched
                -- verdicts (no deterministic match truth) never satisfy.
                SELECT count(*) INTO _verdict_count
                  FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress
                   AND v.status IN ('matched_provisional',
                                    'matched_confirmed',
                                    'adjusted');
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_b23_consequence'
                        USING ERRCODE = '42501';
                END IF;
                UPDATE public.b23_match_task_dispatches AS d
                   SET delivery_state = 'conducted', updated_at = now()
                 WHERE d.task_id = _task AND d.delivery_state = 'published';
                UPDATE public.b26_p2_execution_outbox AS o
                   SET state = 'conducted', updated_at = now()
                 WHERE o.dispatch_task_id = _task AND o.state = 'published';
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN 'conducted';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )

    # 12. Staleness signal, VI revision: immutable-anchor age basis,
    # bounded threshold authority, telemetry-agreement exclusion.
    # SECURITY DEFINER (owner reads; callers hold EXECUTE only) so the
    # DLQ/result agreement check needs no caller table grants. RLS still
    # applies under the caller tenant GUC (no BYPASSRLS anywhere).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_stale_unconducted(
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS TABLE (
            task_id character varying(155),
            tenant_id uuid,
            state character varying(32),
            age_seconds double precision,
            updated_at timestamp with time zone
        )
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _threshold integer;
        BEGIN
            _threshold := COALESCE(p_stale_after_seconds, 300);
            IF _threshold < 1 OR _threshold > 86400 THEN
                RAISE EXCEPTION 'b26_p2_staleness_threshold_out_of_bounds'
                    USING ERRCODE = '42501';
            END IF;
            RETURN QUERY
            SELECT d.task_id, d.tenant_id, d.delivery_state,
                   EXTRACT(EPOCH FROM (now() - COALESCE(
                       d.first_published_at, d.dispatched_at)))::double precision,
                   COALESCE(d.first_published_at, d.dispatched_at)
            FROM public.b23_match_task_dispatches AS d
            JOIN public.b26_p2_execution_outbox AS o
              ON o.dispatch_task_id = d.task_id
             AND o.tenant_id = d.tenant_id
             AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id
            WHERE d.delivery_state = 'published'
              AND o.state = 'published'
              AND COALESCE(d.first_published_at, d.dispatched_at)
                  < now() - (_threshold || ' seconds')::interval
              -- Terminal task failure is actionable ONLY when both
              -- telemetry channels agree (DLQ row AND result FAILURE).
              -- Either channel alone never silences never-consumed work:
              -- disagreement stays visible here (actionable), never
              -- invisible everywhere.
              AND NOT (
                    EXISTS (
                        SELECT 1 FROM public.worker_failed_jobs AS w
                         WHERE w.task_id = d.task_id
                    )
                AND EXISTS (
                        SELECT 1 FROM public.celery_taskmeta AS m
                         WHERE m.task_id = d.task_id
                           AND m.status = 'FAILURE'
                    )
              )
            ORDER BY COALESCE(d.first_published_at, d.dispatched_at) ASC;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_user"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_relay;
            END IF;
        END $$;
        """
    )

    # 13. Total operational disposition: every accepted D maps to one
    # explicit actionable state. LEFT JOINs keep zombie parents (dispatch
    # without outbox twin) visible instead of invisible. Quarantine is a
    # first-class disposition. Result/DLQ disagreement never hides work:
    # only joint DLQ+FAILURE agreement is terminal; anything else stays
    # in the pending/in-flight/stale ladder.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_operational_disposition(
            p_task_id text,
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _threshold integer;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _anchor timestamptz;
            _outbox_state text;
            _has_outbox boolean;
            _quarantined boolean;
            _dlq boolean;
            _failed boolean;
            _prev_guc text;
            _result text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_disposition_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            _threshold := COALESCE(p_stale_after_seconds, 300);
            IF _threshold < 1 OR _threshold > 86400 THEN
                RAISE EXCEPTION 'b26_p2_staleness_threshold_out_of_bounds'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN 'NOT_ACCEPTED';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state,
                       COALESCE(d.first_published_at, d.dispatched_at)
                  INTO _dispatch_state, _anchor
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    _result := 'DIVERGENT_ACTIONABLE';
                ELSE
                    SELECT (o.state IS NOT NULL), o.state
                      INTO _has_outbox, _outbox_state
                      FROM public.b26_p2_execution_outbox AS o
                     WHERE o.dispatch_task_id = _task;
                    _has_outbox := COALESCE(_has_outbox, false);
                    SELECT EXISTS (
                        SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                         WHERE q.task_id = _task
                    ) INTO _quarantined;
                    SELECT EXISTS (
                        SELECT 1 FROM public.worker_failed_jobs AS w
                         WHERE w.task_id = _task
                    ) INTO _dlq;
                    SELECT EXISTS (
                        SELECT 1 FROM public.celery_taskmeta AS m
                         WHERE m.task_id = _task
                           AND m.status = 'FAILURE'
                    ) INTO _failed;
                    IF _dispatch_state = 'conducted'
                       AND (_has_outbox IS DISTINCT FROM true
                            OR _outbox_state = 'conducted') THEN
                        _result := 'CONDUCTED';
                    ELSIF NOT _has_outbox THEN
                        _result := 'MISSING_CHILD_ACTIONABLE';
                    ELSIF _dispatch_state IS DISTINCT FROM _outbox_state THEN
                        _result := 'DIVERGENT_ACTIONABLE';
                    ELSIF _quarantined
                       AND _dispatch_state = 'pending_publish' THEN
                        _result := 'QUARANTINED_ACTIONABLE';
                    ELSIF _dispatch_state = 'pending_publish' THEN
                        _result := 'PENDING_PUBLICATION';
                    ELSIF _dispatch_state = 'published' THEN
                        IF _dlq AND _failed THEN
                            _result := 'TERMINAL_FAILURE_ACTIONABLE';
                        ELSIF _quarantined THEN
                            _result := 'QUARANTINED_ACTIONABLE';
                        ELSIF _anchor < now() - (_threshold || ' seconds')::interval THEN
                            _result := 'STALE_UNCONDUCTED';
                        ELSE
                            _result := 'PUBLISHED_IN_FLIGHT';
                        END IF;
                    ELSE
                        _result := 'DIVERGENT_ACTIONABLE';
                    END IF;
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN _result;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_operational_disposition(text, integer)"
        " FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer)"
        " TO app_user"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer)"
        " TO app_ro"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_operational_disposition(text, integer)
                    TO app_relay;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_operational_disposition(text, integer)
                    TO app_worker;
            END IF;
        END $$;
        """
    )

    # 14. Least-privilege deltas: relay consumes quarantine/disposition
    # (shipping operational consumer); beat schedules only (no new
    # grants). Receipt/quarantine readability for worker/audit preserved;
    # receipt synthesis (INSERT) stays revoked (step 9).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_relay;
                GRANT SELECT ON TABLE public.worker_failed_jobs TO app_relay;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_start(timestamptz) TO app_worker;
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_end(timestamptz) TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_start(timestamptz) TO app_relay;
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_end(timestamptz) TO app_relay;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Reverse order of upgrade. All destructive steps carry the
    # CI:DESTRUCTIVE_OK marker (reversible rollback, non-production
    # direction only).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_end(timestamptz) FROM app_relay;
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_start(timestamptz) FROM app_relay;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_end(timestamptz) FROM app_worker;
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_canonical_day_start(timestamptz) FROM app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI canonical grants.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE SELECT ON TABLE public.b26_p2_execution_quarantine FROM app_relay;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI relay quarantine readability.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_operational_disposition(text, integer) FROM app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_operational_disposition(text, integer) FROM app_relay;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI disposition grants.
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer)"
        " FROM app_ro"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI disposition grants.
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.b26_p2_operational_disposition(text, integer)"
        " FROM app_user"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI disposition grants.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_operational_disposition(text, integer)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI disposition law.
    )
    # Restore the V staleness law (plain-SQL, updated_at basis, FAILURE
    # exclusion) BEFORE the vocabulary step-down below.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_stale_unconducted(
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS TABLE (
            task_id character varying(155),
            tenant_id uuid,
            state character varying(32),
            age_seconds double precision,
            updated_at timestamp with time zone
        )
        LANGUAGE sql
        STABLE
        SET search_path TO 'public', 'pg_temp'
        AS $$
            SELECT d.task_id, d.tenant_id, d.delivery_state,
                   EXTRACT(EPOCH FROM (now() - GREATEST(d.updated_at, o.updated_at))),
                   GREATEST(d.updated_at, o.updated_at)
            FROM public.b23_match_task_dispatches AS d
            JOIN public.b26_p2_execution_outbox AS o
              ON o.dispatch_task_id = d.task_id
             AND o.tenant_id = d.tenant_id
             AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id
            WHERE d.delivery_state = 'published'
              AND o.state = 'published'
              AND GREATEST(d.updated_at, o.updated_at)
                  < now() - (GREATEST(COALESCE(p_stale_after_seconds, 300), 1) || ' seconds')::interval
              AND NOT EXISTS (
                    SELECT 1 FROM public.celery_taskmeta AS m
                     WHERE m.task_id = d.task_id
                       AND m.status = 'FAILURE'
              )
            ORDER BY GREATEST(d.updated_at, o.updated_at) ASC
        $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI staleness law.
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_mark_conducted(p_task_id text)
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _outbox_state text;
            _receipt_count integer;
            _verdict_count integer;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_conducted_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_conducted_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state INTO _dispatch_state
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT o.state INTO _outbox_state
                  FROM public.b26_p2_execution_outbox AS o
                 WHERE o.dispatch_task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_outbox'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_state = 'conducted' AND _outbox_state = 'conducted' THEN
                    PERFORM set_config('app.current_tenant_id',
                                       COALESCE(_prev_guc, ''), true);
                    RETURN 'already_conducted';
                END IF;
                IF _dispatch_state IS DISTINCT FROM 'published'
                   OR _outbox_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_not_published'
                        USING ERRCODE = '42501';
                END IF;
                SELECT count(*) INTO _receipt_count
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task
                   AND r.tenant_id = _tenant
                   AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_receipt'
                        USING ERRCODE = '42501';
                END IF;
                SELECT count(*) INTO _verdict_count
                  FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress;
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_b23_consequence'
                        USING ERRCODE = '42501';
                END IF;
                UPDATE public.b23_match_task_dispatches AS d
                   SET delivery_state = 'conducted', updated_at = now()
                 WHERE d.task_id = _task AND d.delivery_state = 'published';
                UPDATE public.b26_p2_execution_outbox AS o
                   SET state = 'conducted', updated_at = now()
                 WHERE o.dispatch_task_id = _task AND o.state = 'published';
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN 'conducted';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI gate law.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_record_conduction_receipt(text, text, integer)
                    FROM app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI receipt writer.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_conduction_receipt(text, text, integer)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI receipt writer.
    )
    op.execute(
        "GRANT INSERT ON TABLE public.b26_p2_execution_quarantine TO app_user"  # CI:DESTRUCTIVE_OK - reversible rollback restoring V default-derived quarantine writes.
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_user"  # CI:DESTRUCTIVE_OK - reversible rollback restoring pre-VI transport writes.
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_user"  # CI:DESTRUCTIVE_OK - reversible rollback restoring pre-VI transport writes.
    )
    op.execute(
        "GRANT INSERT ON TABLE public.b26_p2_conduction_receipts TO app_user"  # CI:DESTRUCTIVE_OK - reversible rollback restoring V default-derived receipt writes.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT, INSERT ON TABLE public.b26_p2_conduction_receipts TO app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback restoring V worker receipt synthesis.
    )
    # Restore the directory-rooted V resolver (sovereign check removed).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_resolve_dispatch_authority(p_task_id text)
        RETURNS TABLE(tenant_id uuid, webhook_ingress_identity_id uuid, window_start timestamptz, window_end timestamptz)
        LANGUAGE sql SECURITY DEFINER SET search_path TO 'public', 'pg_temp' AS $$
         SELECT dir.tenant_id, dir.webhook_ingress_identity_id, dir.window_start, dir.window_end
         FROM public.b26_p2_task_authority_directory AS dir WHERE dir.task_id = p_task_id $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI sovereign resolver.
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_sovereign_custody ON public.webhook_ingress_identities"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI ingress custody.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_ingress_sovereign_custody()"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI ingress custody.
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_sovereign_window ON public.b23_match_task_dispatches"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI sovereign window.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_dispatch_sovereign_window()"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI sovereign window.
    )
    # Restore the V outbox transition law (no issuance trigger, no retry
    # bound) and drop the VI issuance law.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_outbox_issuance ON public.b26_p2_execution_outbox"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI outbox issuance law.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_outbox_issuance()"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI outbox issuance law.
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_outbox_transitions()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF OLD.dispatch_task_id IS DISTINCT FROM NEW.dispatch_task_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_task_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_outbox_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.state IS DISTINCT FROM NEW.state THEN
                IF OLD.state = 'pending_publish'
                   AND NEW.state = 'published' THEN
                    NULL;
                ELSIF OLD.state = 'published'
                   AND NEW.state = 'conducted' THEN
                    -- Corrective V: same gate law as dispatch above.
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b26_p2_outbox_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI outbox retry bound.
    )
    # Restore the V dispatch immutability body (no anchor, no INSERT
    # branch) BEFORE dropping the anchor column below: the VI trigger
    # references first_published_at and must be replaced first.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_immutability()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_id IS DISTINCT FROM NEW.task_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_id_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_name IS DISTINCT FROM NEW.task_name THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_name_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.queue IS DISTINCT FROM NEW.queue THEN
                RAISE EXCEPTION 'b26_p2_dispatch_queue_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.routing_key IS DISTINCT FROM NEW.routing_key THEN
                RAISE EXCEPTION 'b26_p2_dispatch_routing_key_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider IS DISTINCT FROM NEW.provider THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_event_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_commerce_reference IS DISTINCT FROM NEW.provider_native_commerce_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_commerce_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.normalized_commerce_reference_value IS DISTINCT FROM NEW.normalized_commerce_reference_value THEN
                RAISE EXCEPTION 'b26_p2_dispatch_norm_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.correlation_id IS DISTINCT FROM NEW.correlation_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_correlation_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_start IS DISTINCT FROM NEW.window_start THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_dispatch_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.delivery_state IS DISTINCT FROM NEW.delivery_state THEN
                IF OLD.delivery_state = 'pending_publish'
                   AND NEW.delivery_state = 'published' THEN
                    NULL;
                ELSIF OLD.delivery_state = 'published'
                   AND NEW.delivery_state = 'conducted' THEN
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b26_p2_dispatch_delivery_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI anchor law.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_dispatch_immutability'
            ) THEN
                DROP TRIGGER trg_b26_p2_dispatch_immutability
                    ON public.b23_match_task_dispatches;
            END IF;
            CREATE TRIGGER trg_b26_p2_dispatch_immutability
            BEFORE UPDATE ON public.b23_match_task_dispatches
            FOR EACH ROW EXECUTE FUNCTION
                public.b26_p2_enforce_dispatch_immutability();
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI trigger scope.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches"
        " DROP COLUMN IF EXISTS first_published_at"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI progress anchor.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_canonical_day_end(timestamptz)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI canonical window.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_canonical_day_start(timestamptz)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI canonical window.
    )
    # VI-source quarantine rows cannot satisfy the restored V CHECK:
    # fail closed (explicit operator disposition) instead of silently
    # dropping provenance. RLS is disabled for the guard read exactly as
    # in the upgrade census: the migrating principal holds no tenant GUC
    # and a bare count would match zero rows SILENTLY, passing vacuously
    # and failing later at the CHECK with a raw constraint violation.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        DECLARE _n integer := 0;
        BEGIN
            SELECT count(*) INTO _n
            FROM public.b26_p2_execution_quarantine AS q
            WHERE q.source_relation IN (
                'b23_match_task_dispatches', 'b26_p2_conduction_receipts');
            IF _n <> 0 THEN
                RAISE EXCEPTION 'b26_p2_vi_quarantine_not_downgradable:%', _n;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_quarantine FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine"
        " DROP CONSTRAINT IF EXISTS ck_b26_p2_quarantine_source"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI quarantine sources.
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_quarantine
            ADD CONSTRAINT ck_b26_p2_quarantine_source
            CHECK (source_relation IN (
                'b26_p2_execution_outbox',
                'b26_p2_task_authority_directory'
            ))
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective VI quarantine sources.
    )
