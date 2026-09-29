"""B2.6-P2 Corrective XIV: temporal enforcement completeness hardening.

Revision ID: 202609270002
Revises: 202609270001

Closes two enforcement gaps the XIV behavioral matrix executes against:

1. Conducted verdict commerce-reference value changes
   (b23_match_verdicts.canonical_commerce_reference UPDATE_REFUSED).
   The conservation trigger refused presence flips and link moves on
   conducted lineages but permitted a present-to-present value rewrite.
   A conducted commerce reference is sovereign deterministic truth; any
   value change on a conducted lineage now fails closed with
   b26_p2_conducted_verdict_regression_refused. Non-conducted
   (B2.3-correctable) rows are unaffected.

2. Policy version immutability
   (b26_p2_scope_policy_authority.scope_policy_version VERSION_BOUND).
   The policy trigger refused semantic-sha mutation under a fixed
   version but permitted renaming the version itself. Policy versions
   are append-only governance: new versions arrive via INSERT, never
   via UPDATE. Any UPDATE of scope_policy_version now fails closed with
   b26_p2_policy_version_immutable_refused. The sha-mutation rule is
   unchanged.

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved.
"""

from __future__ import annotations

from alembic import op

revision = "202609270002"
down_revision = "202609270001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_verdict_temporal_conservation()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $function$
        DECLARE
            _tenant uuid;
            _ingress uuid;
            _old_qual boolean;
            _new_qual boolean;
            _link_moved boolean;
            _old_ref_present boolean;
            _new_ref_present boolean;
            _ref_presence_flipped boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                _tenant := NEW.tenant_id;
                _ingress := NEW.webhook_ingress_identity_id;
                _new_qual := NEW.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                IF _new_qual AND _ingress IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = _tenant
                           AND d.webhook_ingress_identity_id = _ingress
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_set_insert_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                _tenant := OLD.tenant_id;
                _ingress := OLD.webhook_ingress_identity_id;
                _old_qual := OLD.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                IF _old_qual AND _ingress IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = _tenant
                           AND d.webhook_ingress_identity_id = _ingress
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_verdict_immutable'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                _link_moved :=
                    (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id)
                    OR (OLD.tenant_id IS DISTINCT FROM NEW.tenant_id);
                _old_qual := OLD.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                _new_qual := NEW.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                _old_ref_present := public.b26_p2_ascii_strip(COALESCE(OLD.canonical_commerce_reference, '')) <> '';
                _new_ref_present := public.b26_p2_ascii_strip(COALESCE(NEW.canonical_commerce_reference, '')) <> '';
                _ref_presence_flipped := _old_ref_present IS DISTINCT FROM _new_ref_present;
                IF (_old_qual AND NOT _new_qual) OR (_old_qual AND _link_moved) THEN
                    IF OLD.webhook_ingress_identity_id IS NOT NULL THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = OLD.tenant_id
                               AND d.webhook_ingress_identity_id = OLD.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_verdict_regression_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                END IF;
                IF _new_qual AND NEW.webhook_ingress_identity_id IS NOT NULL
                   AND (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                        OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
                        OR (NOT _old_qual)) THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = NEW.tenant_id
                           AND d.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_verdict_identity_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                -- XIV: conducted commerce-reference value rewrite. Presence
                -- flips are refused below; a present-to-present value change
                -- on a conducted lineage is an equal violation of the
                -- UPDATE_REFUSED disposition and fails with the same
                -- regression law. Non-conducted (B2.3-correctable) rows are
                -- unaffected: the EXISTS test finds no conducted dispatch.
                IF OLD.canonical_commerce_reference IS DISTINCT FROM NEW.canonical_commerce_reference
                   AND _old_qual AND _new_qual
                   AND _old_ref_present AND _new_ref_present
                   AND NOT _link_moved THEN
                    IF OLD.webhook_ingress_identity_id IS NOT NULL THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = OLD.tenant_id
                               AND d.webhook_ingress_identity_id = OLD.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_verdict_regression_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                END IF;
                IF _ref_presence_flipped THEN
                    IF OLD.webhook_ingress_identity_id IS NOT NULL AND (_old_qual OR _new_qual) THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = OLD.tenant_id
                               AND d.webhook_ingress_identity_id = OLD.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_reference_presence_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                    IF NEW.webhook_ingress_identity_id IS NOT NULL AND (_old_qual OR _new_qual)
                       AND (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                            OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id) THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = NEW.tenant_id
                               AND d.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_reference_presence_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $function$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_policy_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                -- XIV: policy versions are append-only governance. New
                -- versions arrive via INSERT; renaming a version in place
                -- breaks the VERSION_BOUND disposition (receipts bind the
                -- version string) and fails closed.
                IF OLD.scope_policy_version IS DISTINCT FROM NEW.scope_policy_version THEN
                    RAISE EXCEPTION 'b26_p2_policy_version_immutable_refused'
                        USING ERRCODE = '42501';
                END IF;
                IF NEW.scope_policy_version IS NOT DISTINCT FROM OLD.scope_policy_version
                   AND (NEW.source_sha256 IS DISTINCT FROM OLD.source_sha256
                        OR NEW.semantic_sha256 IS DISTINCT FROM OLD.semantic_sha256) THEN
                    RAISE EXCEPTION 'b26_p2_policy_semantic_mutation_refused'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )


def downgrade() -> None:
    # Fail-closed: enforcement tightening is intentionally NOT rolled back.
    # A downgrade leaves the strict law in place; re-upgrade converges.
    pass
