"""Governed Postgres-native artifact persistence for B2.4-P8."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.artifacts import (
    DEFAULT_P8_ARTIFACT_POLICY,
    P8_ALLOWED_ARTIFACT_TYPES,
    P8_ALLOWED_RETENTION_CLASSES,
    RETENTION_TTLS,
    ArtifactPolicy,
    artifact_sha256,
    encode_payload_bytes,
    validate_artifact_ref,
)
from app.bayesian.enums import ArtifactLifecycleStatus, Compression
from app.bayesian.exceptions import (
    BayesianArtifactNotFoundError,
    BayesianArtifactPolicyError,
    BayesianArtifactQuotaExceededError,
)
from app.bayesian.models import BayesianArtifact
from app.bayesian.tenant_context import assert_bound_tenant


@dataclass(frozen=True)
class ArtifactMetadata:
    """Payload-free artifact authority projection."""

    id: UUID
    tenant_id: UUID
    fit_id: UUID
    artifact_ref: str
    artifact_hash: str
    artifact_type: str
    storage_backend: str
    artifact_uri_internal: str
    artifact_size_bytes: int
    payload_byte_count: int
    compression: str | None
    retention_class: str
    lifecycle_status: str
    policy_version: str
    expires_at: datetime | None
    pruned_at: datetime | None
    pruned_reason: str | None
    pruned_metadata: dict[str, object]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ArtifactPayload:
    """Explicit payload accessor result for verification/download-only paths."""

    metadata: ArtifactMetadata
    payload_bytes: bytes | None


def artifact_metadata_select():
    """Return the canonical payload-free metadata projection."""

    return select(
        BayesianArtifact.id,
        BayesianArtifact.tenant_id,
        BayesianArtifact.fit_id,
        BayesianArtifact.artifact_ref,
        BayesianArtifact.artifact_hash,
        BayesianArtifact.artifact_type,
        BayesianArtifact.storage_backend,
        BayesianArtifact.artifact_uri_internal,
        BayesianArtifact.artifact_size_bytes,
        BayesianArtifact.payload_byte_count,
        BayesianArtifact.compression,
        BayesianArtifact.retention_class,
        BayesianArtifact.lifecycle_status,
        BayesianArtifact.policy_version,
        BayesianArtifact.expires_at,
        BayesianArtifact.pruned_at,
        BayesianArtifact.pruned_reason,
        BayesianArtifact.pruned_metadata,
        BayesianArtifact.created_at,
        BayesianArtifact.updated_at,
    )


def _metadata_from_mapping(row) -> ArtifactMetadata:
    return ArtifactMetadata(
        id=row["id"],
        tenant_id=row["tenant_id"],
        fit_id=row["fit_id"],
        artifact_ref=row["artifact_ref"],
        artifact_hash=row["artifact_hash"],
        artifact_type=row["artifact_type"],
        storage_backend=row["storage_backend"],
        artifact_uri_internal=row["artifact_uri_internal"],
        artifact_size_bytes=int(row["artifact_size_bytes"]),
        payload_byte_count=int(row["payload_byte_count"]),
        compression=row["compression"],
        retention_class=row["retention_class"],
        lifecycle_status=row["lifecycle_status"],
        policy_version=row["policy_version"],
        expires_at=row["expires_at"],
        pruned_at=row["pruned_at"],
        pruned_reason=row["pruned_reason"],
        pruned_metadata=dict(row["pruned_metadata"] or {}),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class BayesianArtifactRepository:
    """Tenant-scoped read/write wrapper for P8 artifact authority rows.

    Callers must use a session with `app.current_tenant_id` already set.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_metadata_by_ref(
        self, *, tenant_id: UUID, artifact_ref: str
    ) -> ArtifactMetadata:
        stmt = artifact_metadata_select().where(
            BayesianArtifact.tenant_id == tenant_id,
            BayesianArtifact.artifact_ref == artifact_ref,
        )
        result = await self._session.execute(stmt)
        row = result.mappings().one_or_none()
        if row is None:
            raise BayesianArtifactNotFoundError(
                f"bayesian artifact not found: {artifact_ref}"
            )
        return _metadata_from_mapping(row)

    async def get_by_ref(
        self, *, tenant_id: UUID, artifact_ref: str
    ) -> ArtifactMetadata:
        return await self.get_metadata_by_ref(
            tenant_id=tenant_id,
            artifact_ref=artifact_ref,
        )

    async def get_payload_by_ref(
        self, *, tenant_id: UUID, artifact_ref: str
    ) -> ArtifactPayload:
        metadata = await self.get_metadata_by_ref(
            tenant_id=tenant_id,
            artifact_ref=artifact_ref,
        )
        result = await self._session.execute(
            select(BayesianArtifact.payload_bytes).where(
                BayesianArtifact.tenant_id == tenant_id,
                BayesianArtifact.artifact_ref == artifact_ref,
            )
        )
        return ArtifactPayload(
            metadata=metadata,
            payload_bytes=result.scalar_one_or_none(),
        )


def _json_param(payload: dict[str, object] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _expires_at(retention_class: str, now: datetime) -> datetime | None:
    ttl = RETENTION_TTLS[retention_class]
    return None if ttl is None else now + ttl


def _artifact_ref(
    *, tenant_id: UUID, fit_id: UUID, artifact_type: str, artifact_hash: str
) -> str:
    return f"b24://artifact/{tenant_id}/{fit_id}/{artifact_type}/{artifact_hash[:12]}"


def _ensure_quota_row(
    conn: Connection,
    *,
    tenant_id: UUID,
    policy: ArtifactPolicy,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO public.bayesian_artifact_storage_quotas (
                tenant_id,
                policy_version,
                quota_bytes,
                max_artifact_count,
                active_bytes,
                pruned_bytes,
                active_artifact_count,
                pruned_artifact_count,
                rejected_count
            )
            VALUES (
                :tenant_id,
                :policy_version,
                :quota_bytes,
                :max_artifact_count,
                0,
                0,
                0,
                0,
                0
            )
            ON CONFLICT (tenant_id)
            DO UPDATE SET
                policy_version = EXCLUDED.policy_version,
                quota_bytes = LEAST(
                    bayesian_artifact_storage_quotas.quota_bytes,
                    EXCLUDED.quota_bytes
                ),
                max_artifact_count = LEAST(
                    bayesian_artifact_storage_quotas.max_artifact_count,
                    EXCLUDED.max_artifact_count
                ),
                updated_at = now()
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "policy_version": policy.policy_version,
            "quota_bytes": policy.default_tenant_quota_bytes,
            "max_artifact_count": policy.max_tenant_artifact_count,
        },
    )


def _reserve_quota(
    conn: Connection,
    *,
    tenant_id: UUID,
    size_bytes: int,
    policy: ArtifactPolicy,
) -> bool:
    _ensure_quota_row(conn, tenant_id=tenant_id, policy=policy)
    result = conn.execute(
        text(
            """
            UPDATE public.bayesian_artifact_storage_quotas
            SET active_bytes = active_bytes + :size_bytes,
                active_artifact_count = active_artifact_count + 1,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND active_bytes + :size_bytes <= quota_bytes
              AND active_bytes + :size_bytes <= :policy_quota_bytes
              AND active_artifact_count + 1 <= max_artifact_count
              AND active_artifact_count + 1 <= :policy_max_artifact_count
            RETURNING active_bytes, active_artifact_count
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "size_bytes": size_bytes,
            "policy_quota_bytes": policy.default_tenant_quota_bytes,
            "policy_max_artifact_count": policy.max_tenant_artifact_count,
        },
    ).scalar_one_or_none()
    return result is not None


def _release_quota_reservation(
    conn: Connection,
    *,
    tenant_id: UUID,
    size_bytes: int,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.bayesian_artifact_storage_quotas
            SET active_bytes = GREATEST(active_bytes - :size_bytes, 0),
                active_artifact_count = GREATEST(active_artifact_count - 1, 0),
                updated_at = now()
            WHERE tenant_id = :tenant_id
            """
        ),
        {"tenant_id": str(tenant_id), "size_bytes": size_bytes},
    )


def _register_quota_rejection(
    conn: Connection,
    *,
    tenant_id: UUID,
    reason: str,
    policy: ArtifactPolicy,
) -> None:
    _ensure_quota_row(conn, tenant_id=tenant_id, policy=policy)
    conn.execute(
        text(
            """
            UPDATE public.bayesian_artifact_storage_quotas
            SET rejected_count = rejected_count + 1,
                last_rejection_reason = :reason,
                updated_at = now()
            WHERE tenant_id = :tenant_id
            """
        ),
        {"tenant_id": str(tenant_id), "reason": reason},
    )


def _validate_fit_wal_budget(
    conn: Connection,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    size_bytes: int,
    policy: ArtifactPolicy,
) -> None:
    fit_exists = conn.execute(
        text(
            """
            SELECT id
            FROM public.bayesian_model_fits
            WHERE tenant_id = :tenant_id
              AND id = :fit_id
            """
        ),
        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
    ).scalar_one_or_none()
    if fit_exists is None:
        raise BayesianArtifactPolicyError("artifact fit authority row not found")
    existing_bytes = int(
        conn.execute(
            text(
                """
                SELECT COALESCE(SUM(artifact_size_bytes), 0)
                FROM public.bayesian_artifacts
                WHERE tenant_id = :tenant_id
                  AND fit_id = :fit_id
                  AND lifecycle_status = 'active'
                """
            ),
            {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
        ).scalar_one()
    )
    if existing_bytes + size_bytes > policy.max_artifact_wal_budget_bytes_per_fit:
        raise BayesianArtifactQuotaExceededError("fit artifact WAL budget exceeded")


def _persist_rejected_artifact_metadata(
    conn: Connection,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    artifact_ref: str,
    artifact_hash: str,
    artifact_type: str,
    size_bytes: int,
    retention_class: str,
    compression: str,
    rejection_reason: str,
    policy: ArtifactPolicy,
) -> dict[str, object]:
    metadata = {
        "rejection_reason": rejection_reason,
        "attempted_payload_byte_count": size_bytes,
        "policy_version": policy.policy_version,
    }
    row = conn.execute(
        text(
            """
                INSERT INTO public.bayesian_artifacts (
                    tenant_id,
                    fit_id,
                    artifact_ref,
                    artifact_hash,
                    artifact_type,
                    storage_backend,
                    artifact_uri_internal,
                    artifact_size_bytes,
                    payload_json,
                    payload_bytes,
                    payload_byte_count,
                    compression,
                    retention_class,
                    lifecycle_status,
                    policy_version,
                    pruned_metadata
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :artifact_ref,
                    :artifact_hash,
                    :artifact_type,
                    'postgres',
                    :artifact_ref,
                    :artifact_size_bytes,
                    NULL,
                    NULL,
                    0,
                    :compression,
                    :retention_class,
                    'rejected',
                    :policy_version,
                    CAST(:pruned_metadata AS jsonb)
                )
                RETURNING id
                """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "artifact_ref": artifact_ref,
            "artifact_hash": artifact_hash,
            "artifact_type": artifact_type,
            "artifact_size_bytes": size_bytes,
            "compression": compression,
            "retention_class": retention_class,
            "policy_version": policy.policy_version,
            "pruned_metadata": _json_param(metadata),
        },
    ).scalar_one()
    return {
        "artifact_id": str(row),
        "artifact_ref": artifact_ref,
        "artifact_hash": artifact_hash,
        "artifact_size_bytes": size_bytes,
        "idempotent_replay": False,
        "rejected": True,
        "rejection_reason": rejection_reason,
    }


def persist_artifact_sync(
    conn: Connection,
    *,
    tenant_id: UUID,
    fit_id: UUID,
    artifact_type: str,
    payload: dict[str, object],
    retention_class: str,
    compression: str = Compression.NONE.value,
    policy: ArtifactPolicy = DEFAULT_P8_ARTIFACT_POLICY,
) -> dict[str, object]:
    """Persist one bounded artifact and return its authority metadata.

    This is the only approved P8 durable artifact write path. It is idempotent
    for identical `(tenant_id, artifact_ref, artifact_hash)` writes.
    """

    assert_bound_tenant(conn, tenant_id=tenant_id)
    if artifact_type not in P8_ALLOWED_ARTIFACT_TYPES:
        raise BayesianArtifactPolicyError("artifact type is not P8-governed")
    if retention_class not in P8_ALLOWED_RETENTION_CLASSES:
        raise BayesianArtifactPolicyError("retention class is not P8-governed")
    stored_bytes, stored_hash = encode_payload_bytes(
        payload,
        compression=compression,
        policy=policy,
    )
    size_bytes = len(stored_bytes)
    artifact_ref = _artifact_ref(
        tenant_id=tenant_id,
        fit_id=fit_id,
        artifact_type=artifact_type,
        artifact_hash=stored_hash,
    )
    validate_artifact_ref(artifact_ref)
    existing = (
        conn.execute(
            text(
                """
            SELECT id, artifact_hash, artifact_size_bytes, lifecycle_status
            FROM public.bayesian_artifacts
            WHERE tenant_id = :tenant_id
              AND artifact_ref = :artifact_ref
            """
            ),
            {"tenant_id": str(tenant_id), "artifact_ref": artifact_ref},
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if existing["artifact_hash"] != stored_hash:
            raise BayesianArtifactPolicyError("artifact ref hash mismatch")
        if existing["lifecycle_status"] == ArtifactLifecycleStatus.REJECTED.value:
            return {
                "artifact_id": str(existing["id"]),
                "artifact_ref": artifact_ref,
                "artifact_hash": stored_hash,
                "artifact_size_bytes": int(existing["artifact_size_bytes"]),
                "idempotent_replay": True,
                "rejected": True,
                "rejection_reason": "tenant_quota_exceeded",
            }
        if existing["lifecycle_status"] != ArtifactLifecycleStatus.ACTIVE.value:
            raise BayesianArtifactPolicyError("pruned artifact ref cannot be rewritten")
        return {
            "artifact_id": str(existing["id"]),
            "artifact_ref": artifact_ref,
            "artifact_hash": stored_hash,
            "artifact_size_bytes": int(existing["artifact_size_bytes"]),
            "idempotent_replay": True,
            "rejected": False,
        }
    _validate_fit_wal_budget(
        conn,
        tenant_id=tenant_id,
        fit_id=fit_id,
        size_bytes=size_bytes,
        policy=policy,
    )
    if not _reserve_quota(
        conn, tenant_id=tenant_id, size_bytes=size_bytes, policy=policy
    ):
        rejection_reason = "tenant_quota_exceeded"
        _register_quota_rejection(
            conn,
            tenant_id=tenant_id,
            reason=rejection_reason,
            policy=policy,
        )
        return _persist_rejected_artifact_metadata(
            conn,
            tenant_id=tenant_id,
            fit_id=fit_id,
            artifact_ref=artifact_ref,
            artifact_hash=stored_hash,
            artifact_type=artifact_type,
            size_bytes=size_bytes,
            retention_class=retention_class,
            compression=compression,
            rejection_reason=rejection_reason,
            policy=policy,
        )
    now = datetime.now(timezone.utc)
    payload_json = payload if compression == Compression.NONE.value else None
    row = conn.execute(
        text(
            """
            INSERT INTO public.bayesian_artifacts (
                tenant_id,
                fit_id,
                artifact_ref,
                artifact_hash,
                artifact_type,
                storage_backend,
                artifact_uri_internal,
                artifact_size_bytes,
                payload_json,
                payload_bytes,
                payload_byte_count,
                compression,
                retention_class,
                lifecycle_status,
                policy_version,
                expires_at
            )
            VALUES (
                :tenant_id,
                :fit_id,
                :artifact_ref,
                :artifact_hash,
                :artifact_type,
                'postgres',
                :artifact_ref,
                :artifact_size_bytes,
                CAST(:payload_json AS jsonb),
                :payload_bytes,
                :payload_byte_count,
                :compression,
                :retention_class,
                'active',
                :policy_version,
                :expires_at
            )
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "artifact_ref": artifact_ref,
            "artifact_hash": stored_hash,
            "artifact_type": artifact_type,
            "artifact_size_bytes": size_bytes,
            "payload_json": _json_param(payload_json),
            "payload_bytes": stored_bytes,
            "payload_byte_count": size_bytes,
            "compression": compression,
            "retention_class": retention_class,
            "policy_version": policy.policy_version,
            "expires_at": _expires_at(retention_class, now),
        },
    ).scalar_one()
    return {
        "artifact_id": str(row),
        "artifact_ref": artifact_ref,
        "artifact_hash": stored_hash,
        "artifact_size_bytes": size_bytes,
        "idempotent_replay": False,
        "rejected": False,
    }


def verify_artifact_bytes_sync(
    conn: Connection,
    *,
    tenant_id: UUID,
    artifact_ref: str,
) -> bool:
    assert_bound_tenant(conn, tenant_id=tenant_id)
    row = (
        conn.execute(
            text(
                """
            SELECT artifact_hash, payload_bytes, lifecycle_status
            FROM public.bayesian_artifacts
            WHERE tenant_id = :tenant_id
              AND artifact_ref = :artifact_ref
            """
            ),
            {"tenant_id": str(tenant_id), "artifact_ref": artifact_ref},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise BayesianArtifactNotFoundError(
            f"bayesian artifact not found: {artifact_ref}"
        )
    if row["lifecycle_status"] != ArtifactLifecycleStatus.ACTIVE.value:
        return False
    payload_bytes = bytes(row["payload_bytes"] or b"")
    return artifact_sha256(payload_bytes) == row["artifact_hash"]


def prune_expired_artifacts_sync(
    conn: Connection,
    *,
    tenant_id: UUID,
    batch_limit: int = DEFAULT_P8_ARTIFACT_POLICY.max_prune_batch_size,
) -> dict[str, int]:
    """Prune expired non-audit artifacts with audit-preserving tombstones."""

    assert_bound_tenant(conn, tenant_id=tenant_id)
    bounded_limit = min(
        max(batch_limit, 1), DEFAULT_P8_ARTIFACT_POLICY.max_prune_batch_size
    )
    rows = (
        conn.execute(
            text(
                """
            SELECT id,
                   artifact_ref,
                   artifact_hash,
                   artifact_type,
                   artifact_size_bytes
            FROM public.bayesian_artifacts
            WHERE tenant_id = :tenant_id
              AND lifecycle_status = 'active'
              AND expires_at IS NOT NULL
              AND expires_at <= now()
            ORDER BY expires_at, created_at
            LIMIT :batch_limit
            FOR UPDATE SKIP LOCKED
            """
            ),
            {"tenant_id": str(tenant_id), "batch_limit": bounded_limit},
        )
        .mappings()
        .all()
    )
    pruned_bytes = 0
    for row in rows:
        metadata = {
            "artifact_ref": row["artifact_ref"],
            "artifact_hash": row["artifact_hash"],
            "artifact_type": row["artifact_type"],
            "artifact_size_bytes": int(row["artifact_size_bytes"]),
            "policy_version": DEFAULT_P8_ARTIFACT_POLICY.policy_version,
        }
        conn.execute(
            text(
                """
                UPDATE public.bayesian_artifacts
                SET lifecycle_status = 'pruned',
                    pruned_at = now(),
                    pruned_reason = 'retention_expired',
                    pruned_metadata = CAST(:pruned_metadata AS jsonb),
                    payload_json = NULL,
                    payload_bytes = NULL,
                    payload_byte_count = 0,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :artifact_id
                  AND lifecycle_status = 'active'
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "artifact_id": str(row["id"]),
                "pruned_metadata": _json_param(metadata),
            },
        )
        pruned_bytes += int(row["artifact_size_bytes"])
    if rows:
        _ensure_quota_row(conn, tenant_id=tenant_id, policy=DEFAULT_P8_ARTIFACT_POLICY)
        conn.execute(
            text(
                """
                UPDATE public.bayesian_artifact_storage_quotas
                SET active_bytes = GREATEST(active_bytes - :pruned_bytes, 0),
                    pruned_bytes = pruned_bytes + :pruned_bytes,
                    active_artifact_count = GREATEST(active_artifact_count - :count, 0),
                    pruned_artifact_count = pruned_artifact_count + :count,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "pruned_bytes": pruned_bytes,
                "count": len(rows),
            },
        )
    return {"pruned_count": len(rows), "pruned_bytes": pruned_bytes}
