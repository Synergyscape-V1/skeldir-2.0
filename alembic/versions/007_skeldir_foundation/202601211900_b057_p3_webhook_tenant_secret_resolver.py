"""B0.5.7-P3: Mediate webhook tenant secret resolution via SECURITY DEFINER.

Revision ID: 202601211900
Revises: 202601131610
Create Date: 2026-01-21 19:00:00

Motivation:
- Runtime DB identity must not require direct SELECT on public.tenants.
- Webhook ingress must still resolve tenant_id + per-vendor webhook secrets.

Approach:
- Create schema `security` (if missing).
- Add `security.resolve_tenant_webhook_secrets(api_key_hash text)` as SECURITY DEFINER.
- Grant EXECUTE on the function (and USAGE on schema) to runtime roles.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202601211900"
down_revision: Union[str, None] = "202601131610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS security")
    op.execute("DROP FUNCTION IF EXISTS security.resolve_tenant_webhook_secrets(text)")

    op.execute(
        """
        CREATE FUNCTION security.resolve_tenant_webhook_secrets(api_key_hash text)
        RETURNS TABLE (
          tenant_id uuid,
          shopify_webhook_secret text,
          stripe_webhook_secret text,
          paypal_webhook_secret text,
          woocommerce_webhook_secret text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT
            t.id AS tenant_id,
            t.shopify_webhook_secret,
            t.stripe_webhook_secret,
            t.paypal_webhook_secret,
            t.woocommerce_webhook_secret
          FROM public.tenants t
          WHERE t.api_key_hash = $1
          LIMIT 1
        $$;
        """
    )

    # Prevent accidental exposure through PUBLIC.
    op.execute(
        "REVOKE ALL ON FUNCTION security.resolve_tenant_webhook_secrets(text) FROM PUBLIC"
    )

    # Runtime roles: allow mediated access only.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT USAGE ON SCHEMA security TO app_user;
            GRANT EXECUTE ON FUNCTION security.resolve_tenant_webhook_secrets(text) TO app_user;
          END IF;

          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
            GRANT USAGE ON SCHEMA security TO app_rw;
            GRANT EXECUTE ON FUNCTION security.resolve_tenant_webhook_secrets(text) TO app_rw;
          END IF;

          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ro') THEN
            GRANT USAGE ON SCHEMA security TO app_ro;
            GRANT EXECUTE ON FUNCTION security.resolve_tenant_webhook_secrets(text) TO app_ro;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS security.resolve_tenant_webhook_secrets(text)")
