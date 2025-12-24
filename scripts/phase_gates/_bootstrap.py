"""
Environment-invariant sys.path bootstrap for phase gate runners.

Why this exists:
- In CI we commonly execute runner entrypoints as files, e.g.:
    python scripts/phase_gates/run_phase.py VALUE_01
  In that mode, Python sets sys.path[0] to scripts/phase_gates/, which means
  *repo root* is NOT automatically importable. That can break:
    import scripts.phase_gates...

This module deterministically injects:
- REPO_ROOT (for scripts.*)
- BACKEND_ROOT (for app.*)

Design constraint:
- This module must be importable when sys.path[0] == scripts/phase_gates/.
  Therefore, runner scripts should import it as a *local module*:
      import _bootstrap; _bootstrap.bootstrap()
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _debug_enabled() -> bool:
    return os.environ.get("SKELDIR_BOOTSTRAP_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def bootstrap(*, verify_imports: bool = False) -> None:
    """
    Add repo root and backend/ to sys.path if not already present.

    - **repo root** enables imports like `scripts.phase_gates.*`
    - **backend root** enables imports like `app.*`
    """
    repo_root = Path(__file__).resolve().parents[2]
    backend_root = repo_root / "backend"

    repo_root_str = str(repo_root)
    backend_root_str = str(backend_root)

    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)
        if _debug_enabled():
            print(f"[bootstrap] sys.path += REPO_ROOT: {repo_root_str}")

    if backend_root_str not in sys.path:
        sys.path.insert(0, backend_root_str)
        if _debug_enabled():
            print(f"[bootstrap] sys.path += BACKEND_ROOT: {backend_root_str}")

    if verify_imports:
        # Verifications are intentionally cheap and fail-fast.
        import importlib

        importlib.import_module("scripts.phase_gates")
        importlib.import_module("app")


if __name__ == "__main__":
    os.environ.setdefault("SKELDIR_BOOTSTRAP_DEBUG", "1")
    bootstrap()
    print("[bootstrap] OK")
