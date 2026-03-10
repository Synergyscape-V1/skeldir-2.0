"""
Transient OAuth handshake session ORM model.

Stores tenant-scoped ephemeral authorize/callback state, including hashed state
nonce and optional encrypted PKCE verifier material.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


class OAuthHandshakeSession(Base, TenantMixin):
    __tablename__ = "oauth_handshake_sessions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    state_nonce_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    encrypted_pkce_verifier: Mapped[Optional[bytes]] = mapped_column(BYTEA, nullable=True)
    pkce_key_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    pkce_code_challenge: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pkce_code_challenge_method: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    redirect_uri: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    provider_session_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    terminal_reason: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    gc_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "state_nonce_hash",
            name="uq_oauth_handshake_sessions_tenant_state_hash",
        ),
        CheckConstraint(
            "status IN ('pending', 'consumed', 'expired', 'aborted')",
            name="ck_oauth_handshake_sessions_status_valid",
        ),
        CheckConstraint(
            "(status = 'consumed' AND consumed_at IS NOT NULL) OR "
            "(status <> 'consumed' AND consumed_at IS NULL)",
            name="ck_oauth_handshake_sessions_consumed_shape",
        ),
        CheckConstraint(
            "(encrypted_pkce_verifier IS NULL AND pkce_key_id IS NULL) OR "
            "(encrypted_pkce_verifier IS NOT NULL AND pkce_key_id IS NOT NULL)",
            name="ck_oauth_handshake_sessions_pkce_key_binding",
        ),
    )
