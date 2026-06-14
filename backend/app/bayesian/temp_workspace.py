"""Parent-owned fit-attempt workspace lifecycle for Bayesian workers."""

from __future__ import annotations

import json
import os
import re
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID


WORKSPACE_OWNER = "skeldir-b24-p9"
WORKSPACE_METADATA_FILE = "skeldir_workspace_owner.json"
WORKSPACE_LOCK_FILE = ".skeldir_workspace_reaper.lock"
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class WorkspaceLease:
    """Physical workspace authority for one tenant/fit/hash/attempt."""

    root: Path
    path: Path
    tenant_id: UUID
    fit_id: UUID
    source_snapshot_hash: str
    execution_attempt_id: str
    parent_pid: int


def workspace_root() -> Path:
    return Path(
        os.getenv(
            "B24_BAYESIAN_WORKSPACE_ROOT", Path("/tmp") / "skeldir-b24-workspaces"
        )
    ).resolve()


def _safe_segment(value: object, *, label: str) -> str:
    segment = str(value)
    if label == "source_snapshot_hash":
        valid = _SHA256.fullmatch(segment) is not None
    else:
        valid = _SAFE_SEGMENT.fullmatch(segment) is not None
    if not valid or segment in {".", ".."}:
        raise ValueError(f"unsafe B2.4-P9 workspace segment: {label}")
    return segment


def create_workspace_lease(
    *,
    tenant_id: UUID,
    fit_id: UUID,
    source_snapshot_hash: str,
    execution_attempt_id: str,
) -> WorkspaceLease:
    """Create a tenant/fit/source/attempt-scoped workspace with ownership metadata."""

    root = workspace_root()
    tenant_segment = _safe_segment(tenant_id, label="tenant_id")
    fit_segment = _safe_segment(fit_id, label="fit_id")
    hash_segment = _safe_segment(source_snapshot_hash, label="source_snapshot_hash")
    attempt_segment = _safe_segment(execution_attempt_id, label="execution_attempt_id")
    path = root / tenant_segment / fit_segment / hash_segment / attempt_segment
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root != resolved_path and resolved_root not in resolved_path.parents:
        raise ValueError("workspace path escapes B2.4-P9 root")
    path.mkdir(parents=True, exist_ok=False)
    lease = WorkspaceLease(
        root=root,
        path=path,
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_snapshot_hash,
        execution_attempt_id=execution_attempt_id,
        parent_pid=os.getpid(),
    )
    metadata = {
        "owner": WORKSPACE_OWNER,
        "tenant_id": str(tenant_id),
        "fit_id": str(fit_id),
        "source_snapshot_hash": source_snapshot_hash,
        "execution_attempt_id": execution_attempt_id,
        "parent_pid": lease.parent_pid,
        "created_at": time.time(),
    }
    (path / WORKSPACE_METADATA_FILE).write_text(
        json.dumps(metadata, sort_keys=True), encoding="utf-8"
    )
    return lease


def cleanup_workspace(lease: WorkspaceLease) -> bool:
    """Remove a workspace only when its P9 ownership metadata matches."""

    metadata_path = lease.path / WORKSPACE_METADATA_FILE
    if not metadata_path.exists():
        return False
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("owner") != WORKSPACE_OWNER:
        return False
    if metadata.get("tenant_id") != str(lease.tenant_id):
        return False
    if metadata.get("fit_id") != str(lease.fit_id):
        return False
    shutil.rmtree(lease.path, ignore_errors=False)
    return True


def _pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OSError):
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def _workspace_reaper_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / WORKSPACE_LOCK_FILE
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        yield False
        return
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield True
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def _is_owned_child_path(root: Path, path: Path) -> bool:
    try:
        resolved_root = root.resolve(strict=True)
    except FileNotFoundError:
        return False
    try:
        resolved_path = path.resolve(strict=True)
    except FileNotFoundError:
        return False
    if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
        return False
    current = path
    while current != root:
        if current.is_symlink():
            return False
        current = current.parent
    return True


def reap_expired_workspaces(
    *, ttl_seconds: int = 3600, max_deletions: int = 25, max_scan_entries: int = 200
) -> dict[str, object]:
    """Bounded pre-flight janitor for stale Skeldir-owned P9 workspaces."""

    root = workspace_root()
    now = time.time()
    scanned = deleted = preserved_active = preserved_foreign = preserved_invalid = 0
    if not root.exists():
        return {
            "root": str(root),
            "scanned": 0,
            "deleted": 0,
            "preserved_active": 0,
            "preserved_foreign": 0,
            "preserved_invalid": 0,
            "lock_contended": False,
        }
    lock_contended = False
    with _workspace_reaper_lock(root) as lock_acquired:
        if not lock_acquired:
            lock_contended = True
            return {
                "root": str(root),
                "scanned": 0,
                "deleted": 0,
                "preserved_active": 0,
                "preserved_foreign": 0,
                "preserved_invalid": 0,
                "lock_contended": lock_contended,
            }
        for metadata_path in list(root.rglob(WORKSPACE_METADATA_FILE)):
            if scanned >= max_scan_entries or deleted >= max_deletions:
                break
            scanned += 1
            if not _is_owned_child_path(root, metadata_path.parent):
                preserved_invalid += 1
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                deleted += 1
                continue
            except Exception:
                preserved_invalid += 1
                continue
            if metadata.get("owner") != WORKSPACE_OWNER:
                preserved_foreign += 1
                continue
            if _pid_alive(metadata.get("parent_pid")):
                preserved_active += 1
                continue
            created_at = float(metadata.get("created_at", now))
            if now - created_at < ttl_seconds:
                preserved_active += 1
                continue
            try:
                shutil.rmtree(metadata_path.parent, ignore_errors=False)
            except FileNotFoundError:
                pass
            deleted += 1
    return {
        "root": str(root),
        "scanned": scanned,
        "deleted": deleted,
        "preserved_active": preserved_active,
        "preserved_foreign": preserved_foreign,
        "preserved_invalid": preserved_invalid,
        "lock_contended": lock_contended,
    }
