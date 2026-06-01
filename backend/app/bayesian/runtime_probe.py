"""CLI probes for the B2.4-P5 Bayesian worker runtime."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.bayesian.runtime_policy import apply_native_runtime_environment, runtime_policy_json
from app.bayesian.sampler_supervisor import run_supervised_sampler, synthetic_blocking_child_command


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, sort_keys=True))


def import_smoke() -> dict[str, object]:
    policy = apply_native_runtime_environment()
    import arviz as az
    import pymc as pm
    import pytensor

    return {
        "probe": "import_smoke",
        "runtime": policy.as_runtime_record(),
        "pymc_version": pm.__version__,
        "pytensor_version": pytensor.__version__,
        "arviz_version": az.__version__,
    }


def pytensor_compile() -> dict[str, object]:
    policy = apply_native_runtime_environment()
    import numpy as np
    import pytensor
    import pytensor.tensor as pt

    x = pt.vector("x")
    fn = pytensor.function([x], x * 2 + 1, mode="FAST_RUN")
    value = fn(np.asarray([1.0, 2.0, 3.0])).tolist()
    linker = str(getattr(pytensor.config, "linker", ""))
    mode = str(getattr(pytensor.config, "mode", ""))
    if linker.lower() in {"py", "python"}:
        raise RuntimeError(f"invalid PyTensor linker fallback: {linker}")
    return {
        "probe": "pytensor_compile",
        "runtime": policy.as_runtime_record(),
        "mode": mode,
        "linker": linker,
        "compiledir": str(getattr(pytensor.config, "compiledir", "")),
        "value": value,
    }


def tiny_benchmark() -> dict[str, object]:
    policy = apply_native_runtime_environment()
    import numpy as np
    import pymc as pm

    started = time.monotonic()
    with pm.Model():
        mu = pm.Normal("mu", mu=0.0, sigma=1.0)
        pm.Normal("obs", mu=mu, sigma=1.0, observed=np.asarray([0.0, 0.1, -0.1]))
        idata = pm.sample(
            draws=20,
            tune=20,
            chains=policy.pymc_chains,
            cores=policy.pymc_cores,
            random_seed=42,
            progressbar=False,
            compute_convergence_checks=False,
            discard_tuned_samples=True,
        )
    elapsed = time.monotonic() - started
    if elapsed > policy.benchmark_threshold_s:
        raise RuntimeError(
            f"tiny PyMC benchmark exceeded threshold: {elapsed:.3f}s > {policy.benchmark_threshold_s:.3f}s"
        )
    return {
        "probe": "tiny_benchmark",
        "elapsed_seconds": round(elapsed, 3),
        "threshold_seconds": policy.benchmark_threshold_s,
        "chains": policy.pymc_chains,
        "cores": policy.pymc_cores,
        "posterior_vars": sorted(idata.posterior.data_vars),
    }


def thread_budget() -> dict[str, object]:
    policy = apply_native_runtime_environment()
    import numpy as np

    np.dot(np.ones((4, 4)), np.ones((4, 4)))
    try:
        from threadpoolctl import threadpool_info
    except Exception:
        threadpools = []
    else:
        threadpools = threadpool_info()
    return {
        "probe": "thread_budget",
        "runtime": policy.as_runtime_record(),
        "threadpools": threadpools,
    }


def compiledir_concurrency() -> dict[str, object]:
    policy = apply_native_runtime_environment()

    def compile_once() -> float:
        started = time.monotonic()
        pytensor_compile()
        return time.monotonic() - started

    with ThreadPoolExecutor(max_workers=2) as executor:
        elapsed = list(executor.map(lambda _: compile_once(), range(2)))
    return {
        "probe": "compiledir_concurrency",
        "compiledir": policy.compiledir,
        "elapsed_seconds": [round(item, 3) for item in elapsed],
    }


def supervisor_kill() -> dict[str, object]:
    result = run_supervised_sampler(synthetic_blocking_child_command(seconds=60), deadline_seconds=1.0)
    if not result.killed_by_supervisor or not result.orphan_reaped:
        raise RuntimeError(f"supervisor kill proof failed: {result}")
    return {"probe": "supervisor_kill", **result.__dict__}


def runtime_report() -> dict[str, object]:
    compiler = shutil.which("gcc") or shutil.which("cc") or shutil.which("cl")
    payload = import_smoke()
    payload["policy_json"] = json.loads(runtime_policy_json())
    payload["compiler"] = compiler
    return payload


COMMANDS = {
    "import-smoke": import_smoke,
    "pytensor-compile": pytensor_compile,
    "tiny-benchmark": tiny_benchmark,
    "thread-budget": thread_budget,
    "compiledir-concurrency": compiledir_concurrency,
    "supervisor-kill": supervisor_kill,
    "runtime-report": runtime_report,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = COMMANDS[args.command]()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
