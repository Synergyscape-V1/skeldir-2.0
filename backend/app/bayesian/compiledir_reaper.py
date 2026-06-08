"""Parent-owned PyTensor compiledir lifecycle and bounded stale-dir reaper."""

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
from uuid import uuid4


OWNER_MARKER = "skeldir-b24-p5"
METADATA_FILE = "skeldir_compiledir_owner.json"
LOCK_FILE = ".skeldir_reaper.lock"
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True)
class CompiledirLease:
    root: Path
    path: Path
    worker_id: str
    execution_id: str
    parent_pid: int
    tenant_id: UUID | None = None
    fit_id: UUID | None = None
    source_snapshot_hash: str | None = None
    child_pid: int | None = None

    def with_child_pid(self, child_pid: int) -> "CompiledirLease":
        return CompiledirLease(
            root=self.root,
            path=self.path,
            worker_id=self.worker_id,
            execution_id=self.execution_id,
            parent_pid=self.parent_pid,
            tenant_id=self.tenant_id,
            fit_id=self.fit_id,
            source_snapshot_hash=self.source_snapshot_hash,
            child_pid=child_pid,
        )


def runtime_root() -> Path:
    return Path(
        os.getenv("B24_PYTENSOR_ROOT", Path("/tmp") / "skeldir-b24-pytensor")
    ).resolve()


def _safe_segment(value: object, *, label: str) -> str:
    segment = str(value)
    if label == "source_snapshot_hash":
        valid = _SHA256.fullmatch(segment) is not None
    else:
        valid = _SAFE_SEGMENT.fullmatch(segment) is not None
    if not valid or segment in {".", ".."}:
        raise ValueError(f"unsafe B2.4 compiledir segment: {label}")
    return segment


def create_compiledir_lease(
    *,
    execution_id: str | None = None,
    worker_id: str | None = None,
    tenant_id: UUID | None = None,
    fit_id: UUID | None = None,
    source_snapshot_hash: str | None = None,
) -> CompiledirLease:
    """Create a worker/PID/execution-scoped compiledir with ownership metadata."""

    root = runtime_root()
    worker = worker_id or os.getenv(
        "B24_BAYESIAN_WORKER_RUNTIME_ID", "local-bayesian-worker"
    )
    identity = (
        execution_id or os.getenv("B24_PYTENSOR_EXECUTION_ID") or f"probe-{uuid4().hex}"
    )
    parent_pid = os.getpid()
    if any(value is not None for value in (tenant_id, fit_id, source_snapshot_hash)):
        if tenant_id is None or fit_id is None or source_snapshot_hash is None:
            raise ValueError(
                "compiledir tenant, fit, and source hash must travel together"
            )
        path = (
            root
            / worker
            / _safe_segment(tenant_id, label="tenant_id")
            / _safe_segment(fit_id, label="fit_id")
            / _safe_segment(source_snapshot_hash, label="source_snapshot_hash")
            / f"parent-{parent_pid}"
            / _safe_segment(identity, label="execution_id")
        )
    else:
        path = (
            root
            / worker
            / f"parent-{parent_pid}"
            / _safe_segment(identity, label="execution_id")
        )
    resolved_root = root.resolve()
    resolved_path = path.resolve()
    if resolved_root != resolved_path and resolved_root not in resolved_path.parents:
        raise ValueError("compiledir path escapes B2.4 root")
    path.mkdir(parents=True, exist_ok=False)
    metadata = {
        "owner": OWNER_MARKER,
        "worker_id": worker,
        "execution_id": identity,
        "parent_pid": parent_pid,
        "created_at": time.time(),
    }
    if tenant_id is not None:
        metadata.update(
            {
                "tenant_id": str(tenant_id),
                "fit_id": str(fit_id),
                "source_snapshot_hash": source_snapshot_hash,
            }
        )
    (path / METADATA_FILE).write_text(
        json.dumps(metadata, sort_keys=True), encoding="utf-8"
    )
    return CompiledirLease(
        root=root,
        path=path,
        worker_id=worker,
        execution_id=identity,
        parent_pid=parent_pid,
        tenant_id=tenant_id,
        fit_id=fit_id,
        source_snapshot_hash=source_snapshot_hash,
    )


def record_child_pid(lease: CompiledirLease, child_pid: int) -> CompiledirLease:
    metadata_path = lease.path / METADATA_FILE
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["child_pid"] = int(child_pid)
    metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    return lease.with_child_pid(child_pid)


def cleanup_compiledir(lease: CompiledirLease) -> bool:
    """Remove a compiledir only when it carries Skeldir P5 ownership metadata."""

    metadata_path = lease.path / METADATA_FILE
    if not metadata_path.exists():
        return False
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("owner") != OWNER_MARKER:
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
def _reaper_lock(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = root / LOCK_FILE
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


def reap_expired_compiledirs(
    *, ttl_seconds: int = 3600, max_deletions: int = 25, max_scan_entries: int = 200
) -> dict[str, object]:
    """Bounded reaper for expired Skeldir-owned compiledirs only."""

    root = runtime_root()
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
    with _reaper_lock(root) as lock_acquired:
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
        for metadata_path in list(root.rglob(METADATA_FILE)):
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
            if metadata.get("owner") != OWNER_MARKER:
                preserved_foreign += 1
                continue
            if _pid_alive(metadata.get("parent_pid")) or _pid_alive(
                metadata.get("child_pid")
            ):
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
