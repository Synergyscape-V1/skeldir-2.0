from __future__ import annotations

import json
import logging
import os
import select
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import UUID

import psycopg2

from app.core.secrets import get_database_url

logger = logging.getLogger(__name__)

REVOCATION_NOTIFY_CHANNEL_DENYLIST = "skeldir_token_revoked"
REVOCATION_NOTIFY_CHANNEL_CUTOFF = "skeldir_tokens_invalid_before_updated"

_MUTATION_DISABLE_EVENT_LISTENER = "SKELDIR_B12_P5_DISABLE_REVOCATION_EVENT_LISTENER"
_DEFAULT_POLL_TIMEOUT_SECONDS = 1.0


@dataclass(frozen=True)
class CachedRevocationSnapshot:
    is_revoked: bool
    is_known: bool


def _to_sync_dsn(raw_url: str) -> str:
    parsed = urlsplit(raw_url)
    query_params = dict(parse_qsl(parsed.query))
    query_params.pop("channel_binding", None)
    sanitized = urlunsplit(parsed._replace(query=urlencode(query_params)))
    if sanitized.startswith("postgresql+asyncpg://"):
        return sanitized.replace("postgresql+asyncpg://", "postgresql://", 1)
    return sanitized


def _parse_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        if not raw:
            return None
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class RevocationRuntimeCache:
    """
    Process-local revocation cache.

    Denylist storage is bounded by token expiration. Cutoff storage is bounded by
    tenant/user cardinality. A background LISTEN/NOTIFY loop keeps the cache
    synchronized across API and worker processes without request-path DB I/O.
    """

    def __init__(self, *, runtime_name: str = "default") -> None:
        self._runtime_name = runtime_name
        self._lock = threading.Lock()
        self._listener_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._denylisted_until: dict[tuple[UUID, UUID, UUID], datetime] = {}
        self._cutoff_by_user: dict[tuple[UUID, UUID], datetime | None] = {}
        self._known_clean_jti_until: dict[tuple[UUID, UUID, UUID], datetime] = {}

    def close(self) -> None:
        self._stop_event.set()
        listener = self._listener_thread
        if listener and listener.is_alive():
            listener.join(timeout=2.0)

    def ensure_started(self) -> None:
        if os.getenv(_MUTATION_DISABLE_EVENT_LISTENER) == "1":
            return
        if self._listener_thread and self._listener_thread.is_alive():
            return
        with self._lock:
            if self._listener_thread and self._listener_thread.is_alive():
                return
            self._stop_event.clear()
            thread = threading.Thread(
                target=self._listen_loop,
                name=f"revocation-listener-{self._runtime_name}",
                daemon=True,
            )
            thread.start()
            self._listener_thread = thread

    def note_denylist(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        jti: UUID,
        expires_at: datetime,
    ) -> None:
        expiry = _parse_timestamp(expires_at)
        if expiry is None:
            return
        key = (tenant_id, user_id, jti)
        with self._lock:
            existing = self._denylisted_until.get(key)
            if existing is None or expiry > existing:
                self._denylisted_until[key] = expiry
            self._known_clean_jti_until.pop(key, None)

    def note_cutoff(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        tokens_invalid_before: datetime,
    ) -> None:
        cutoff = _parse_timestamp(tokens_invalid_before)
        if cutoff is None:
            return
        key = (tenant_id, user_id)
        with self._lock:
            current = self._cutoff_by_user.get(key)
            if current is None or cutoff > current:
                self._cutoff_by_user[key] = cutoff

    def note_cutoff_absent(self, *, tenant_id: UUID, user_id: UUID) -> None:
        key = (tenant_id, user_id)
        with self._lock:
            self._cutoff_by_user.setdefault(key, None)

    def note_clean_token(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        jti: UUID,
        expires_at: datetime,
    ) -> None:
        expiry = _parse_timestamp(expires_at)
        if expiry is None:
            return
        key = (tenant_id, user_id, jti)
        with self._lock:
            self._known_clean_jti_until[key] = expiry

    def snapshot_for_token(
        self,
        *,
        tenant_id: UUID,
        user_id: UUID,
        jti: UUID,
        issued_at_epoch: int,
    ) -> CachedRevocationSnapshot:
        now = datetime.now(timezone.utc)
        issued_at = datetime.fromtimestamp(int(issued_at_epoch), tz=timezone.utc)
        tuple_key = (tenant_id, user_id, jti)
        user_key = (tenant_id, user_id)

        with self._lock:
            self._purge_expired_locked(now)

            denylisted_until = self._denylisted_until.get(tuple_key)
            if denylisted_until is not None and denylisted_until > now:
                return CachedRevocationSnapshot(is_revoked=True, is_known=True)

            cutoff_known = user_key in self._cutoff_by_user
            cutoff = self._cutoff_by_user.get(user_key)
            if cutoff is not None and issued_at <= cutoff:
                return CachedRevocationSnapshot(is_revoked=True, is_known=True)

            clean_until = self._known_clean_jti_until.get(tuple_key)
            if cutoff_known and clean_until is not None and clean_until > now:
                return CachedRevocationSnapshot(is_revoked=False, is_known=True)

            return CachedRevocationSnapshot(is_revoked=False, is_known=False)

    def _purge_expired_locked(self, now_utc: datetime) -> None:
        for key, expiry in list(self._denylisted_until.items()):
            if expiry <= now_utc:
                self._denylisted_until.pop(key, None)
        for key, expiry in list(self._known_clean_jti_until.items()):
            if expiry <= now_utc:
                self._known_clean_jti_until.pop(key, None)

    def _listen_loop(self) -> None:
        dsn = _to_sync_dsn(get_database_url())
        backoff_seconds = 0.5
        while not self._stop_event.is_set():
            conn = None
            try:
                conn = psycopg2.connect(dsn)
                conn.set_session(autocommit=True)
                cur = conn.cursor()
                cur.execute(f"LISTEN {REVOCATION_NOTIFY_CHANNEL_DENYLIST};")
                cur.execute(f"LISTEN {REVOCATION_NOTIFY_CHANNEL_CUTOFF};")
                logger.info(
                    "revocation_listener_started",
                    extra={"runtime_name": self._runtime_name},
                )
                backoff_seconds = 0.5

                while not self._stop_event.is_set():
                    ready, _, _ = select.select(
                        [conn],
                        [],
                        [],
                        _DEFAULT_POLL_TIMEOUT_SECONDS,
                    )
                    if not ready:
                        continue
                    conn.poll()
                    while conn.notifies:
                        notify = conn.notifies.pop(0)
                        self._apply_notification(notify.channel, notify.payload)
            except Exception:
                logger.exception(
                    "revocation_listener_error",
                    extra={"runtime_name": self._runtime_name},
                )
                time.sleep(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2.0, 5.0)
            finally:
                try:
                    if conn is not None:
                        conn.close()
                except Exception:
                    pass

    def _apply_notification(self, channel: str, payload: str | None) -> None:
        if not payload:
            return
        try:
            body = json.loads(payload)
        except json.JSONDecodeError:
            return

        tenant_id = _parse_uuid(body.get("tenant_id"))
        user_id = _parse_uuid(body.get("user_id"))
        if tenant_id is None or user_id is None:
            return

        if channel == REVOCATION_NOTIFY_CHANNEL_DENYLIST:
            jti = _parse_uuid(body.get("jti"))
            expires_at = _parse_timestamp(body.get("expires_at"))
            if jti is None or expires_at is None:
                return
            self.note_denylist(
                tenant_id=tenant_id,
                user_id=user_id,
                jti=jti,
                expires_at=expires_at,
            )
            return

        if channel == REVOCATION_NOTIFY_CHANNEL_CUTOFF:
            cutoff = _parse_timestamp(body.get("tokens_invalid_before"))
            if cutoff is None:
                return
            self.note_cutoff(
                tenant_id=tenant_id,
                user_id=user_id,
                tokens_invalid_before=cutoff,
            )


_DEFAULT_CACHE = RevocationRuntimeCache()


def get_revocation_runtime_cache() -> RevocationRuntimeCache:
    return _DEFAULT_CACHE


def with_isolated_revocation_cache_for_test(
    runtime_name: str,
    callback: Callable[[RevocationRuntimeCache], None],
) -> None:
    cache = RevocationRuntimeCache(runtime_name=runtime_name)
    try:
        callback(cache)
    finally:
        cache.close()
