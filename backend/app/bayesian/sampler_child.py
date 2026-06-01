"""DB-airgapped sampler child entrypoint for B2.4-P5 runtime probes."""

from __future__ import annotations

import argparse
import importlib.abc
import importlib.util
import json
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
    for module in FORBIDDEN_IMPORT_PREFIXES:
        try:
            importlib.util.find_spec(module)
        except ImportError:
            blocked.append(module)
        else:
            unexpected.append(module)
    if unexpected:
        raise RuntimeError(f"forbidden imports unexpectedly succeeded: {unexpected}")
    return {"blocked_imports": blocked, "unexpected_imports": unexpected}


def _run_sleep(seconds: int, marker: str | None) -> int:
    if marker:
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(0.2)
    return 0


def main() -> int:
    install_import_airgap()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("env-report", "import-negative", "sleep"), required=True
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
            "env_keys": sorted(os.environ),
            "forbidden_env_present": [],
            "pytensor_compiledir": os.environ.get("B24_PYTENSOR_COMPILEDIR"),
        }
        _write_json(args.output, payload)
        return 0
    if args.mode == "import-negative":
        _write_json(args.output, {"pid": os.getpid(), **_attempt_forbidden_imports()})
        return 0
    if args.mode == "sleep":
        return _run_sleep(args.seconds, args.marker)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
