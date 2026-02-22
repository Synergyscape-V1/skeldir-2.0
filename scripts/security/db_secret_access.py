#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys


def _ensure_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_path = repo_root / "backend"
    backend_str = str(backend_path)
    if backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def resolve_runtime_database_url() -> str:
    _ensure_backend_on_path()
    from app.core.secrets import get_database_url

    return get_database_url()


def resolve_migration_database_url() -> str:
    _ensure_backend_on_path()
    from app.core.secrets import get_migration_database_url

    return get_migration_database_url()
