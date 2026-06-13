"""Celery boot-time topology gate for Bayesian workers."""

from __future__ import annotations

import atexit
import hashlib
import hmac
import json
import logging
import os
import secrets
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from celery import signals

from app.bayesian.db_boot_probe import (
    BayesianWorkerBootTopologyProbeError,
    run_bayesian_worker_boot_topology_probe,
)

logger = logging.getLogger(__name__)

BAYESIAN_WORKER_AUTHORITY_VERSION = "b24-p9-worker-generation-v1"
BAYESIAN_CHILD_AUTHORITY_BUDGET_S = 0.2
_AUTHORITY_FILE_ENV = "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_FILE"
_AUTHORITY_DIR_ENV = "SKELDIR_BAYESIAN_WORKER_GENERATION_AUTHORITY_DIR"
_TOPOLOGY_FINGERPRINT_ENV_NAMES = (
    "DATABASE_URL",
    "SKELDIR_BAYESIAN_DB_TOPOLOGY",
    "SKELDIR_BAYESIAN_DB_TOPOLOGY_ATTESTATION",
    "SKELDIR_BAYESIAN_DB_TOPOLOGY_SOURCE",
)


class BayesianWorkerBootTopologyProofMissing(RuntimeError):
    """Raised when a Bayesian task starts without process-local topology proof."""


@dataclass(frozen=True)
class BayesianWorkerGenerationProof:
    """Parent-process physical proof and local authority material."""

    generation_id: str
    parent_pid: int
    topology_fingerprint: str
    authority_secret: str
    proof_elapsed_seconds: float
    worker_connection_count: int
    observer_connection_count: int
    created_monotonic: float


@dataclass(frozen=True)
class BayesianWorkerExecutionAuthority:
    """Process-local authority derived from the parent generation proof."""

    generation_id: str
    pid: int
    parent_pid: int
    topology_fingerprint: str
    token: str
    issued_monotonic: float
    derivation_elapsed_seconds: float


_bayesian_worker_generation_proof: BayesianWorkerGenerationProof | None = None
_bayesian_execution_authority: BayesianWorkerExecutionAuthority | None = None
_bayesian_boot_topology_probe_signal_registered = False
_bayesian_generation_authority_file: Path | None = None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_probe_event(event: dict[str, object]) -> None:
    path = os.getenv("BAYESIAN_PROBE_LOG_PATH")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
    except Exception:
        logger.warning("bayesian_probe_log_write_failed", extra={"path": path})


def _topology_authority_fingerprint() -> str:
    payload = {name: os.getenv(name, "") for name in _TOPOLOGY_FINGERPRINT_ENV_NAMES}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _generation_proof_to_json(
    proof: BayesianWorkerGenerationProof,
) -> dict[str, object]:
    return {
        "authority_version": BAYESIAN_WORKER_AUTHORITY_VERSION,
        "generation_id": proof.generation_id,
        "parent_pid": proof.parent_pid,
        "topology_fingerprint": proof.topology_fingerprint,
        "authority_secret": proof.authority_secret,
        "proof_elapsed_seconds": proof.proof_elapsed_seconds,
        "worker_connection_count": proof.worker_connection_count,
        "observer_connection_count": proof.observer_connection_count,
        "created_monotonic": proof.created_monotonic,
    }


def _generation_proof_from_json(
    payload: dict[str, object],
) -> BayesianWorkerGenerationProof:
    if payload.get("authority_version") != BAYESIAN_WORKER_AUTHORITY_VERSION:
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_authority_version_mismatch"
        )
    proof = BayesianWorkerGenerationProof(
        generation_id=str(payload["generation_id"]),
        parent_pid=int(payload["parent_pid"]),
        topology_fingerprint=str(payload["topology_fingerprint"]),
        authority_secret=str(payload["authority_secret"]),
        proof_elapsed_seconds=float(payload["proof_elapsed_seconds"]),
        worker_connection_count=int(payload["worker_connection_count"]),
        observer_connection_count=int(payload["observer_connection_count"]),
        created_monotonic=float(payload["created_monotonic"]),
    )
    if not proof.generation_id or not proof.authority_secret:
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_authority_incomplete"
        )
    return proof


def _authority_directory() -> Path:
    root = os.getenv(_AUTHORITY_DIR_ENV)
    if root:
        directory = Path(root)
    else:
        directory = Path(tempfile.gettempdir()) / "skeldir-bayesian-worker-authority"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory


def _cleanup_generation_authority_file(path: Path) -> None:
    with suppress(OSError):
        path.unlink()


def _persist_generation_authority_file(proof: BayesianWorkerGenerationProof) -> None:
    global _bayesian_generation_authority_file
    directory = _authority_directory()
    path = directory / f"{proof.generation_id}-{proof.parent_pid}.json"
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(_generation_proof_to_json(proof), sort_keys=True),
        encoding="utf-8",
    )
    with suppress(OSError):
        temp_path.chmod(0o600)
    temp_path.replace(path)
    with suppress(OSError):
        path.chmod(0o600)
    os.environ[_AUTHORITY_FILE_ENV] = str(path)
    _bayesian_generation_authority_file = path
    atexit.register(_cleanup_generation_authority_file, path)


def _load_generation_authority_file() -> BayesianWorkerGenerationProof:
    path = os.getenv(_AUTHORITY_FILE_ENV, "").strip()
    if not path:
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_proof_required"
        )
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_authority_invalid"
        )
    proof = _generation_proof_from_json(payload)
    if proof.topology_fingerprint != _topology_authority_fingerprint():
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_topology_fingerprint_mismatch"
        )
    return proof


def _authority_token(
    proof: BayesianWorkerGenerationProof,
    *,
    pid: int,
    topology_fingerprint: str,
) -> str:
    message = "|".join(
        (
            BAYESIAN_WORKER_AUTHORITY_VERSION,
            proof.generation_id,
            str(proof.parent_pid),
            str(pid),
            topology_fingerprint,
        )
    ).encode("utf-8")
    return hmac.new(
        proof.authority_secret.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


def _derive_process_authority_from_generation() -> BayesianWorkerExecutionAuthority:
    global _bayesian_worker_generation_proof
    proof = _bayesian_worker_generation_proof
    if proof is None:
        proof = _load_generation_authority_file()
        _bayesian_worker_generation_proof = proof
    started = time.monotonic()
    pid = os.getpid()
    topology_fingerprint = _topology_authority_fingerprint()
    if topology_fingerprint != proof.topology_fingerprint:
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_generation_topology_fingerprint_mismatch"
        )
    token = _authority_token(
        proof,
        pid=pid,
        topology_fingerprint=topology_fingerprint,
    )
    authority = BayesianWorkerExecutionAuthority(
        generation_id=proof.generation_id,
        pid=pid,
        parent_pid=proof.parent_pid,
        topology_fingerprint=topology_fingerprint,
        token=token,
        issued_monotonic=time.monotonic(),
        derivation_elapsed_seconds=time.monotonic() - started,
    )
    if authority.derivation_elapsed_seconds > BAYESIAN_CHILD_AUTHORITY_BUDGET_S:
        raise BayesianWorkerBootTopologyProofMissing(
            "bayesian_worker_child_authority_budget_exceeded"
        )
    return authority


def bayesian_worker_boot_topology_probe_has_passed() -> bool:
    """Return whether this OS process carries valid generation authority."""

    proof = _bayesian_worker_generation_proof
    authority = _bayesian_execution_authority
    if proof is None or authority is None:
        return False
    topology_fingerprint = _topology_authority_fingerprint()
    expected_token = _authority_token(
        proof,
        pid=os.getpid(),
        topology_fingerprint=topology_fingerprint,
    )
    return (
        authority.pid == os.getpid()
        and authority.generation_id == proof.generation_id
        and authority.parent_pid == proof.parent_pid
        and authority.topology_fingerprint == proof.topology_fingerprint
        and topology_fingerprint == proof.topology_fingerprint
        and hmac.compare_digest(authority.token, expected_token)
    )


def assert_bayesian_worker_boot_topology_proven() -> None:
    """Fail closed when a Bayesian task starts without process-local proof."""

    if bayesian_worker_boot_topology_probe_has_passed():
        return
    raise BayesianWorkerBootTopologyProofMissing(
        "bayesian_worker_boot_topology_probe_required"
    )


def _run_bayesian_worker_boot_topology_probe_if_needed() -> None:
    """Fatal parent-generation physical proof before task consumption."""

    global _bayesian_worker_generation_proof
    global _bayesian_execution_authority
    if bayesian_worker_boot_topology_probe_has_passed():
        return
    if _bayesian_worker_generation_proof is not None:
        _bayesian_execution_authority = _derive_process_authority_from_generation()
        return

    logger.info(
        "bayesian_worker_boot_topology_probe_started",
        extra={
            "event_type": "bayesian.worker_boot_topology_probe",
            "worker_pid": os.getpid(),
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_worker_generation_proof_started",
            "timestamp": _utc_now(),
            "worker_pid": os.getpid(),
        }
    )
    try:
        result = run_bayesian_worker_boot_topology_probe()
    except (BayesianWorkerBootTopologyProbeError, RuntimeError) as exc:
        logger.critical(
            "bayesian_worker_boot_topology_probe_failed",
            extra={
                "event_type": "bayesian.worker_boot_topology_probe",
                "worker_pid": os.getpid(),
                "error": exc.__class__.__name__,
            },
        )
        _append_probe_event(
            {
                "event": "bayesian_worker_generation_proof_failed",
                "timestamp": _utc_now(),
                "worker_pid": os.getpid(),
                "error": exc.__class__.__name__,
            }
        )
        raise SystemExit("bayesian_worker_boot_topology_probe_failed") from exc

    _bayesian_worker_generation_proof = BayesianWorkerGenerationProof(
        generation_id=uuid4().hex,
        parent_pid=os.getpid(),
        topology_fingerprint=_topology_authority_fingerprint(),
        authority_secret=secrets.token_urlsafe(32),
        proof_elapsed_seconds=result.elapsed_seconds,
        worker_connection_count=getattr(result, "worker_connection_count", 2),
        observer_connection_count=getattr(result, "observer_connection_count", 0),
        created_monotonic=time.monotonic(),
    )
    _persist_generation_authority_file(_bayesian_worker_generation_proof)
    _bayesian_execution_authority = _derive_process_authority_from_generation()
    logger.info(
        "bayesian_worker_boot_topology_probe_passed",
        extra={
            "event_type": "bayesian.worker_boot_topology_probe",
            "worker_pid": os.getpid(),
            "old_pid": result.old_pid,
            "new_pid": result.new_pid,
            "elapsed_seconds": result.elapsed_seconds,
            "worker_generation_id": _bayesian_worker_generation_proof.generation_id,
            "worker_connection_count": (
                _bayesian_worker_generation_proof.worker_connection_count
            ),
            "observer_connection_count": (
                _bayesian_worker_generation_proof.observer_connection_count
            ),
            "generation_authority_file": bool(_bayesian_generation_authority_file),
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_worker_generation_proof_passed",
            "timestamp": _utc_now(),
            "worker_pid": os.getpid(),
            "worker_generation_id": _bayesian_worker_generation_proof.generation_id,
            "old_pid": result.old_pid,
            "new_pid": result.new_pid,
            "elapsed_seconds": result.elapsed_seconds,
            "worker_connection_count": (
                _bayesian_worker_generation_proof.worker_connection_count
            ),
            "observer_connection_count": (
                _bayesian_worker_generation_proof.observer_connection_count
            ),
            "generation_authority_file": bool(_bayesian_generation_authority_file),
        }
    )


def _derive_bayesian_child_authority_if_needed() -> None:
    """Derive fork-child authority without opening a database connection."""

    global _bayesian_execution_authority
    if bayesian_worker_boot_topology_probe_has_passed():
        return
    try:
        _bayesian_execution_authority = _derive_process_authority_from_generation()
    except BayesianWorkerBootTopologyProofMissing as exc:
        logger.critical(
            "bayesian_worker_child_authority_failed",
            extra={
                "event_type": "bayesian.worker_child_authority",
                "worker_pid": os.getpid(),
                "error": str(exc),
            },
        )
        _append_probe_event(
            {
                "event": "bayesian_worker_child_authority_failed",
                "timestamp": _utc_now(),
                "worker_pid": os.getpid(),
                "error": str(exc),
            }
        )
        raise SystemExit("bayesian_worker_child_authority_failed") from exc
    logger.info(
        "bayesian_worker_child_authorized",
        extra={
            "event_type": "bayesian.worker_child_authority",
            "worker_pid": os.getpid(),
            "worker_generation_id": _bayesian_execution_authority.generation_id,
            "derivation_elapsed_seconds": (
                _bayesian_execution_authority.derivation_elapsed_seconds
            ),
        },
    )
    _append_probe_event(
        {
            "event": "bayesian_worker_child_authorized",
            "timestamp": _utc_now(),
            "worker_pid": os.getpid(),
            "worker_generation_id": _bayesian_execution_authority.generation_id,
            "derivation_elapsed_seconds": (
                _bayesian_execution_authority.derivation_elapsed_seconds
            ),
        }
    )


def _on_bayesian_worker_init(**kwargs) -> None:
    _run_bayesian_worker_boot_topology_probe_if_needed()


def _on_bayesian_worker_process_init(**kwargs) -> None:
    _derive_bayesian_child_authority_if_needed()


def ensure_bayesian_worker_boot_probe_signal_registered() -> None:
    """Register the Bayesian boot probe on worker parent and child lifecycles."""

    global _bayesian_boot_topology_probe_signal_registered
    if _bayesian_boot_topology_probe_signal_registered:
        return
    signals.worker_init.connect(_on_bayesian_worker_init, weak=False)
    signals.worker_process_init.connect(_on_bayesian_worker_process_init, weak=False)
    _bayesian_boot_topology_probe_signal_registered = True
