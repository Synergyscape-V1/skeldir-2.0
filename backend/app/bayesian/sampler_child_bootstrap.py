"""Stdlib-only bootstrap for isolated sampler child processes.

The supervisor executes this file by path, not through ``-m app...``. That lets
the bootstrap install import and multiprocessing policy before any Skeldir
package is imported.
"""

from __future__ import annotations

import importlib.abc
import os
import sys


FORBIDDEN_IMPORT_PREFIXES = (
    "sqlalchemy",
    "asyncpg",
    "psycopg",
    "psycopg2",
    "celery",
    "app.celery_app",
    "app.core.config",
    "app.core.secrets",
    "app.database",
    "app.db",
    "app.bayesian.models",
    "app.bayesian.runtime_state",
    "app.tasks",
)


class _SamplerChildForbiddenImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(
        self, fullname: str, path: object | None, target: object | None = None
    ) -> object | None:
        if _is_forbidden_import(fullname):
            raise ImportError(
                "B2.4-P5 sampler child boot import blocked before app import: "
                f"{fullname}"
            )
        return None


def _is_forbidden_import(fullname: str) -> bool:
    return any(
        fullname == prefix or fullname.startswith(prefix + ".")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def _forbidden_modules_in_cache() -> tuple[str, ...]:
    return tuple(sorted(name for name in sys.modules if _is_forbidden_import(name)))


def _install_import_airgap_at_boot() -> None:
    leaked = _forbidden_modules_in_cache()
    sys._b24_p5_airgap_preinstall_forbidden = leaked
    if leaked:
        raise RuntimeError(
            "B2.4-P5 sampler child forbidden modules were cached before "
            f"airgap bootstrap: {list(leaked)}"
        )
    if not any(
        isinstance(finder, _SamplerChildForbiddenImportBlocker)
        for finder in sys.meta_path
    ):
        sys.meta_path.insert(0, _SamplerChildForbiddenImportBlocker())
    sys._b24_p5_airgap_bootstrap_active = True


def _install_multiprocessing_guards_at_boot() -> None:
    import multiprocessing

    original_get_context = multiprocessing.get_context

    def blocked_fork(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("B2.4-P5 sampler child forbids os.fork")

    def blocked_get_context(method: str | None = None) -> object:
        raise RuntimeError(
            "B2.4-P5 sampler child is single-process-only; "
            f"multiprocessing context requested: {method or 'default'}"
        )

    def blocked_process(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "B2.4-P5 sampler child forbids multiprocessing.Process"
        )

    if hasattr(os, "fork"):
        os.fork = blocked_fork  # type: ignore[assignment]
    sys._b24_p5_original_multiprocessing_get_context = original_get_context
    multiprocessing.get_context = blocked_get_context  # type: ignore[assignment]
    multiprocessing.Process = blocked_process  # type: ignore[assignment]
    sys._b24_p5_multiprocessing_policy = "single-process"
    sys._b24_p5_multiprocessing_guard_active = True


def main() -> int:
    if os.environ.get("B24_SAMPLER_CHILD_BOOTSTRAP") != "1":
        raise RuntimeError("B2.4-P5 sampler child bootstrap flag is missing")
    _install_import_airgap_at_boot()
    _install_multiprocessing_guards_at_boot()
    from app.bayesian.sampler_child import main as sampler_child_main

    return sampler_child_main()


if __name__ == "__main__":
    raise SystemExit(main())
