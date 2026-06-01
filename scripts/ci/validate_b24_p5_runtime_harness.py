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
RUNTIME_IDENTITY = BAYESIAN_PACKAGE / "runtime_identity.py"
CHILD_ENVIRONMENT = BAYESIAN_PACKAGE / "child_environment.py"
SAMPLER_CHILD = BAYESIAN_PACKAGE / "sampler_child.py"
SAMPLER_CHILD_BOOTSTRAP = BAYESIAN_PACKAGE / "sampler_child_bootstrap.py"
COMPILEDIR_REAPER = BAYESIAN_PACKAGE / "compiledir_reaper.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
BAYESIAN_REQUIREMENTS = Path("backend/requirements-bayesian.txt")
BAYESIAN_DOCKERFILE = Path("backend/Dockerfile.bayesian")
P5_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605281200_b24_p5_runtime_statuses.py"
)
P5_TESTS = Path("backend/tests/test_b24_p5_runtime_harness.py")
P5_POSTGRES_TESTS = Path("backend/tests/test_b24_p5_postgres_runtime.py")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
ENFORCER_REGISTRY = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_MATRIX = Path("docs/ci/gate_subsumption_matrix.yaml")

REQUIRED_FILES = {
    RUNTIME_POLICY,
    SAMPLER_SUPERVISOR,
    RUNTIME_PROBE,
    RUNTIME_STATE,
    RUNTIME_IDENTITY,
    CHILD_ENVIRONMENT,
    SAMPLER_CHILD,
    SAMPLER_CHILD_BOOTSTRAP,
    COMPILEDIR_REAPER,
    BAYESIAN_REQUIREMENTS,
    BAYESIAN_DOCKERFILE,
    P5_MIGRATION,
    P5_TESTS,
    P5_POSTGRES_TESTS,
}


class ValidationError(RuntimeError):
    pass


FORBIDDEN_CHILD_IMPORT_PREFIXES = (
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

CHILD_ENTRYPOINT_TOP_LEVEL_ALLOWLIST = {
    "__future__",
    "argparse",
    "importlib",
    "importlib.abc",
    "importlib.util",
    "json",
    "multiprocessing",
    "os",
    "pathlib",
    "signal",
    "sys",
    "time",
}


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _is_forbidden_child_import(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in FORBIDDEN_CHILD_IMPORT_PREFIXES
    )


def _top_level_imports(text: str, *, filename: str) -> set[str]:
    tree = ast.parse(text, filename=filename)
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")
    return imports


def validate_dependency_lane() -> None:
    requirements = _read(BAYESIAN_REQUIREMENTS)
    dockerfile = _read(BAYESIAN_DOCKERFILE)
    for token in (
        "pymc==5.28.5",
        "pytensor==2.38.3",
        "arviz==0.23.4",
        "threadpoolctl==3.6.0",
    ):
        _require(
            token in requirements, f"Bayesian dependency lane missing pin: {token}"
        )
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
        "B24_PYTENSOR_ROOT=/tmp/skeldir-b24-pytensor",
        "PYTENSOR_FLAGS=mode=FAST_RUN,linker=cvm",
        "celery",
        "--concurrency=1",
    ):
        _require(
            token in dockerfile,
            f"Bayesian worker image missing runtime proof token: {token}",
        )
    _require(
        "B24_PYTENSOR_COMPILEDIR=/tmp/skeldir-b24-pytensor/worker" not in dockerfile,
        "Bayesian worker image must not use static worker-scoped PyTensor compiledir",
    )


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
        "B24_PYTENSOR_ROOT",
        "B24_PYTENSOR_EXECUTION_ID",
        "base_compiledir=",
        "re.sub",
        "sampler_supervisor_deadline_s",
        "celery_soft_time_limit_s",
        "celery_hard_time_limit_s",
        "apply_native_runtime_environment",
        "parent-",
        "execution_id",
    ):
        _require(token in text, f"runtime policy missing: {token}")
    normalized = re.sub(r"\s+", " ", text)
    _require(
        "total_native_threads = ( self.worker_concurrency * self.pymc_cores * self.blas_total_threads )"
        in normalized,
        "native thread budget formula missing",
    )


def validate_supervisor(text: str | None = None) -> None:
    text = text if text is not None else _read(SAMPLER_SUPERVISOR)
    for token in (
        "start_new_session",
        "CREATE_NEW_PROCESS_GROUP",
        "close_fds",
        "PR_SET_PDEATHSIG",
        "os.killpg",
        "taskkill",
        "SIGKILL",
        "run_supervised_sampler",
        "build_child_env_for_lease",
        "cleanup_compiledir",
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
        "compiledir_lifecycle",
        "reaper_probe",
        "child_env_airgap",
        "child_import_airgap",
        "parent_death",
        "behavioral_negative_controls",
        "supervisor_kill",
        "runtime_report",
        "pm.Model",
        "pm.sample",
        "pymc_single_process_sample_kwargs",
        "**sample_policy",
        "single-process",
        "pytensor.function",
        "threadpool_info",
        "compute_convergence_checks=False",
        "assert_runtime_identity",
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
    _require(
        "pymc" not in top_level_imports,
        "PyMC must not import before runtime env caps are applied",
    )


def validate_runtime_state(text: str | None = None) -> None:
    text = text if text is not None else _read(RUNTIME_STATE)
    for token in (
        "bind_runtime_tenant_context",
        "mark_fit_timeout",
        "mark_fit_timeout_sync",
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


def validate_runtime_identity(text: str | None = None) -> None:
    text = text if text is not None else _read(RUNTIME_IDENTITY)
    for token in (
        "EXPECTED_RUNTIME_IDENTITY",
        '"pytensor": "2.38.3"',
        "collect_runtime_identity",
        "assert_runtime_identity",
        "compiler_required",
    ):
        _require(token in text, f"runtime identity lock missing: {token}")


def validate_child_airgap(text: str | None = None) -> None:
    child_env = text if text is not None else _read(CHILD_ENVIRONMENT)
    child = _read(SAMPLER_CHILD)
    for token in (
        "ALLOWLISTED_CHILD_ENV",
        "build_sampler_child_env",
        "source_env if source_env is not None else os.environ",
        "B24_PYTENSOR_COMPILEDIR",
        "B24_SAMPLER_CHILD_BOOTSTRAP",
    ):
        _require(token in child_env, f"child environment allowlist missing: {token}")
    _require(
        "os.environ.copy()" not in child_env,
        "child env must not blacklist-copy parent environment",
    )
    for forbidden in (
        "DATABASE_URL",
        "SKELDIR_FAKE_PARENT_SECRET",
        "AWS_SECRET_ACCESS_KEY",
        "STRIPE_API_KEY",
    ):
        _require(
            forbidden not in child_env,
            f"secret-like env must not be allowlisted: {forbidden}",
        )
    for token in (
        "FORBIDDEN_IMPORT_PREFIXES",
        "sqlalchemy",
        "asyncpg",
        "psycopg",
        "app.bayesian.runtime_state",
        "app.tasks",
        "install_import_airgap",
        "assert_boot_airgap_active",
        "preinstall_forbidden_modules",
        "pre_attempt_forbidden_modules",
        "post_attempt_forbidden_modules",
        "fork-negative",
        "assert_environment_airgap",
    ):
        _require(token in child, f"sampler child airgap missing: {token}")


def validate_sampler_child_boot_airgap(
    child_text: str | None = None,
    bootstrap_text: str | None = None,
    child_env_text: str | None = None,
) -> None:
    child = child_text if child_text is not None else _read(SAMPLER_CHILD)
    bootstrap = (
        bootstrap_text
        if bootstrap_text is not None
        else _read(SAMPLER_CHILD_BOOTSTRAP)
    )
    child_env = (
        child_env_text if child_env_text is not None else _read(CHILD_ENVIRONMENT)
    )
    imports = _top_level_imports(child, filename=SAMPLER_CHILD.as_posix())
    forbidden_imports = sorted(
        module for module in imports if _is_forbidden_child_import(module)
    )
    _require(
        not forbidden_imports,
        f"sampler child top-level forbidden import before airgap: {forbidden_imports}",
    )
    disallowed = sorted(imports - CHILD_ENTRYPOINT_TOP_LEVEL_ALLOWLIST)
    _require(
        not disallowed,
        f"sampler child top-level import is not explicitly child-safe: {disallowed}",
    )
    bootstrap_imports = _top_level_imports(
        bootstrap, filename=SAMPLER_CHILD_BOOTSTRAP.as_posix()
    )
    bootstrap_forbidden = sorted(
        module for module in bootstrap_imports if _is_forbidden_child_import(module)
    )
    _require(
        not bootstrap_forbidden,
        f"sampler child bootstrap top-level forbidden import: {bootstrap_forbidden}",
    )
    bootstrap_disallowed = sorted(
        bootstrap_imports
        - {"__future__", "importlib.abc", "os", "sys"}
    )
    _require(
        not bootstrap_disallowed,
        "sampler child bootstrap top-level import is not stdlib-only: "
        f"{bootstrap_disallowed}",
    )
    for token in (
        'os.environ.get("B24_SAMPLER_CHILD_BOOTSTRAP") != "1"',
        "_install_import_airgap_at_boot",
        "_forbidden_modules_in_cache",
        "sys._b24_p5_airgap_preinstall_forbidden",
        "sys._b24_p5_airgap_bootstrap_active = True",
        "_SamplerChildForbiddenImportBlocker",
    ):
        _require(token in bootstrap, f"sampler child bootstrap missing: {token}")
    _require(
        "from app.bayesian.sampler_child import main as sampler_child_main"
        in bootstrap,
        "sampler child bootstrap must import sampler_child only after guard install",
    )
    _require(
        'env["B24_SAMPLER_CHILD_BOOTSTRAP"] = "1"' in child_env,
        "sampler child env must force bootstrap flag",
    )


def validate_physical_multiprocessing_containment(
    bootstrap_text: str | None = None, child_text: str | None = None
) -> None:
    bootstrap = (
        bootstrap_text
        if bootstrap_text is not None
        else _read(SAMPLER_CHILD_BOOTSTRAP)
    )
    child = child_text if child_text is not None else _read(SAMPLER_CHILD)
    for token in (
        "_install_multiprocessing_guards_at_boot",
        "os.fork = blocked_fork",
        "multiprocessing.get_context = blocked_get_context",
        "multiprocessing.Process = blocked_process",
        'sys._b24_p5_multiprocessing_policy = "single-process"',
        "sys._b24_p5_multiprocessing_guard_active = True",
    ):
        _require(
            token in bootstrap,
            f"sampler child physical multiprocessing guard missing: {token}",
        )
    for token in (
        "_attempt_fork_multiprocessing_controls",
        "multiprocessing.get_context(\"fork\")",
        "multiprocessing.get_context()",
        "multiprocessing.Process",
        "multiprocessing_guard_active",
    ):
        _require(token in child, f"sampler child fork negative control missing: {token}")
    for path in sorted((ROOT / BAYESIAN_PACKAGE).glob("*.py")):
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8", errors="replace")
        if rel == SAMPLER_CHILD:
            continue
        tree = ast.parse(text, filename=rel.as_posix())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            owner = node.func.value
            if (
                isinstance(owner, ast.Name)
                and owner.id == "os"
                and node.func.attr == "fork"
            ):
                raise ValidationError(f"os.fork forbidden in {rel.as_posix()}")
            if isinstance(owner, ast.Name) and owner.id == "multiprocessing":
                if node.func.attr == "Process":
                    raise ValidationError(
                        f"default multiprocessing.Process forbidden in {rel.as_posix()}"
                    )
                if node.func.attr == "get_context":
                    raise ValidationError(
                        "multiprocessing context acquisition forbidden in "
                        f"{rel.as_posix()}"
                    )


def validate_pymc_sampling_policy(runtime_probe_text: str | None = None) -> None:
    runtime_probe = (
        runtime_probe_text if runtime_probe_text is not None else _read(RUNTIME_PROBE)
    )
    _require(
        "pymc_single_process_sample_kwargs(policy)" in runtime_probe,
        "PyMC sample policy helper is not used before pm.sample",
    )
    _require("**sample_policy" in runtime_probe, "pm.sample must expand sample_policy")
    sample_calls: list[str] = []
    for path in sorted((ROOT / BAYESIAN_PACKAGE).glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        text = runtime_probe if path.relative_to(ROOT) == RUNTIME_PROBE else path.read_text(
            encoding="utf-8", errors="replace"
        )
        tree = ast.parse(text, filename=rel)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "sample"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "pm"
            ):
                sample_calls.append(f"{rel}:{node.lineno}")
                has_policy_expansion = any(
                    keyword.arg is None
                    and isinstance(keyword.value, ast.Name)
                    and keyword.value.id == "sample_policy"
                    for keyword in node.keywords
                )
                _require(
                    has_policy_expansion,
                    f"pm.sample bypasses P5 sample_policy at {rel}:{node.lineno}",
                )
    _require(sample_calls, "P5 PyMC sample inventory is empty")
    _require(len(sample_calls) == 1, f"unexpected P5 pm.sample inventory: {sample_calls}")
    _require(
        sample_calls[0].startswith(f"{RUNTIME_PROBE.as_posix()}:"),
        f"unexpected P5 pm.sample location: {sample_calls}",
    )


def validate_compiledir_reaper(text: str | None = None) -> None:
    text = text if text is not None else _read(COMPILEDIR_REAPER)
    for token in (
        "OWNER_MARKER",
        "METADATA_FILE",
        "create_compiledir_lease",
        "record_child_pid",
        "cleanup_compiledir",
        "reap_expired_compiledirs",
        "max_deletions",
        "max_scan_entries",
        "_reaper_lock",
        "preserved_foreign",
        "preserved_active",
        "parent-",
    ):
        _require(token in text, f"compiledir reaper missing: {token}")
    _require(
        "while True" not in text, "reaper must not be an unbounded background loop"
    )


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
        _require(
            "include_router" not in text, f"router registration forbidden in {rel}"
        )
        _require("app.llm" not in text, f"LLM import forbidden in {rel}")
        _require("openai" not in text.lower(), f"provider SDK forbidden in {rel}")
        _require("anthropic" not in text.lower(), f"provider SDK forbidden in {rel}")
    frontend_root = ROOT / "frontend"
    if frontend_root.exists():
        for current, dirs, files in os.walk(frontend_root):
            dirs[:] = [
                name
                for name in dirs
                if name not in {"node_modules", ".next", "dist", "build"}
            ]
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
        "B2.4-P5 PostgreSQL Runtime Proof",
        "docker build",
        "backend/Dockerfile.bayesian",
        "runtime-report",
        "pytensor-compile",
        "tiny-benchmark",
        "child-env-airgap",
        "child-boot-airgap",
        "child-import-airgap",
        "fork-multiprocessing-negative-controls",
        "compiledir-lifecycle",
        "reaper-probe",
        "parent-death",
        "behavioral-negative-controls",
        "supervisor-kill",
        "SKELDIR_B24_P5_REQUIRE_DB_PROOFS",
        "ENFORCE_RUNTIME_IDENTITY_PARITY",
        "test_b24_p5_postgres_runtime.py",
    ):
        _require(token in workflow, f"P5 workflow wiring missing: {token}")
    _require(
        "validate-b24-p5-runtime-harness" in makefile,
        "Makefile missing P5 validator target",
    )
    _require(
        "validate-b24-p5-runtime-harness" in registry,
        "enforcer registry missing P5 gate",
    )
    _require(
        "validate-b24-p5-runtime-harness" in subsumption,
        "gate subsumption matrix missing P5 gate",
    )


def validate_tests() -> None:
    tests = _read(P5_TESTS)
    postgres_tests = _read(P5_POSTGRES_TESTS)
    for token in (
        "test_b24_p5_thread_budget_rejects_oversubscription",
        "test_b24_p5_timeout_hierarchy_is_enforced",
        "test_b24_p5_supervisor_kills_blocking_child",
        "test_b24_p5_child_env_is_allowlisted",
        "test_b24_p5_child_runtime_blocks_db_imports",
        "test_b24_p5_child_boot_airgap_reports_preinstall_cache_empty",
        "test_b24_p5_child_fork_and_default_multiprocessing_are_blocked",
        "test_b24_p5_pymc_sample_uses_central_single_process_policy",
        "test_b24_p5_reaper_preserves_foreign_and_deletes_expired_owned",
        "test_b24_p5_runtime_state_writes_only_bayesian_table",
        "test_b24_p5_probe_does_not_import_pymc_before_env_caps",
    ):
        _require(token in tests, f"missing P5 test: {token}")
    for token in (
        "test_b24_p5_worker_timeout_fallback_persists_tenant_scoped_fit_state",
        "test_b24_p5_sampler_child_opens_zero_postgres_connections",
        "_emit_fallback_event",
        "durable_timeout_written",
        "tenant_b_row",
        "pg_stat_activity",
        "application_name=b24_p5_child_airgap",
        "pytest.mark.integration",
    ):
        _require(token in postgres_tests, f"missing P5 PostgreSQL proof token: {token}")


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_dependency_lane()
    validate_runtime_policy()
    validate_supervisor()
    validate_runtime_probe()
    validate_runtime_state()
    validate_runtime_identity()
    validate_child_airgap()
    validate_sampler_child_boot_airgap()
    validate_physical_multiprocessing_containment()
    validate_pymc_sampling_policy()
    validate_compiledir_reaper()
    validate_schema_statuses()
    validate_boundary()
    validate_ci_wiring()
    validate_tests()


def run_negative_controls() -> None:
    controls = (
        (
            "missing_thread_cap",
            lambda: validate_runtime_policy(
                _read(RUNTIME_POLICY).replace(
                    "OPENBLAS_NUM_THREADS", "OPENBLAS_THREADS_REMOVED"
                )
            ),
            "OPENBLAS",
        ),
        (
            "missing_process_group",
            lambda: validate_supervisor(
                _read(SAMPLER_SUPERVISOR).replace("start_new_session", "same_session")
            ),
            "start_new_session",
        ),
        (
            "missing_benchmark",
            lambda: validate_runtime_probe(
                _read(RUNTIME_PROBE).replace("pm.sample", "mock_sample")
            ),
            "pm.sample",
        ),
        (
            "missing_timeout_write",
            lambda: validate_runtime_state(
                _read(RUNTIME_STATE).replace("FitStatus.TIMEOUT", "FitStatus.FAILED")
            ),
            "FitStatus.TIMEOUT",
        ),
        (
            "missing_tenant_guc",
            lambda: validate_runtime_state(
                _read(RUNTIME_STATE).replace(
                    "set_config('app.current_tenant_id'", "set_config('missing_tenant'"
                )
            ),
            "set_config",
        ),
        (
            "missing_child_allowlist",
            lambda: validate_child_airgap(
                _read(CHILD_ENVIRONMENT).replace(
                    "ALLOWLISTED_CHILD_ENV", "ALLOWLIST_REMOVED"
                )
            ),
            "ALLOWLISTED_CHILD_ENV",
        ),
        (
            "forbidden_pre_airgap_import",
            lambda: validate_sampler_child_boot_airgap(
                "import sqlalchemy\n" + _read(SAMPLER_CHILD)
            ),
            "forbidden",
        ),
        (
            "missing_child_bootstrap_flag",
            lambda: validate_sampler_child_boot_airgap(
                child_env_text=_read(CHILD_ENVIRONMENT).replace(
                    'env["B24_SAMPLER_CHILD_BOOTSTRAP"] = "1"',
                    "# bootstrap flag removed",
                )
            ),
            "bootstrap",
        ),
        (
            "missing_boot_sysmodules_snapshot",
            lambda: validate_sampler_child_boot_airgap(
                bootstrap_text=_read(SAMPLER_CHILD_BOOTSTRAP).replace(
                    "sys._b24_p5_airgap_preinstall_forbidden",
                    "sys._b24_p5_airgap_preinstall_removed",
                )
            ),
            "preinstall",
        ),
        (
            "missing_fork_guard",
            lambda: validate_physical_multiprocessing_containment(
                bootstrap_text=_read(SAMPLER_CHILD_BOOTSTRAP).replace(
                    "os.fork = blocked_fork",
                    "# os.fork guard removed",
                )
            ),
            "os.fork",
        ),
        (
            "unsafe_pymc_sample_policy",
            lambda: validate_pymc_sampling_policy(
                _read(RUNTIME_PROBE).replace("**sample_policy,", "cores=2,")
            ),
            "sample_policy",
        ),
        (
            "missing_runtime_identity",
            lambda: validate_runtime_identity(
                _read(RUNTIME_IDENTITY).replace(
                    '"pytensor": "2.38.3"', '"pytensor": "0.0.0"'
                )
            ),
            "2.38.3",
        ),
        (
            "missing_reaper_bounds",
            lambda: validate_compiledir_reaper(
                _read(COMPILEDIR_REAPER).replace("max_deletions", "unbounded_deletions")
            ),
            "max_deletions",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason: {exc}",
            )
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
