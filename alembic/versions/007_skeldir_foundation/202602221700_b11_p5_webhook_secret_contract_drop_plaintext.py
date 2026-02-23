"""B1.1-P5: Tenant webhook secret redesign (contract phase).

Revision ID: 202602221700
Revises: 202602221630
Create Date: 2026-02-22 17:00:00
"""

from __future__ import annotations

import json
import os
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "202602221700"
down_revision: Union[str, None] = "202602221630"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROVIDERS = ("shopify", "stripe", "paypal", "woocommerce")


def _resolve_platform_encryption_material() -> tuple[str, str]:
    raw = (os.getenv("PLATFORM_TOKEN_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise RuntimeError(
            "B1.1-P5 contract migration requires PLATFORM_TOKEN_ENCRYPTION_KEY to be present"
        )

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        keys = payload.get("keys")
        current_key_id = str(payload.get("current_key_id") or "").strip()
        if not isinstance(keys, dict) or not current_key_id:
            raise RuntimeError(
                "PLATFORM_TOKEN_ENCRYPTION_KEY key-ring payload missing current_key_id/keys"
            )
        current_key = str(keys.get(current_key_id) or "").strip()
        if not current_key:
            raise RuntimeError(
                "PLATFORM_TOKEN_ENCRYPTION_KEY key-ring payload missing current key material"
            )
        return current_key_id, current_key

    current_key_id = (os.getenv("PLATFORM_TOKEN_KEY_ID") or "legacy-default").strip()
    if not current_key_id:
        current_key_id = "legacy-default"
    return current_key_id, raw


def upgrade() -> None:
    bind = op.get_bind()
    current_key_id, current_key = _resolve_platform_encryption_material()

    # Final safety backfill before plaintext contract drop.
    for provider in PROVIDERS:
        bind.execute(
            text(
                f"""
                UPDATE public.tenants
                SET
                  {provider}_webhook_secret_ciphertext = pgp_sym_encrypt({provider}_webhook_secret, :current_key),
                  {provider}_webhook_secret_key_id = :current_key_id
                WHERE {provider}_webhook_secret IS NOT NULL
                  AND btrim({provider}_webhook_secret) <> ''
                  AND (
                    {provider}_webhook_secret_ciphertext IS NULL
                    OR {provider}_webhook_secret_key_id IS NULL
                  )
                """
            ),
            {"current_key": current_key, "current_key_id": current_key_id},
        )

    op.execute("DROP FUNCTION IF EXISTS security.resolve_tenant_webhook_secrets(text)")
    op.execute(
        """
        CREATE FUNCTION security.resolve_tenant_webhook_secrets(api_key_hash text)
        RETURNS TABLE (
          tenant_id uuid,
          tenant_updated_at timestamptz,
          shopify_webhook_secret_ciphertext bytea,
          shopify_webhook_secret_key_id text,
          stripe_webhook_secret_ciphertext bytea,
          stripe_webhook_secret_key_id text,
          paypal_webhook_secret_ciphertext bytea,
          paypal_webhook_secret_key_id text,
          woocommerce_webhook_secret_ciphertext bytea,
          woocommerce_webhook_secret_key_id text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT
            t.id AS tenant_id,
            t.updated_at AS tenant_updated_at,
            t.shopify_webhook_secret_ciphertext,
            t.shopify_webhook_secret_key_id,
            t.stripe_webhook_secret_ciphertext,
            t.stripe_webhook_secret_key_id,
            t.paypal_webhook_secret_ciphertext,
            t.paypal_webhook_secret_key_id,
            t.woocommerce_webhook_secret_ciphertext,
            t.woocommerce_webhook_secret_key_id
          FROM public.tenants t
          WHERE t.api_key_hash = $1
          LIMIT 1
        $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION security.resolve_tenant_webhook_secrets(text) FROM PUBLIC"
    )
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

    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS shopify_webhook_secret")  # CI:DESTRUCTIVE_OK - B1.1-P5 contract drop
    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS stripe_webhook_secret")  # CI:DESTRUCTIVE_OK - B1.1-P5 contract drop
    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS paypal_webhook_secret")  # CI:DESTRUCTIVE_OK - B1.1-P5 contract drop
    op.execute("ALTER TABLE public.tenants DROP COLUMN IF EXISTS woocommerce_webhook_secret")  # CI:DESTRUCTIVE_OK - B1.1-P5 contract drop


def downgrade() -> None:
    for provider in PROVIDERS:
        op.execute(
            text(
                f"""
                ALTER TABLE public.tenants
                ADD COLUMN IF NOT EXISTS {provider}_webhook_secret TEXT
                """
            )
        )
    op.execute("DROP FUNCTION IF EXISTS security.resolve_tenant_webhook_secrets(text)")
    op.execute(
        """
        CREATE FUNCTION security.resolve_tenant_webhook_secrets(api_key_hash text)
        RETURNS TABLE (
          tenant_id uuid,
          tenant_updated_at timestamptz,
          shopify_webhook_secret text,
          stripe_webhook_secret text,
          paypal_webhook_secret text,
          woocommerce_webhook_secret text,
          shopify_webhook_secret_ciphertext bytea,
          shopify_webhook_secret_key_id text,
          stripe_webhook_secret_ciphertext bytea,
          stripe_webhook_secret_key_id text,
          paypal_webhook_secret_ciphertext bytea,
          paypal_webhook_secret_key_id text,
          woocommerce_webhook_secret_ciphertext bytea,
          woocommerce_webhook_secret_key_id text
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = pg_catalog, public
        AS $$
          SELECT
            t.id AS tenant_id,
            t.updated_at AS tenant_updated_at,
            t.shopify_webhook_secret,
            t.stripe_webhook_secret,
            t.paypal_webhook_secret,
            t.woocommerce_webhook_secret,
            t.shopify_webhook_secret_ciphertext,
            t.shopify_webhook_secret_key_id,
            t.stripe_webhook_secret_ciphertext,
            t.stripe_webhook_secret_key_id,
            t.paypal_webhook_secret_ciphertext,
            t.paypal_webhook_secret_key_id,
            t.woocommerce_webhook_secret_ciphertext,
            t.woocommerce_webhook_secret_key_id
          FROM public.tenants t
          WHERE t.api_key_hash = $1
          LIMIT 1
        $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION security.resolve_tenant_webhook_secrets(text) FROM PUBLIC"
    )
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
