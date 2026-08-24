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
from typing import Any


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
        str(name) for name in getattr(sys, "_b24_p5_airgap_preinstall_forbidden", ())
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


def _write_json_durable(path: str, payload: dict[str, object]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    with output.open("wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_parent_dir(output)


def _fsync_parent_dir(path: Path) -> None:
    if os.name == "nt":
        return
    fd = os.open(str(path.parent), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def emit_stage_marker(stage: str, **metadata: object) -> None:
    """Synchronously persist a child stage marker for post-SIGKILL recovery."""

    from datetime import datetime, timezone

    marker_raw = os.environ.get("B24_STAGE_MARKER_PATH")
    if not marker_raw:
        return
    marker = Path(marker_raw)
    marker.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "stage": stage,
        "pid": os.getpid(),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        **metadata,
    }
    line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    with marker.open("ab") as handle:
        handle.write(line.encode("utf-8"))
        handle.flush()
        os.fsync(handle.fileno())
    _fsync_parent_dir(marker)


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
    emit_stage_marker("input_loaded", mode="sleep")
    if marker:
        Path(marker).write_text(str(os.getpid()), encoding="utf-8")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        time.sleep(0.2)
    return 0


def _run_stage_marker_kill() -> int:
    emit_stage_marker("input_loaded", mode="stage-marker-kill")
    if os.name == "nt":
        os._exit(99)
    os.kill(os.getpid(), signal.SIGKILL)
    return 99


def _run_real_fit(input_path: str, output_path: str) -> int:
    emit_stage_marker("input_loaded", mode="real-fit")
    source = Path(input_path)
    if source.stat().st_size > 64 * 1024:
        raise RuntimeError("real-fit input exceeds B2.4-P6 transport cap")
    payload = json.loads(source.read_text(encoding="utf-8"))

    from app.bayesian.model_spec import B24_P6_MODEL_SPEC
    from app.bayesian.diagnostics import (
        DEFAULT_P7_DIAGNOSTIC_POLICY,
        compute_arviz_diagnostic_summary,
    )
    from app.bayesian.result_contract import validate_result_summary
    from app.bayesian.runtime_policy import (
        apply_native_runtime_environment,
        build_runtime_policy,
    )
    from app.bayesian.runtime_probe import run_single_process_pymc_sample
    from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY

    runtime_policy = apply_native_runtime_environment(build_runtime_policy())

    import numpy as np
    import pymc as pm

    observed_raw = payload.get("observed_signal", [0.0, 0.25, -0.25])
    observed = np.asarray(observed_raw, dtype=float)
    if observed.ndim != 1 or observed.size < 2:
        raise RuntimeError(
            "real-fit observed_signal must be a 1D array with >=2 values"
        )
    if not np.all(np.isfinite(observed)):
        raise RuntimeError("real-fit observed_signal contains non-finite values")

    policy = DEFAULT_P6_SAMPLING_POLICY
    policy.validate()
    if (
        int(payload.get("max_samples", policy.total_chain_iterations))
        < policy.total_chain_iterations
    ):
        raise RuntimeError("real-fit sampling policy exceeds fit max_samples")
    if int(payload.get("max_cores", policy.cores)) < policy.cores:
        raise RuntimeError("real-fit sampling policy exceeds fit max_cores")

    random_seed = int(payload["random_seed"])

    # The authority check, on the runtime this process actually resolved.
    #
    # Everything above validated the *fit* against policy. This validates the
    # policy against the *machine*, and it is the seam Corrective Action X
    # exists to close: the profile declared four chains while the shipped image
    # resolved one, and nothing compared them, so PyMC sampled a topology no
    # authority had approved and the diagnostics discovered it four minutes
    # later by failing. A refusal here costs nothing and happens before any
    # financial-compute authority is spent.
    from app.bayesian.inference_profile import (
        RuntimeProfileMismatchError,
        assert_observed_topology_matches_profile,
        assert_runtime_matches_profile,
    )

    emit_stage_marker("runtime_authority_check", mode="real-fit")
    try:
        runtime_correspondence = assert_runtime_matches_profile(runtime_policy)
    except RuntimeProfileMismatchError:
        emit_stage_marker("runtime_authority_rejected", mode="real-fit")
        raise

    started = time.monotonic()
    with pm.Model() as model:
        mu = pm.Normal("mu", mu=0.0, sigma=1.0)
        pm.Normal("observed_signal", mu=mu, sigma=1.0, observed=observed)
        emit_stage_marker("model_built", mode="real-fit")
        emit_stage_marker("graph_compiling", mode="real-fit")
        model.compile_logp()
        emit_stage_marker("graph_compiled", mode="real-fit")
        emit_stage_marker("sampling_started", mode="real-fit")
        trace: Any = run_single_process_pymc_sample(
            pm,
            runtime_policy,
            draws=policy.draws_per_chain,
            tune=policy.tune_per_chain,
            random_seed=random_seed,
            progressbar=False,
            compute_convergence_checks=False,
            discard_tuned_samples=True,
            return_inferencedata=True,
            target_accept=policy.target_accept,
            init=policy.init,
        )
    elapsed_seconds = time.monotonic() - started
    emit_stage_marker("sampling_completed", mode="real-fit")
    sample_stats = getattr(trace, "sample_stats", None)
    divergence_count = (
        int(np.asarray(sample_stats["diverging"].values).sum())
        if sample_stats is not None and "diverging" in sample_stats
        else 0
    )
    # What physically exists, measured on the object PyMC returned.
    #
    # These were `policy.chains` and `policy.posterior_draws_total` -- the
    # numbers the configuration intended. Under the shipped one-chain image
    # they would have recorded 4 and 4000 for a posterior that had 1 and 1000,
    # which is not a rounding error but a false statement about what happened,
    # persisted beside a hash and eventually signed.
    observed_chains = int(trace.posterior.sizes["chain"])
    observed_draws_per_chain = int(trace.posterior.sizes["draw"])
    try:
        observed = assert_observed_topology_matches_profile(
            observed_chains=observed_chains,
            observed_draws_per_chain=observed_draws_per_chain,
        )
    except RuntimeProfileMismatchError:
        emit_stage_marker("observed_topology_rejected", mode="real-fit")
        raise

    mu_values = np.asarray(trace.posterior["mu"].values, dtype=float)
    mu_mean = float(np.mean(mu_values))
    mu_sd = float(np.std(mu_values))
    fit_metadata = {
        "schema_version": "b24-p6-child-result-v1",
        "status": "sampled_unvalidated",
        "model_type": B24_P6_MODEL_SPEC.model_type,
        "model_version": B24_P6_MODEL_SPEC.model_version,
        "execution_id": str(payload["execution_id"]),
        "fit_id": str(payload["fit_id"]),
        "tenant_id": str(payload["tenant_id"]),
        "source_snapshot_hash": str(payload["source_snapshot_hash"]),
        "runtime_seconds": round(elapsed_seconds, 6),
        "execution_success": True,
        # Observed, not intended. See the measurement above.
        "n_chains": observed["observed_chains"],
        "n_samples_actual": observed["observed_posterior_draws_total"],
        # Both halves retained, so the correspondence is auditable rather than
        # merely asserted once and discarded.
        "authorized_chains": policy.chains,
        "authorized_posterior_draws_total": policy.posterior_draws_total,
        "observed_draws_per_chain": observed["observed_draws_per_chain"],
        "runtime_correspondence": runtime_correspondence,
        "divergence_count": divergence_count,
        "posterior_summary": {
            "mu_mean": mu_mean,
            "mu_sd": mu_sd,
        },
    }
    emit_stage_marker("diagnostics_started", mode="real-fit")
    result = compute_arviz_diagnostic_summary(
        trace,
        fit_metadata=fit_metadata,
        policy=DEFAULT_P7_DIAGNOSTIC_POLICY,
    )
    emit_stage_marker("diagnostics_completed", mode="real-fit")
    emit_stage_marker("intervals_started", mode="real-fit")
    emit_stage_marker("intervals_completed", mode="real-fit")
    validate_result_summary(result)
    _write_json_durable(output_path, result)
    emit_stage_marker("result_summary_written", mode="real-fit")
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
            "stage-marker-kill",
            "real-fit",
        ),
        required=True,
    )
    parser.add_argument("--output")
    parser.add_argument("--input")
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
    if args.mode == "stage-marker-kill":
        return _run_stage_marker_kill()
    if args.mode == "real-fit":
        if not args.input or not args.output:
            raise RuntimeError("real-fit mode requires --input and --output")
        return _run_real_fit(args.input, args.output)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
