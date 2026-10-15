"""B2.6-P2 family-law v4: narrow the Shopify creation moment to 60 s.

ADD2-VF1/A.1 proved forged nonterminal shapes (+90/+120/+240 s updates)
reach verified financial scope end to end under the v3 300 s window:
inside it the HMAC-uncovered topic confers creation family on bodies
that positively read as creations everywhere except their update skew.
Genuine creates carry coincident instants from the same Shopify
transaction; any material update skew marks a restated obligation, and
the tenant-held webhook secret makes every body byte forgeable, so the
unsigned topic cannot rehabilitate it.

This revision narrows the creation-moment bound 300 s -> 60 s in BOTH
enforcement layers (Python derive_shopify_lifecycle via
SHOPIFY_CREATION_SKEW_SECONDS, and this database admission function),
and publishes family-law v4 (contract version bump per the versioning
law; v3 rows keep bound values; the (60,300]s band is cohort-qualified
by activation revision because raw bodies never persist and lifecycle
instants are transient, so the band is unidentifiable row-wise; the
(0,60]s adaptive residual goes to the auditors as DEVIATION-FOR-AUDIT).

No money-state mutation: no verdict, ingress, ledger or consequence
row is touched. Owner-context INSERT of the publication row is admitted
by the history immutability trigger's sovereign-writer rule.

Downgrade restores the 300 s bound; the v4 publication row is
retained (history immutability trigger refuses UPDATE/DELETE;
downgraded lanes re-admit the v3 window -- fail-open relative to v4,
documented).
"""

from __future__ import annotations

from alembic import op

revision = "202609300007"
down_revision = "202609300006"


def upgrade() -> None:
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
    -- XXI (H-XXI-03): lifecycle admission is enforced at the minting
    -- seam, not just in Python derivation. Terminal lifecycle markers
    -- are never creation-family evidence, for any provider: a
    -- cancelled or refunded body cannot found current authority even
    -- when every other check passes (defense in depth behind the
    -- derivation layer, which refuses these shapes first).
    IF p_cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
            USING ERRCODE = '42501';
    END IF;
    IF COALESCE(p_refunds_present, false) THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
            USING ERRCODE = '42501';
    END IF;
    -- Positive Shopify creation law: the transported topic asserts
    -- creation, but only a body that positively reads as a creation
    -- earns it. At mint time (p_require_creation_proof) the moments
    -- and status must be fully present; at re-attestation only
    -- positive contradictions refuse (the original mint already
    -- established the creation; unknown fields cannot).
    IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, ''))) = 'shopify'
       AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
           = 'orders.create' THEN
        IF p_require_creation_proof THEN
            IF p_financial_status IS NULL
               OR lower(public.b26_p2_ascii_strip(p_financial_status))
                  NOT IN ('pending', 'authorized', 'paid',
                          'partially_paid') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF abs(extract(epoch FROM (p_updated_at - p_created_at))) > 60 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        ELSE
            IF p_financial_status IS NOT NULL
               AND lower(public.b26_p2_ascii_strip(p_financial_status))
                   NOT IN ('pending', 'authorized', 'paid',
                           'partially_paid', 'voided', 'refunded',
                           'partially_refunded') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL
               AND abs(extract(epoch FROM (p_updated_at - p_created_at)))
                   > 60 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
    END IF;
    RETURN;
END $$;

        """
    )
    op.execute(
        """
        INSERT INTO public.b26_p2_publication_history AS h (law_kind, law_id, law_version, law_digest, activation_revision, prev_entry_hash, entry_hash)
        VALUES ('event-family-law', 'b26-p2-event-family-law', 'v4', '355308b1c4de48e6fcac373c7c6fe3accdfe232bd13fb8cd863c8b6ac017e720', '202609300007', '0b99e1e84d44eb1d68977c611a3d38035fce5c04af33933fb42bb278b1b81162', '200dfb55d0f702b5fbde2555f00e0d5d7c6f29ff1d62969b3a30ac6b1140bb1e')
        ON CONFLICT ON CONSTRAINT b26_p2_publication_identity_single_valued DO NOTHING;
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
    -- XXI (H-XXI-03): lifecycle admission is enforced at the minting
    -- seam, not just in Python derivation. Terminal lifecycle markers
    -- are never creation-family evidence, for any provider: a
    -- cancelled or refunded body cannot found current authority even
    -- when every other check passes (defense in depth behind the
    -- derivation layer, which refuses these shapes first).
    IF p_cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
            USING ERRCODE = '42501';
    END IF;
    IF COALESCE(p_refunds_present, false) THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
            USING ERRCODE = '42501';
    END IF;
    -- Positive Shopify creation law: the transported topic asserts
    -- creation, but only a body that positively reads as a creation
    -- earns it. At mint time (p_require_creation_proof) the moments
    -- and status must be fully present; at re-attestation only
    -- positive contradictions refuse (the original mint already
    -- established the creation; unknown fields cannot).
    IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, ''))) = 'shopify'
       AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
           = 'orders.create' THEN
        IF p_require_creation_proof THEN
            IF p_financial_status IS NULL
               OR lower(public.b26_p2_ascii_strip(p_financial_status))
                  NOT IN ('pending', 'authorized', 'paid',
                          'partially_paid') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF abs(extract(epoch FROM (p_updated_at - p_created_at))) > 300 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        ELSE
            IF p_financial_status IS NOT NULL
               AND lower(public.b26_p2_ascii_strip(p_financial_status))
                   NOT IN ('pending', 'authorized', 'paid',
                           'partially_paid', 'voided', 'refunded',
                           'partially_refunded') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL
               AND abs(extract(epoch FROM (p_updated_at - p_created_at)))
                   > 300 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
    END IF;
    RETURN;
END $$;

        """
    )
