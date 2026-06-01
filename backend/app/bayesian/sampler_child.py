"""DB-airgapped sampler child entrypoint for B2.4-P5 runtime probes."""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import json
import multiprocessing
import os
import signal
import sys
import time
from pathlib import Path


FORBIDDEN_ENV_FRAGMENTS = (
    "DATABASE",
    "DB_",
    "PG",
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "KEY",
    "CREDENTIAL",
    "AWS_",
    "GCP_",
    "AZURE_",
    "STRIPE",
    "SHOPIFY",
    "PAYPAL",
)

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


class _ForbiddenImportBlocker(importlib.abc.MetaPathFinder):
    def find_spec(
        self, fullname: str, path: object | None, target: object | None = None
    ) -> object | None:
        if any(
            fullname == prefix or fullname.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ):
            raise ImportError(
                f"B2.4-P5 sampler child DB/control-plane import blocked: {fullname}"
            )
        return None


def install_import_airgap() -> None:
    if not any(isinstance(finder, _ForbiddenImportBlocker) for finder in sys.meta_path):
        sys.meta_path.insert(0, _ForbiddenImportBlocker())


def _is_forbidden_module(name: str) -> bool:
    return any(
        name == prefix or name.startswith(prefix + ".")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def forbidden_sys_modules_snapshot() -> list[str]:
    return sorted(name for name in sys.modules if _is_forbidden_module(name))


def assert_boot_airgap_active() -> dict[str, object]:
    preinstall = sorted(
        str(name)
        for name in getattr(sys, "_b24_p5_airgap_preinstall_forbidden", ())
    )
    if preinstall:
        raise RuntimeError(
            "forbidden modules were cached before child airgap bootstrap: "
            f"{preinstall}"
        )
    if getattr(sys, "_b24_p5_airgap_bootstrap_active", False) is not True:
        raise RuntimeError("sampler child boot airgap was not installed by bootstrap")
    if getattr(sys, "_b24_p5_multiprocessing_guard_active", False) is not True:
        raise RuntimeError("sampler child multiprocessing guard is not active")
    cached = forbidden_sys_modules_snapshot()
    if cached:
        raise RuntimeError(f"forbidden modules cached in sampler child: {cached}")
    return {
        "boot_airgap_active": True,
        "preinstall_forbidden_modules": preinstall,
        "cached_forbidden_modules": cached,
        "multiprocessing_policy": getattr(
            sys, "_b24_p5_multiprocessing_policy", "unknown"
        ),
        "multiprocessing_guard_active": True,
        "multiprocessing_start_method": multiprocessing.get_start_method(
            allow_none=True
        ),
    }


def assert_environment_airgap() -> list[str]:
    leaked = [
        name
        for name in sorted(os.environ)
        if any(fragment in name.upper() for fragment in FORBIDDEN_ENV_FRAGMENTS)
        and name not in {"PYTHONKEYRING_BACKEND"}
    ]
    if leaked:
        raise RuntimeError(
            f"sampler child received forbidden environment variables: {leaked}"
        )
    return leaked


def _write_json(path: str | None, payload: dict[str, object]) -> None:
    if not path:
        print(json.dumps(payload, sort_keys=True))
        return
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _attempt_forbidden_imports() -> dict[str, object]:
    blocked: list[str] = []
    unexpected: list[str] = []
    before = forbidden_sys_modules_snapshot()
    if before:
        raise RuntimeError(f"forbidden modules cached before import attempts: {before}")
    for module in FORBIDDEN_IMPORT_PREFIXES:
        try:
            importlib.util.find_spec(module)
        except ImportError:
            blocked.append(module)
        else:
            unexpected.append(module)
    if unexpected:
        raise RuntimeError(f"forbidden imports unexpectedly succeeded: {unexpected}")
    after = forbidden_sys_modules_snapshot()
    if after:
        raise RuntimeError(f"forbidden modules cached after blocked attempts: {after}")
    return {
        "blocked_imports": blocked,
        "unexpected_imports": unexpected,
        "pre_attempt_forbidden_modules": before,
        "post_attempt_forbidden_modules": after,
    }


def _attempt_fork_multiprocessing_controls() -> dict[str, object]:
    blocked: dict[str, str] = {}
    if hasattr(os, "fork"):
        try:
            os.fork()
        except RuntimeError as exc:
            blocked["os.fork"] = str(exc)
        else:
            raise RuntimeError("os.fork negative control did not fail")
    try:
        multiprocessing.get_context("fork")
    except RuntimeError as exc:
        blocked["multiprocessing.get_context('fork')"] = str(exc)
    else:
        raise RuntimeError("fork context negative control did not fail")
    try:
        multiprocessing.get_context()
    except RuntimeError as exc:
        blocked["multiprocessing.get_context()"] = str(exc)
    else:
        raise RuntimeError("default context negative control did not fail")
    try:
        multiprocessing.Process(target=lambda: None)
    except RuntimeError as exc:
        blocked["multiprocessing.Process"] = str(exc)
    else:
        raise RuntimeError("multiprocessing.Process negative control did not fail")
    return blocked


def _run_sleep(seconds: int, marker: str | None) -> int:
    if marker:
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(0.2)
    return 0


def main() -> int:
    boot_report = assert_boot_airgap_active()
    install_import_airgap()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=(
            "env-report",
            "import-negative",
            "fork-negative",
            "boot-report",
            "sleep",
        ),
        required=True,
    )
    parser.add_argument("--output")
    parser.add_argument("--marker")
    parser.add_argument("--seconds", type=int, default=60)
    args = parser.parse_args()
    assert_environment_airgap()
    if os.name != "nt":
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    if args.mode == "env-report":
        payload = {
            "pid": os.getpid(),
            **boot_report,
            "env_keys": sorted(os.environ),
            "forbidden_env_present": [],
            "pytensor_compiledir": os.environ.get("B24_PYTENSOR_COMPILEDIR"),
        }
        _write_json(args.output, payload)
        return 0
    if args.mode == "import-negative":
        _write_json(
            args.output,
            {"pid": os.getpid(), **boot_report, **_attempt_forbidden_imports()},
        )
        return 0
    if args.mode == "fork-negative":
        _write_json(
            args.output,
            {
                "pid": os.getpid(),
                **boot_report,
                "blocked_controls": _attempt_fork_multiprocessing_controls(),
            },
        )
        return 0
    if args.mode == "boot-report":
        _write_json(args.output, {"pid": os.getpid(), **boot_report})
        return 0
    if args.mode == "sleep":
        return _run_sleep(args.seconds, args.marker)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
