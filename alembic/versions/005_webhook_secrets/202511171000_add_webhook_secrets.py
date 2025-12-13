"""Add per-tenant webhook secrets for vendor signature verification

Revision ID: 202511171000
Revises: 202511141311
Create Date: 2025-11-17 10:00:00

Purpose:
    - Introduce per-tenant webhook secrets for Shopify, Stripe, PayPal, WooCommerce.
    - Support B0.4.5 webhook ingress with tenant-scoped signature validation.

Notes:
    - Columns are nullable to avoid breaking existing tenants; operational flows
      must populate secrets before enabling webhook ingestion.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "202511171000"
down_revision: Union[str, None] = "202512081510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("shopify_webhook_secret", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("stripe_webhook_secret", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("paypal_webhook_secret", sa.Text(), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("woocommerce_webhook_secret", sa.Text(), nullable=True),
    )

    op.execute(
        """
        COMMENT ON COLUMN tenants.shopify_webhook_secret IS
        'Tenant-scoped Shopify webhook signing secret. Used for HMAC verification.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN tenants.stripe_webhook_secret IS
        'Tenant-scoped Stripe webhook signing secret. Used for signature verification.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN tenants.paypal_webhook_secret IS
        'Tenant-scoped PayPal webhook signing secret. Used for signature verification.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN tenants.woocommerce_webhook_secret IS
        'Tenant-scoped WooCommerce webhook signing secret. Used for HMAC verification.'
        """
    )


def downgrade() -> None:
    op.drop_column("tenants", "woocommerce_webhook_secret")
    op.drop_column("tenants", "paypal_webhook_secret")
    op.drop_column("tenants", "stripe_webhook_secret")
    op.drop_column("tenants", "shopify_webhook_secret")
