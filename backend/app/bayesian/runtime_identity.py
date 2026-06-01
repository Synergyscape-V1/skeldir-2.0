"""Drift-failing runtime identity policy for the B2.4-P5 Bayesian lane."""

from __future__ import annotations

import json
import platform
import shutil
from dataclasses import dataclass
from importlib import import_module


EXPECTED_RUNTIME_IDENTITY = {
    "python_major_minor": "3.11",
    "pymc": "5.28.5",
    "pytensor": "2.38.3",
    "arviz": "0.23.4",
    "pytensor_mode": "FAST_RUN",
    "pytensor_linker": "cvm",
    "compiler_required": True,
}


@dataclass(frozen=True)
class RuntimeIdentityReport:
    python: str
    pymc: str
    pytensor: str
    arviz: str
    pytensor_mode: str
    pytensor_linker: str
    compiler: str | None

    def as_dict(self) -> dict[str, object]:
        return {
            "python": self.python,
            "pymc": self.pymc,
            "pytensor": self.pytensor,
            "arviz": self.arviz,
            "pytensor_mode": self.pytensor_mode,
            "pytensor_linker": self.pytensor_linker,
            "compiler": self.compiler,
        }


def collect_runtime_identity() -> RuntimeIdentityReport:
    """Collect import/runtime identity after native environment policy is active."""

    pm = import_module("pymc")
    pytensor = import_module("pytensor")
    az = import_module("arviz")
    return RuntimeIdentityReport(
        python=platform.python_version(),
        pymc=str(pm.__version__),
        pytensor=str(pytensor.__version__),
        arviz=str(az.__version__),
        pytensor_mode=str(getattr(pytensor.config, "mode", "")),
        pytensor_linker=str(getattr(pytensor.config, "linker", "")),
        compiler=shutil.which("gcc") or shutil.which("cc") or shutil.which("cl"),
    )


def assert_runtime_identity(report: RuntimeIdentityReport) -> None:
    """Fail closed when clean rebuild identity drifts from committed policy."""

    expected = EXPECTED_RUNTIME_IDENTITY
    if not report.python.startswith(str(expected["python_major_minor"]) + "."):
        raise RuntimeError(f"Python identity drift: {report.python}")
    for key in ("pymc", "pytensor", "arviz"):
        actual = getattr(report, key)
        if actual != expected[key]:
            raise RuntimeError(f"{key} identity drift: {actual} != {expected[key]}")
    if report.pytensor_mode != expected["pytensor_mode"]:
        raise RuntimeError(f"PyTensor mode drift: {report.pytensor_mode}")
    if report.pytensor_linker != expected["pytensor_linker"]:
        raise RuntimeError(f"PyTensor linker drift: {report.pytensor_linker}")
    if expected["compiler_required"] and not report.compiler:
        raise RuntimeError("compiler identity missing")


def expected_runtime_identity_json() -> str:
    return json.dumps(EXPECTED_RUNTIME_IDENTITY, sort_keys=True)
