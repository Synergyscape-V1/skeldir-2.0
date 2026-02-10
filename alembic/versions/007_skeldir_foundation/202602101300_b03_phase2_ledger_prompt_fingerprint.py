"""B0.3 Phase 2: prompt fingerprints + append-only audit privileges.

Revision ID: 202602101300
Revises: 202602071100
Create Date: 2026-02-10 13:00:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602101300"
down_revision: Union[str, None] = "202602071100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Prompt persistence default: store deterministic fingerprint, not raw prompt text.
    op.execute("ALTER TABLE llm_api_calls ADD COLUMN prompt_fingerprint TEXT")
    op.execute(
        """
        UPDATE llm_api_calls
        SET prompt_fingerprint = md5(
            COALESCE(request_metadata_ref::text, '')
            || '|'
            || COALESCE(endpoint, '')
            || '|'
            || COALESCE(request_id, '')
        )
        WHERE prompt_fingerprint IS NULL
        """
    )
    op.execute("ALTER TABLE llm_api_calls ALTER COLUMN prompt_fingerprint SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_api_calls_prompt_fingerprint "
        "ON llm_api_calls (tenant_id, prompt_fingerprint, created_at DESC)"
    )

    op.execute("ALTER TABLE llm_call_audit ADD COLUMN prompt_fingerprint TEXT")
    op.execute(
        """
        UPDATE llm_call_audit
        SET prompt_fingerprint = md5(
            COALESCE(request_id, '')
            || '|'
            || COALESCE(requested_model, '')
            || '|'
            || COALESCE(resolved_model, '')
        )
        WHERE prompt_fingerprint IS NULL
        """
    )
    op.execute("ALTER TABLE llm_call_audit ALTER COLUMN prompt_fingerprint SET NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_call_audit_prompt_fingerprint "
        "ON llm_call_audit (tenant_id, prompt_fingerprint, created_at DESC)"
    )

    # Enforce append-only posture on llm_call_audit at both privilege and trigger layers.
    op.execute("REVOKE UPDATE, DELETE ON TABLE llm_call_audit FROM app_rw")
    op.execute("GRANT SELECT, INSERT ON TABLE llm_call_audit TO app_rw")
    op.execute("REVOKE DELETE ON TABLE llm_api_calls FROM app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE llm_api_calls TO app_rw")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_llm_call_audit_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'llm_call_audit is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_llm_call_audit_append_only
        BEFORE UPDATE OR DELETE ON llm_call_audit
        FOR EACH ROW
        EXECUTE FUNCTION fn_llm_call_audit_append_only();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_llm_call_audit_append_only ON llm_call_audit")
    op.execute("DROP FUNCTION IF EXISTS fn_llm_call_audit_append_only")

    op.execute("DROP INDEX IF EXISTS idx_llm_call_audit_prompt_fingerprint")
    op.execute(
        "ALTER TABLE llm_call_audit DROP COLUMN IF EXISTS prompt_fingerprint"
    )  # CI:DESTRUCTIVE_OK - Downgrade removes Phase-2 additive column introduced in revision 202602101300.

    op.execute("DROP INDEX IF EXISTS idx_llm_api_calls_prompt_fingerprint")
    op.execute(
        "ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS prompt_fingerprint"
    )  # CI:DESTRUCTIVE_OK - Downgrade removes Phase-2 additive column introduced in revision 202602101300.
