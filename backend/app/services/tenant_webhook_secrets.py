from __future__ import annotations

"""Tenant webhook secret resolution with key-id addressed decrypt + bounded cache."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import logging
import time
from collections import OrderedDict
from threading import Lock
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.core.secrets import (
    get_platform_encryption_key_ring,
    resolve_platform_encryption_key_by_id,
)
from app.db.session import engine as db_engine

logger = logging.getLogger(__name__)

PROVIDERS = ("shopify", "stripe", "paypal", "woocommerce")


@dataclass(frozen=True)
class TenantWebhookSecretPayload:
    tenant_id: UUID
    api_key_hash: str
    secrets: dict[str, str | None]


@dataclass
class _CacheEntry:
    value: str
    expires_at_monotonic: float


class _TenantWebhookSecretCache:
    def __init__(self) -> None:
        self._entries: "OrderedDict[str, _CacheEntry]" = OrderedDict()
        self._lock = Lock()
        self._tenant_versions: dict[str, str] = {}

    @staticmethod
    def _now() -> float:
        return time.monotonic()

    def get(self, key: str) -> str | None:
        now = self._now()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at_monotonic <= now:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry.value

    def set(self, key: str, value: str) -> None:
        ttl = max(1, int(settings.TENANT_SECRETS_CACHE_TTL_SECONDS))
        max_entries = max(1, int(settings.TENANT_SECRETS_CACHE_MAX_ENTRIES))
        expires = self._now() + float(ttl)
        with self._lock:
            self._entries[key] = _CacheEntry(value=value, expires_at_monotonic=expires)
            self._entries.move_to_end(key)
            while len(self._entries) > max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._tenant_versions.clear()

    def evict_tenant(self, tenant_id: UUID) -> None:
        prefix = f"{tenant_id}:"
        with self._lock:
            for key in [k for k in self._entries.keys() if k.startswith(prefix)]:
                self._entries.pop(key, None)
            self._tenant_versions.pop(str(tenant_id), None)

    def sync_tenant_version(self, tenant_id: UUID, version_token: str | None) -> None:
        if not version_token:
            return
        tenant_key = str(tenant_id)
        with self._lock:
            last = self._tenant_versions.get(tenant_key)
            if last is None:
                self._tenant_versions[tenant_key] = version_token
                return
            if last == version_token:
                return
            # Synchronous invalidation on tenant secret mutation.
            prefix = f"{tenant_id}:"
            for key in [k for k in self._entries.keys() if k.startswith(prefix)]:
                self._entries.pop(key, None)
            self._tenant_versions[tenant_key] = version_token


_CACHE = _TenantWebhookSecretCache()
_DECRYPT_COUNTER = 0


def reset_tenant_webhook_secret_cache_for_testing() -> None:
    global _DECRYPT_COUNTER
    _CACHE.clear()
    _DECRYPT_COUNTER = 0


def get_tenant_webhook_secret_internal_stats_for_testing() -> dict[str, int]:
    return {"decrypt_count": _DECRYPT_COUNTER}


def invalidate_tenant_webhook_secret_cache(tenant_id: UUID) -> None:
    _CACHE.evict_tenant(tenant_id)


def _bytes_from_db(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, bytes):
        return value
    return bytes(value)


def _cache_key(
    *,
    tenant_id: UUID,
    provider: str,
    key_id: str,
    ciphertext: bytes,
) -> str:
    digest = hashlib.sha256(ciphertext).hexdigest()
    return f"{tenant_id}:{provider}:{key_id}:{digest}"


async def _decrypt_ciphertext_once(
    conn: AsyncConnection,
    *,
    ciphertext: bytes,
    key: str,
) -> str:
    global _DECRYPT_COUNTER
    res = await conn.execute(
        text("SELECT pgp_sym_decrypt(CAST(:ciphertext AS bytea), CAST(:key AS text)) AS value"),
        {"ciphertext": ciphertext, "key": key},
    )
    _DECRYPT_COUNTER += 1
    value = res.scalar_one_or_none()
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


async def _maybe_lazy_reencrypt(
    _conn: AsyncConnection,
    *,
    tenant_id: UUID,
    provider: str,
    plaintext_secret: str,
    old_key_id: str,
) -> None:
    ring = get_platform_encryption_key_ring(require_fresh_for_write=False)
    if old_key_id == ring.current_key_id:
        return
    current_key = ring.keys.get(ring.current_key_id)
    if not current_key:
        return
    async with db_engine.begin() as write_conn:
        await write_conn.execute(
            text(
                f"""
                UPDATE public.tenants
                SET
                  {provider}_webhook_secret_ciphertext = pgp_sym_encrypt(:secret, :current_key),
                  {provider}_webhook_secret_key_id = :current_key_id,
                  updated_at = :updated_at
                WHERE id = :tenant_id
                  AND {provider}_webhook_secret_key_id = :old_key_id
                """
            ),
            {
                "secret": plaintext_secret,
                "current_key": current_key,
                "current_key_id": ring.current_key_id,
                "tenant_id": str(tenant_id),
                "old_key_id": old_key_id,
                "updated_at": datetime.now(timezone.utc),
            },
        )


async def resolve_tenant_webhook_secrets_from_row(
    conn: AsyncConnection,
    *,
    tenant_id: UUID,
    row: dict[str, Any],
) -> dict[str, str | None]:
    version_token = row.get("tenant_updated_at")
    _CACHE.sync_tenant_version(tenant_id, str(version_token) if version_token is not None else None)

    resolved: dict[str, str | None] = {}
    for provider in PROVIDERS:
        plaintext_raw = row.get(f"{provider}_webhook_secret")
        ciphertext_raw = row.get(f"{provider}_webhook_secret_ciphertext")
        key_id_raw = row.get(f"{provider}_webhook_secret_key_id")
        ciphertext = _bytes_from_db(ciphertext_raw)
        key_id = str(key_id_raw).strip() if key_id_raw is not None else ""

        if not ciphertext or not key_id:
            if plaintext_raw is not None and str(plaintext_raw).strip():
                plaintext_value = str(plaintext_raw)
                plaintext_cache_key = f"{tenant_id}:{provider}:legacy-plaintext:{hashlib.sha256(plaintext_value.encode('utf-8')).hexdigest()}"
                cached_plain = _CACHE.get(plaintext_cache_key)
                if cached_plain is not None:
                    resolved[f"{provider}_webhook_secret"] = cached_plain
                else:
                    _CACHE.set(plaintext_cache_key, plaintext_value)
                    resolved[f"{provider}_webhook_secret"] = plaintext_value
                continue
            resolved[f"{provider}_webhook_secret"] = None
            continue

        cache_key = _cache_key(
            tenant_id=tenant_id,
            provider=provider,
            key_id=key_id,
            ciphertext=ciphertext,
        )
        cached = _CACHE.get(cache_key)
        if cached is not None:
            resolved[f"{provider}_webhook_secret"] = cached
            continue

        key = resolve_platform_encryption_key_by_id(key_id)
        plaintext = await _decrypt_ciphertext_once(conn, ciphertext=ciphertext, key=key)
        _CACHE.set(cache_key, plaintext)
        resolved[f"{provider}_webhook_secret"] = plaintext

        await _maybe_lazy_reencrypt(
            conn,
            tenant_id=tenant_id,
            provider=provider,
            plaintext_secret=plaintext,
            old_key_id=key_id,
        )
    return resolved
