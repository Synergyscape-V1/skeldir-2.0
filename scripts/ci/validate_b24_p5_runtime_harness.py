#!/usr/bin/env python3
"""Validate B2.4-P5 Bayesian runtime harness and native safety boundaries."""

from __future__ import annotations

import argparse
import ast
import os
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
RUNTIME_POLICY = BAYESIAN_PACKAGE / "runtime_policy.py"
SAMPLER_SUPERVISOR = BAYESIAN_PACKAGE / "sampler_supervisor.py"
RUNTIME_PROBE = BAYESIAN_PACKAGE / "runtime_probe.py"
RUNTIME_STATE = BAYESIAN_PACKAGE / "runtime_state.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
BAYESIAN_REQUIREMENTS = Path("backend/requirements-bayesian.txt")
BAYESIAN_DOCKERFILE = Path("backend/Dockerfile.bayesian")
P5_MIGRATION = Path("alembic/versions/007_skeldir_foundation/202605281200_b24_p5_runtime_statuses.py")
P5_TESTS = Path("backend/tests/test_b24_p5_runtime_harness.py")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
ENFORCER_REGISTRY = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_MATRIX = Path("docs/ci/gate_subsumption_matrix.yaml")

REQUIRED_FILES = {
    RUNTIME_POLICY,
    SAMPLER_SUPERVISOR,
    RUNTIME_PROBE,
    RUNTIME_STATE,
    BAYESIAN_REQUIREMENTS,
    BAYESIAN_DOCKERFILE,
    P5_MIGRATION,
    P5_TESTS,
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_dependency_lane() -> None:
    requirements = _read(BAYESIAN_REQUIREMENTS)
    dockerfile = _read(BAYESIAN_DOCKERFILE)
    for token in ("pymc==", "arviz==", "threadpoolctl=="):
        _require(token in requirements, f"Bayesian dependency lane missing pin: {token}")
    _require("pytensor==" not in requirements, "PyTensor must remain resolver-compatible with pinned PyMC")
    for token in (
        "python:3.11-slim",
        "requirements-bayesian.txt",
        "build-essential",
        "libopenblas-dev",
        "B24_BAYESIAN_WORKER_RUNTIME_ID",
        "OMP_NUM_THREADS=1",
        "OPENBLAS_NUM_THREADS=1",
        "MKL_NUM_THREADS=1",
        "NUMEXPR_NUM_THREADS=1",
        "VECLIB_MAXIMUM_THREADS=1",
        "B24_PYTENSOR_COMPILEDIR=/tmp/skeldir-b24-pytensor/worker",
        "PYTENSOR_FLAGS=base_compiledir=/tmp/skeldir-b24-pytensor/worker",
        "celery",
        "--concurrency=1",
    ):
        _require(token in dockerfile, f"Bayesian worker image missing runtime proof token: {token}")


def validate_runtime_policy(text: str | None = None) -> None:
    text = text if text is not None else _read(RUNTIME_POLICY)
    for token in (
        "THREAD_ENV_VARS",
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
        "B24_BAYESIAN_WORKER_CONCURRENCY",
        "B24_PYMC_CORES",
        "B24_PYMC_CHAINS",
        "B24_BLAS_TOTAL_THREADS",
        "B24_BAYESIAN_CPU_BUDGET",
        "B24_PYTENSOR_COMPILEDIR",
        "base_compiledir=",
        "re.sub",
        "sampler_supervisor_deadline_s < self.celery_soft_time_limit_s",
        "apply_native_runtime_environment",
    ):
        _require(token in text, f"runtime policy missing: {token}")
    _require(
        "total_native_threads = self.worker_concurrency * self.pymc_cores * self.blas_total_threads" in text,
        "native thread budget formula missing",
    )


def validate_supervisor(text: str | None = None) -> None:
    text = text if text is not None else _read(SAMPLER_SUPERVISOR)
    for token in (
        "start_new_session",
        "CREATE_NEW_PROCESS_GROUP",
        "os.killpg",
        "taskkill",
        "SIGKILL",
        "run_supervised_sampler",
        "synthetic_blocking_child_command",
        "SIG_IGN",
        "orphan_reaped",
    ):
        _require(token in text, f"sampler supervisor missing kill semantic: {token}")


def validate_runtime_probe(text: str | None = None) -> None:
    text = text if text is not None else _read(RUNTIME_PROBE)
    for token in (
        "import_smoke",
        "pytensor_compile",
        "tiny_benchmark",
        "thread_budget",
        "compiledir_concurrency",
        "supervisor_kill",
        "runtime_report",
        "pm.Model",
        "pm.sample",
        "pytensor.function",
        "threadpool_info",
        "compute_convergence_checks=False",
    ):
        _require(token in text, f"runtime probe missing: {token}")
    _require("raise RuntimeError" in text, "runtime probes must fail closed")
    tree = ast.parse(text, filename=RUNTIME_PROBE.as_posix())
    top_level_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    _require("pymc" not in top_level_imports, "PyMC must not import before runtime env caps are applied")


def validate_runtime_state(text: str | None = None) -> None:
    text = text if text is not None else _read(RUNTIME_STATE)
    for token in (
        "bind_runtime_tenant_context",
        "mark_fit_timeout",
        "sweep_stale_running_fits",
        "set_config('app.current_tenant_id'",
        "tenant_id: UUID",
        "WHERE tenant_id = :tenant_id",
        "status IN ('queued', 'running')",
        "FitStatus.TIMEOUT",
        "FitStatus.WORKER_LOST",
        "FallbackReason.TIMEOUT",
        "FallbackReason.WORKER_FAILURE",
        "credible_interval_status = 'not_available'",
        "UPDATE public.bayesian_model_fits",
    ):
        _require(token in text, f"runtime state persistence missing: {token}")
    for forbidden in (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    ):
        _require(forbidden not in text, f"P5 mutates deterministic truth: {forbidden}")


def validate_schema_statuses() -> None:
    for path in (ENUMS, MODELS, P5_MIGRATION):
        text = _read(path)
        _require("timeout" in text, f"{path.as_posix()} missing timeout status")
        _require("worker_lost" in text, f"{path.as_posix()} missing worker_lost status")


def validate_boundary() -> None:
    for path in sorted((ROOT / BAYESIAN_PACKAGE).glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        _require("APIRouter" not in text, f"public route symbol forbidden in {rel}")
        _require("include_router" not in text, f"router registration forbidden in {rel}")
        _require("app.llm" not in text, f"LLM import forbidden in {rel}")
        _require("openai" not in text.lower(), f"provider SDK forbidden in {rel}")
        _require("anthropic" not in text.lower(), f"provider SDK forbidden in {rel}")
    frontend_root = ROOT / "frontend"
    if frontend_root.exists():
        for current, dirs, files in os.walk(frontend_root):
            dirs[:] = [name for name in dirs if name not in {"node_modules", ".next", "dist", "build"}]
            for filename in files:
                path = Path(current) / filename
                if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx"}:
                    text = path.read_text(encoding="utf-8", errors="replace").lower()
                    _require(
                        "bayesian confidence threshold" not in text,
                        "frontend Bayesian threshold logic forbidden",
                    )


def validate_ci_wiring() -> None:
    workflow = _read(WORKFLOW)
    makefile = _read(MAKEFILE)
    registry = _read(ENFORCER_REGISTRY)
    subsumption = _read(SUBSUMPTION_MATRIX)
    for token in (
        "validate-b24-p5-runtime-harness",
        "B2.4-P5 Bayesian Runtime Harness",
        "docker build",
        "backend/Dockerfile.bayesian",
        "runtime-report",
        "pytensor-compile",
        "tiny-benchmark",
        "supervisor-kill",
    ):
        _require(token in workflow, f"P5 workflow wiring missing: {token}")
    _require("validate-b24-p5-runtime-harness" in makefile, "Makefile missing P5 validator target")
    _require("validate-b24-p5-runtime-harness" in registry, "enforcer registry missing P5 gate")
    _require("validate-b24-p5-runtime-harness" in subsumption, "gate subsumption matrix missing P5 gate")


def validate_tests() -> None:
    tests = _read(P5_TESTS)
    for token in (
        "test_b24_p5_thread_budget_rejects_oversubscription",
        "test_b24_p5_timeout_hierarchy_is_enforced",
        "test_b24_p5_supervisor_kills_blocking_child",
        "test_b24_p5_runtime_state_writes_only_bayesian_table",
        "test_b24_p5_probe_does_not_import_pymc_before_env_caps",
    ):
        _require(token in tests, f"missing P5 test: {token}")


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_dependency_lane()
    validate_runtime_policy()
    validate_supervisor()
    validate_runtime_probe()
    validate_runtime_state()
    validate_schema_statuses()
    validate_boundary()
    validate_ci_wiring()
    validate_tests()


def run_negative_controls() -> None:
    controls = (
        ("missing_thread_cap", lambda: validate_runtime_policy(_read(RUNTIME_POLICY).replace("OPENBLAS_NUM_THREADS", "OPENBLAS_THREADS_REMOVED")), "OPENBLAS"),
        ("missing_process_group", lambda: validate_supervisor(_read(SAMPLER_SUPERVISOR).replace("start_new_session", "same_session")), "start_new_session"),
        ("missing_benchmark", lambda: validate_runtime_probe(_read(RUNTIME_PROBE).replace("pm.sample", "mock_sample")), "pm.sample"),
        ("missing_timeout_write", lambda: validate_runtime_state(_read(RUNTIME_STATE).replace("FitStatus.TIMEOUT", "FitStatus.FAILED")), "FitStatus.TIMEOUT"),
        ("missing_tenant_guc", lambda: validate_runtime_state(_read(RUNTIME_STATE).replace("set_config('app.current_tenant_id'", "set_config('missing_tenant'")), "set_config"),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P5_RUNTIME_HARNESS_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P5_RUNTIME_HARNESS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
