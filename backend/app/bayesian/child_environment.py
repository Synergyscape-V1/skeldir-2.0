"""Explicit allowlist environment builder for sampler child processes."""

from __future__ import annotations

import os
from pathlib import Path


ALLOWLISTED_CHILD_ENV = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTENSOR_FLAGS",
        "B24_BAYESIAN_WORKER_RUNTIME_ID",
        "B24_BAYESIAN_WORKER_CONCURRENCY",
        "B24_PYMC_CORES",
        "B24_PYMC_CHAINS",
        "B24_BLAS_TOTAL_THREADS",
        "B24_BAYESIAN_CPU_BUDGET",
        "B24_PYTENSOR_ROOT",
        "B24_PYTENSOR_COMPILEDIR",
        "B24_PYTENSOR_EXECUTION_ID",
        "B24_SAMPLER_CHILD_BOOTSTRAP",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    }
)


def build_sampler_child_env(
    *,
    compiledir: Path,
    execution_id: str,
    source_env: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build sampler child env from an explicit allowlist; never blacklist-copy."""

    source = source_env if source_env is not None else os.environ
    env = {name: source[name] for name in ALLOWLISTED_CHILD_ENV if name in source}
    env["B24_PYTENSOR_COMPILEDIR"] = str(compiledir)
    env["B24_PYTENSOR_EXECUTION_ID"] = execution_id
    env["B24_SAMPLER_CHILD_BOOTSTRAP"] = "1"
    flags = env.get("PYTENSOR_FLAGS", "")
    parts = [
        part
        for part in flags.split(",")
        if part and not part.startswith("base_compiledir=")
    ]
    parts.insert(0, f"base_compiledir={compiledir.as_posix()}")
    env["PYTENSOR_FLAGS"] = ",".join(parts)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env
