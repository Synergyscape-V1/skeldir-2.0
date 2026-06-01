"""Parent-owned PyTensor compiledir lifecycle and bounded stale-dir reaper."""

from __future__ import annotations

import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


OWNER_MARKER = "skeldir-b24-p5"
METADATA_FILE = "skeldir_compiledir_owner.json"
LOCK_FILE = ".skeldir_reaper.lock"


@dataclass(frozen=True)
class CompiledirLease:
    root: Path
    path: Path
    worker_id: str
    execution_id: str
    parent_pid: int
    child_pid: int | None = None

    def with_child_pid(self, child_pid: int) -> "CompiledirLease":
        return CompiledirLease(
            root=self.root,
            path=self.path,
            worker_id=self.worker_id,
            execution_id=self.execution_id,
            parent_pid=self.parent_pid,
            child_pid=child_pid,
        )


def runtime_root() -> Path:
    return Path(
        os.getenv("B24_PYTENSOR_ROOT", Path("/tmp") / "skeldir-b24-pytensor")
    ).resolve()


def create_compiledir_lease(
    *, execution_id: str | None = None, worker_id: str | None = None
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
    path = root / worker / f"parent-{parent_pid}" / identity
    path.mkdir(parents=True, exist_ok=False)
    metadata = {
        "owner": OWNER_MARKER,
        "worker_id": worker,
        "execution_id": identity,
        "parent_pid": parent_pid,
        "created_at": time.time(),
    }
    (path / METADATA_FILE).write_text(
        json.dumps(metadata, sort_keys=True), encoding="utf-8"
    )
    return CompiledirLease(
        root=root,
        path=path,
        worker_id=worker,
        execution_id=identity,
        parent_pid=parent_pid,
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
    fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


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
        }
    with _reaper_lock(root):
        for metadata_path in root.glob("*/*/*/" + METADATA_FILE):
            if scanned >= max_scan_entries or deleted >= max_deletions:
                break
            scanned += 1
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
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
            shutil.rmtree(metadata_path.parent, ignore_errors=False)
            deleted += 1
    return {
        "root": str(root),
        "scanned": scanned,
        "deleted": deleted,
        "preserved_active": preserved_active,
        "preserved_foreign": preserved_foreign,
        "preserved_invalid": preserved_invalid,
    }
