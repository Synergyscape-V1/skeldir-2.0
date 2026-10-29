"""B2.6-P2 Corrective XXV: sovereign source-money attestation.

Revision ID: 202610270001
Revises: 202610180003

Closes the XXV boundary falsifiers A6/A10/A12, whose root cause is that every
pre-XXV protection over the provider's amount lived inside objects owned by
``migration_owner``:

* ``b26_p2_enforce_verdict_money_authority`` returns NEW for
  ``session_user = 'postgres'``, for any member of ``migration_owner`` and for
  the relation owner, so it cannot constrain the principal both independent
  audits used;
* ``NO FORCE ROW LEVEL SECURITY``, ``DISABLE TRIGGER USER`` and
  ``CREATE OR REPLACE FUNCTION`` are all owner capabilities;
* ``b26_p2_verify_source_money_conservation`` compares rows that the same
  owner may rewrite, so an internally coherent false world stays coherent.

This revision adds the storage for an authority that does NOT live inside the
owner's reach: a statement over the authenticated amount, signed by the
authentication root with an Ed25519 seed mounted only into that process, and
verified by every reader against a public-key fingerprint compiled into the
deployed image. The owner may rewrite or delete these rows and gains nothing:
it cannot produce a signature for an amount the provider never sent, and it
cannot rebuild the compiled anchor in the running image.

There is deliberately no watermark, epoch or "predecessor generation" table.
Such a table would let the owner decide whether a row's money counts as
authoritative by writing the instant the reader compares against, which is
the same class of bypass this revision exists to close. Rows that cannot be
attested are reported as unqualified; they are never presented as current
finance on the strength of an instant the owner can move.
"""

from __future__ import annotations

from alembic import op

revision = "202610270001"
down_revision = "202610180003"
branch_labels = None
depends_on = None


def _grant(statement: str, role: str) -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
        " WHERE rolname = '%s') THEN EXECUTE '%s'; END IF; END $$;"
        % (role, statement.replace("'", "''"))
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # XXV-1. The attestation record. One row per authenticated ingress
    # identity, authored by the authentication root inside the same
    # transaction that persists the authenticated row.
    #
    # The signature is the authority; the row is only its carrier. That is
    # why no trigger here tries to stop the owner from editing the row: a
    # trigger cannot constrain the owner, and it does not need to, because
    # an edited row fails verification in every reader.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_source_money_attestation (
            webhook_ingress_identity_id uuid PRIMARY KEY
                REFERENCES public.webhook_ingress_identities(id)
                ON DELETE CASCADE,
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            statement_version integer NOT NULL,
            attested_amount_minor integer NOT NULL,
            attested_amount_currency character(3) NOT NULL,
            attested_amount_scale integer NOT NULL,
            statement jsonb NOT NULL,
            signature text NOT NULL,
            key_id text NOT NULL,
            key_sha256 text NOT NULL,
            attested_by name NOT NULL DEFAULT session_user,
            attested_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b26_p2_attestation_amount_nonneg
                CHECK (attested_amount_minor >= 0),
            CONSTRAINT ck_b26_p2_attestation_signature_shape
                CHECK (signature LIKE 'ed25519:%'),
            CONSTRAINT ck_b26_p2_attestation_key_sha256_shape
                CHECK (key_sha256 ~ '^[0-9a-f]{64}$'),
            CONSTRAINT ck_b26_p2_attestation_version_known
                CHECK (statement_version >= 1)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS"
        " idx_b26_p2_source_money_attestation_tenant"
        " ON public.b26_p2_source_money_attestation (tenant_id, attested_at DESC)"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_source_money_attestation"
        " ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_source_money_attestation"
        " FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_b26_p2_source_money_attestation"
        " ON public.b26_p2_source_money_attestation"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_b26_p2_source_money_attestation
            ON public.b26_p2_source_money_attestation
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (
                tenant_id = current_setting('app.current_tenant_id')::uuid
            )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_source_money_attestation FROM PUBLIC"
    )
    # Only the authentication root may author an attestation. Every other
    # runtime principal reads.
    _grant(
        "GRANT INSERT, SELECT ON TABLE"
        " public.b26_p2_source_money_attestation TO app_ingress",
        "app_ingress",
    )
    for role in ("app_user", "app_worker", "app_trust_issuer", "app_ro", "app_relay"):
        _grant(
            "GRANT SELECT ON TABLE"
            " public.b26_p2_source_money_attestation TO %s" % role,
            role,
        )

    # ------------------------------------------------------------------
    # XXV-2. There is deliberately NO watermark table.
    #
    # An earlier revision of this migration created
    # ``public.b26_p2_source_attestation_authority`` holding an
    # "attestation_required_from" instant, and every reader granted a
    # "predecessor generation" exemption to a row that had no attestation
    # and was created before that instant. That was an owner-controlled
    # bypass of the only authority the database frame cannot forge: the
    # maintenance principal owns the attestation table (so it can DELETE the
    # row the authentication root wrote) and it owned the watermark table
    # (so it could move the instant), and it can rewrite the row's
    # ``created_at``. Deleting the attestation and moving the watermark was
    # enough to have a coherently forged amount served as ``current`` by the
    # unsigned reader while the mandatory composition proof printed PASS.
    #
    # The physical evidence is falsifier ``xxv-hb03-predecessor-escape``
    # (RED on the candidate artifact, then GREEN after this correction). The
    # exemption is removed rather than hardened, because no instant stored
    # in a table this principal owns can decide whether an amount is
    # authoritative. Money authenticated before the XXV epoch therefore
    # cannot be provider-attested at all -- the provider's signed bytes are
    # not retained -- and is reported as unqualified rather than as current
    # finance. That residual is a DEVIATION-FOR-AUDIT, not a disposition.
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # XXV-3. The authentication root binds each attestation to this
    # database's authority universe, so an attestation lifted into a cloned
    # universe is not evidence there. It reads the universe through the
    # existing DEFINER reader (the table itself stays unreadable to every
    # runtime principal), which until now was granted to every reader
    # except the root that has to sign.
    # ------------------------------------------------------------------
    _grant(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_authority_universe()"
        " TO app_ingress",
        "app_ingress",
    )


def downgrade() -> None:
    # XXV follows the XXIV downgrade law for a rollback to the immediate
    # predecessor: a downgrade revokes reach but does not destroy signed
    # authority records. A downgrade BELOW XXV, however, must remove the
    # XXV-only table: its foreign key to webhook_ingress_identities otherwise
    # prevents a legitimate downgrade through the auth-substrate revisions
    # from dropping that predecessor table. Re-upgrade recreates the empty
    # table; historical rows then read `unverifiable`, never as re-minted
    # authority.
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_source_money_attestation FROM PUBLIC"
    )
    op.execute("DROP TABLE IF EXISTS public.b26_p2_source_money_attestation CASCADE")
