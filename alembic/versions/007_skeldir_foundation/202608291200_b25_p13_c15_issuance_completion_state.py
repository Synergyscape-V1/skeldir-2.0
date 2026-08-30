"""B2.5-P13 C15: separate authorised issuance from completed cryptographic issuance.

Revision ID: 202608291200
Revises: 202608271200

Corrective XV, H-XV-02/H-XV-03.

Before this migration ``trust_access_log`` had exactly one terminal shape for an
issuance request: ``event_type='issuance', status='success'``, written in an
independent committed transaction *before* the capability was minted and long
before P8 produced a signature. Forcing the signer to fail after that commit was
shown, against live PostgreSQL over a real authenticated HTTP journey, to leave
two rows claiming ``issuance/success`` -- each carrying an ``envelope_hash`` --
when only one envelope had ever been signed. Durable history therefore
overstated physical completion, violating ``AUDIT HISTORY = PHYSICAL EVENT
HISTORY``.

The correction separates the two facts rather than renaming one of them:

* ``status`` keeps its existing meaning and its existing value. It is part of
  the audited material that feeds ``audit_hash``, which is itself bound into the
  signed envelope, so changing it would silently reinterpret every envelope
  already issued. It is preserved byte-for-byte.
* ``issuance_state`` is the new physical-completion fact:
  ``authorized`` -> the claim passed P5/P7 and a capability may be minted;
  ``issued``     -> a signature physically exists;
  ``failed``     -> issuance was abandoned after authorisation.

``ck_trust_access_log_issued_requires_crypto`` makes the database itself refuse
to record completed issuance without cryptographic evidence, so the invariant is
enforced by physics rather than by application discipline. A future code path
that forgets to finalise cannot fabricate a completed-issuance row, and one that
tries to claim completion without a signature is rejected by PostgreSQL.
"""

from __future__ import annotations

from alembic import op


revision = "202608291200"
down_revision = "202608271200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD COLUMN issuance_state text NOT NULL DEFAULT 'authorized',
            ADD COLUMN issued_at timestamptz,
            ADD COLUMN issued_signing_key_id text,
            ADD COLUMN issued_signature_hash text
        """
    )
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state CHECK (
                issuance_state IN ('authorized', 'issued', 'failed', 'not_applicable')
            )
        """
    )
    # Non-issuance events (refusal, scope_denial, replay) never reach a signer,
    # so they carry an explicit terminal marker rather than a misleading
    # 'authorized'.
    #
    # trust_access_log runs FORCE ROW LEVEL SECURITY, which subjects even the
    # table owner to its tenant policies. A backfill executed as the
    # least-privilege migration principal with no app.current_tenant_id set
    # therefore matches zero rows, while the CHECK constraint added immediately
    # below still validates every row -- so the migration would fail on any
    # database that already holds audit history. FORCE is lifted for the
    # backfill and restored immediately, the same idiom used by
    # 202512171500_force_rls_recompute_jobs and
    # 202602281100_b12_p2_users_registry_least_privilege.
    op.execute("ALTER TABLE public.trust_access_log NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE public.trust_access_log
        SET issuance_state = 'not_applicable'
        WHERE event_type <> 'issuance'
        """
    )
    op.execute("ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state_event CHECK (
                (event_type = 'issuance' AND issuance_state <> 'not_applicable')
                OR (event_type <> 'issuance' AND issuance_state = 'not_applicable')
            )
        """
    )
    # The physical law: history may not claim a completed cryptographic issuance
    # unless the cryptographic evidence of that issuance is present.
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (
                issuance_state <> 'issued'
                OR (
                    issued_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND envelope_hash IS NOT NULL
                )
            )
        """
    )
    # Symmetrically, an unfinished or abandoned issuance may not carry
    # cryptographic evidence it never produced.
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_unissued_has_no_crypto CHECK (
                issuance_state = 'issued'
                OR (
                    issued_at IS NULL
                    AND issued_signing_key_id IS NULL
                    AND issued_signature_hash IS NULL
                )
            )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_trust_access_log_issuance_state
            ON public.trust_access_log (tenant_id, issuance_state)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_trust_access_log_issuance_state")
    for constraint in (
        "ck_trust_access_log_unissued_has_no_crypto",
        "ck_trust_access_log_issued_requires_crypto",
        "ck_trust_access_log_issuance_state_event",
        "ck_trust_access_log_issuance_state",
    ):
        op.execute(
            f"ALTER TABLE public.trust_access_log DROP CONSTRAINT IF EXISTS {constraint}"
        )
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            DROP COLUMN IF EXISTS issued_signature_hash,
            DROP COLUMN IF EXISTS issued_signing_key_id,
            DROP COLUMN IF EXISTS issued_at,
            DROP COLUMN IF EXISTS issuance_state
        """
    )
