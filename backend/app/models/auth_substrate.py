"""
Privacy-safe auth substrate ORM models.

These models intentionally avoid raw PII fields (email/IP). Identity lookups use
opaque hashes and tenant-scoped membership joins.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserIdentity(Base):
    """Opaque user identity registry (no raw email/IP at rest)."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    login_identifier_hash: Mapped[str] = mapped_column(
        Text, nullable=False, unique=True
    )
    external_subject_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="password",
        server_default="password",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "auth_provider IN ('password', 'oauth_google', 'oauth_microsoft', 'oauth_github', 'sso')",
            name="ck_users_auth_provider_valid",
        ),
        CheckConstraint(
            "length(trim(login_identifier_hash)) > 0",
            name="ck_users_login_identifier_hash_not_empty",
        ),
    )


class Role(Base):
    """Role catalog used by tenant membership role assignments."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint("code = lower(code)", name="ck_roles_code_lowercase"),
        CheckConstraint("length(trim(code)) > 0", name="ck_roles_code_not_empty"),
    )


class TenantMembership(Base):
    """Tenant-scoped user membership binding."""

    __tablename__ = "tenant_memberships"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="active",
        server_default="active",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "user_id",
            name="uq_tenant_memberships_tenant_user",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            name="uq_tenant_memberships_id_tenant",
        ),
        CheckConstraint(
            "membership_status IN ('active', 'revoked')",
            name="ck_tenant_memberships_status_valid",
        ),
        Index(
            "idx_tenant_memberships_tenant_created_at",
            "tenant_id",
            "created_at",
        ),
        Index(
            "idx_tenant_memberships_user_created_at",
            "user_id",
            "created_at",
        ),
    )


class TenantMembershipRole(Base):
    """Tenant-scoped role assignment for a membership."""

    __tablename__ = "tenant_membership_roles"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    membership_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    role_code: Mapped[str] = mapped_column(
        Text,
        ForeignKey("roles.code", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "tenant_id"],
            ["tenant_memberships.id", "tenant_memberships.tenant_id"],
            ondelete="CASCADE",
            name="fk_tenant_membership_roles_membership_tenant",
        ),
        UniqueConstraint(
            "membership_id",
            "role_code",
            name="uq_tenant_membership_roles_membership_role",
        ),
        Index(
            "idx_tenant_membership_roles_tenant_created_at",
            "tenant_id",
            "created_at",
        ),
    )
