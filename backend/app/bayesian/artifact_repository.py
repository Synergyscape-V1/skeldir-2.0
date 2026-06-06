"""Governed Postgres-native artifact persistence for B2.4-P8."""

from __future__ import annotations

import json
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


class BayesianArtifactRepository:
    """Tenant-scoped read/write wrapper for P8 artifact authority rows.

    Callers must use a session with `app.current_tenant_id` already set.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_ref(
        self, *, tenant_id: UUID, artifact_ref: str
    ) -> BayesianArtifact:
        stmt = select(BayesianArtifact).where(
            BayesianArtifact.tenant_id == tenant_id,
            BayesianArtifact.artifact_ref == artifact_ref,
        )
        result = await self._session.execute(stmt)
        artifact = result.scalar_one_or_none()
        if artifact is None:
            raise BayesianArtifactNotFoundError(
                f"bayesian artifact not found: {artifact_ref}"
            )
        return artifact


def _json_param(payload: dict[str, object] | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _expires_at(retention_class: str, now: datetime) -> datetime | None:
    ttl = RETENTION_TTLS[retention_class]
    return None if ttl is None else now + ttl


def _artifact_ref(*, fit_id: UUID, artifact_type: str, artifact_hash: str) -> str:
    return f"b24://artifact/{fit_id}/{artifact_type}/{artifact_hash[:12]}"


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
                0,
                0,
                0,
                0,
                0
            )
            ON CONFLICT (tenant_id)
            DO UPDATE SET
                policy_version = EXCLUDED.policy_version,
                updated_at = now()
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "policy_version": policy.policy_version,
            "quota_bytes": policy.default_tenant_quota_bytes,
        },
    )


def _charge_quota(
    conn: Connection,
    *,
    tenant_id: UUID,
    size_bytes: int,
    policy: ArtifactPolicy,
) -> None:
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
            RETURNING tenant_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "size_bytes": size_bytes,
            "policy_quota_bytes": policy.default_tenant_quota_bytes,
        },
    ).scalar_one_or_none()
    if result is not None:
        return
    conn.execute(
        text(
            """
            UPDATE public.bayesian_artifact_storage_quotas
            SET rejected_count = rejected_count + 1,
                last_rejection_reason = 'tenant_quota_exceeded',
                updated_at = now()
            WHERE tenant_id = :tenant_id
            """
        ),
        {"tenant_id": str(tenant_id)},
    )
    raise BayesianArtifactQuotaExceededError("tenant artifact quota exceeded")


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
            FOR UPDATE
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
            FOR UPDATE
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
        if existing["lifecycle_status"] != ArtifactLifecycleStatus.ACTIVE.value:
            raise BayesianArtifactPolicyError("pruned artifact ref cannot be rewritten")
        return {
            "artifact_id": str(existing["id"]),
            "artifact_ref": artifact_ref,
            "artifact_hash": stored_hash,
            "artifact_size_bytes": int(existing["artifact_size_bytes"]),
            "idempotent_replay": True,
        }
    _validate_fit_wal_budget(
        conn,
        tenant_id=tenant_id,
        fit_id=fit_id,
        size_bytes=size_bytes,
        policy=policy,
    )
    _charge_quota(conn, tenant_id=tenant_id, size_bytes=size_bytes, policy=policy)
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
    }


def verify_artifact_bytes_sync(
    conn: Connection,
    *,
    tenant_id: UUID,
    artifact_ref: str,
) -> bool:
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
