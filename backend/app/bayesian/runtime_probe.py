"""CLI probes for the B2.4-P5 Bayesian worker runtime."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.bayesian.compiledir_reaper import (
    create_compiledir_lease,
    reap_expired_compiledirs,
)
from app.bayesian.runtime_policy import (
    apply_native_runtime_environment,
    pymc_single_process_sample_kwargs,
    runtime_policy_json,
)
from app.bayesian.runtime_identity import (
    assert_runtime_identity,
    collect_runtime_identity,
    expected_runtime_identity_json,
)
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    launch_sampler_child,
    run_supervised_sampler,
    sampler_child_command,
    synthetic_blocking_child_command,
)


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

    if policy.pymc_cores != 1 or policy.pymc_chains != 1:
        raise RuntimeError(
            "B2.4-P5 single-process PyMC policy requires cores=1 and chains=1"
        )
    sample_policy = pymc_single_process_sample_kwargs(policy)
    started = time.monotonic()
    with pm.Model():
        mu = pm.Normal("mu", mu=0.0, sigma=1.0)
        pm.Normal("obs", mu=mu, sigma=1.0, observed=np.asarray([0.0, 0.1, -0.1]))
        idata = pm.sample(
            draws=20,
            tune=20,
            **sample_policy,
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
        "chains": sample_policy["chains"],
        "cores": sample_policy["cores"],
        "blas_cores": sample_policy["blas_cores"],
        "multiprocessing_policy": "single-process",
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
    result = run_supervised_sampler(
        synthetic_blocking_child_command(seconds=60), deadline_seconds=1.0
    )
    if not result.killed_by_supervisor or not result.orphan_reaped:
        raise RuntimeError(f"supervisor kill proof failed: {result}")
    return {"probe": "supervisor_kill", **result.__dict__}


def runtime_report() -> dict[str, object]:
    payload = import_smoke()
    identity = collect_runtime_identity()
    assert_runtime_identity(identity)
    payload["policy_json"] = json.loads(runtime_policy_json())
    payload["expected_identity"] = json.loads(expected_runtime_identity_json())
    payload["actual_identity"] = identity.as_dict()
    payload["compiler"] = (
        shutil.which("gcc") or shutil.which("cc") or shutil.which("cl")
    )
    return payload


def child_env_airgap() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="child-env-airgap")
    output = lease.root / "child-env-airgap.json"
    source_env = {
        **os.environ,
        "DATABASE_URL": "postgresql://leak:leak@127.0.0.1/leak",
        "SKELDIR_FAKE_PARENT_SECRET": "must_not_reach_child",
        "AWS_SECRET_ACCESS_KEY": "must_not_reach_child",
        "STRIPE_API_KEY": "must_not_reach_child",
    }
    env = build_child_env_for_lease(lease, source_env=source_env)
    result = run_supervised_sampler(
        sampler_child_command(mode="env-report", output=output, seconds=1),
        deadline_seconds=10,
        env=env,
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    forbidden = [
        name
        for name in payload["env_keys"]
        if name
        in {
            "DATABASE_URL",
            "SKELDIR_FAKE_PARENT_SECRET",
            "AWS_SECRET_ACCESS_KEY",
            "STRIPE_API_KEY",
        }
    ]
    if forbidden:
        raise RuntimeError(f"child env airgap failed: {forbidden}")
    return {"probe": "child_env_airgap", "result": result.__dict__, "child": payload}


def child_import_airgap() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="child-import-airgap")
    output = lease.root / "child-import-airgap.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="import-negative", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    if payload.get("unexpected_imports"):
        raise RuntimeError(f"child import airgap failed: {payload}")
    if payload.get("pre_attempt_forbidden_modules") or payload.get(
        "post_attempt_forbidden_modules"
    ):
        raise RuntimeError(f"child sys.modules airgap failed: {payload}")
    return {"probe": "child_import_airgap", "result": result.__dict__, "child": payload}


def child_boot_airgap() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="child-boot-airgap")
    output = lease.root / "child-boot-airgap.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="boot-report", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    if not payload.get("boot_airgap_active"):
        raise RuntimeError(f"child boot airgap inactive: {payload}")
    if payload.get("preinstall_forbidden_modules") or payload.get(
        "cached_forbidden_modules"
    ):
        raise RuntimeError(f"child boot sys.modules leak: {payload}")
    if payload.get("multiprocessing_policy") != "single-process":
        raise RuntimeError(f"child multiprocessing policy missing: {payload}")
    return {"probe": "child_boot_airgap", "result": result.__dict__, "child": payload}


def fork_multiprocessing_negative_controls() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="fork-multiprocessing-negative")
    output = lease.root / "fork-multiprocessing-negative.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="fork-negative", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    required = {
        "multiprocessing.get_context('fork')",
        "multiprocessing.get_context()",
        "multiprocessing.Process",
    }
    if os.name != "nt":
        required.add("os.fork")
    blocked = set(payload.get("blocked_controls", {}))
    missing = sorted(required - blocked)
    if missing:
        raise RuntimeError(f"fork/multiprocessing controls did not fail: {missing}")
    return {
        "probe": "fork_multiprocessing_negative_controls",
        "result": result.__dict__,
        "child": payload,
    }


def compiledir_lifecycle() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="compiledir-lifecycle")
    compiledir = str(lease.path)
    result = run_supervised_sampler(
        sampler_child_command(mode="sleep", seconds=60),
        deadline_seconds=1.0,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    if Path(compiledir).exists():
        raise RuntimeError(f"parent-owned compiledir cleanup failed: {compiledir}")
    return {
        "probe": "compiledir_lifecycle",
        "compiledir": compiledir,
        "result": result.__dict__,
    }


def reaper_probe() -> dict[str, object]:
    lease = create_compiledir_lease(execution_id="expired-owned-reaper")
    metadata_path = lease.path / "skeldir_compiledir_owner.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["created_at"] = time.time() - 7200
    metadata["parent_pid"] = 99999999
    metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    foreign = lease.root / "foreign" / "parent-99999999" / "not-owned"
    foreign.mkdir(parents=True, exist_ok=True)
    (foreign / "skeldir_compiledir_owner.json").write_text(
        json.dumps({"owner": "foreign", "created_at": time.time() - 7200}),
        encoding="utf-8",
    )
    report = reap_expired_compiledirs(
        ttl_seconds=60, max_deletions=10, max_scan_entries=50
    )
    if lease.path.exists() or not foreign.exists():
        raise RuntimeError(f"reaper ownership proof failed: {report}")
    return {
        "probe": "reaper_probe",
        "report": report,
        "foreign_preserved": str(foreign),
    }


def _parent_death_parent(output: Path) -> int:
    lease = create_compiledir_lease(execution_id="parent-death")
    marker = lease.root / "parent-death-child.pid"
    proc = launch_sampler_child(
        sampler_child_command(mode="sleep", marker=marker, seconds=60),
        env=build_child_env_for_lease(lease),
    )
    payload = {
        "parent_pid": os.getpid(),
        "child_pid": proc.pid,
        "compiledir": str(lease.path),
        "marker": str(marker),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    while True:
        time.sleep(1)


def _pid_alive(pid: int) -> bool:
    try:
        result = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)],
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and "Z" in result.stdout:
            return False
    except Exception:
        pass
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parent_death() -> dict[str, object]:
    if os.name == "nt":
        raise RuntimeError("parent death proof requires Linux PR_SET_PDEATHSIG")
    root = Path(os.getenv("B24_PYTENSOR_ROOT", "/tmp/skeldir-b24-pytensor"))
    output = root / "parent-death.json"
    parent = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.bayesian.runtime_probe",
            "parent-death-parent",
            "--output",
            str(output),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    deadline = time.monotonic() + 10
    while not output.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not output.exists():
        parent.kill()
        raise RuntimeError("parent-death proof failed to launch child")
    payload = json.loads(output.read_text(encoding="utf-8"))
    child_pid = int(payload["child_pid"])
    os.kill(parent.pid, signal.SIGKILL)
    parent.wait(timeout=5)
    deadline = time.monotonic() + 10
    while _pid_alive(child_pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    child_dead = not _pid_alive(child_pid)
    if not child_dead:
        raise RuntimeError(f"parent-death child survived: {payload}")
    report = reap_expired_compiledirs(
        ttl_seconds=0, max_deletions=10, max_scan_entries=50
    )
    return {
        "probe": "parent_death",
        "parent_pid": parent.pid,
        "child_pid": child_pid,
        "child_dead": child_dead,
        "reaper": report,
    }


def behavioral_negative_controls() -> dict[str, object]:
    controls: dict[str, str] = {}
    try:
        os.environ["B24_PYMC_CORES"] = "2"
        tiny_benchmark()
    except RuntimeError as exc:
        controls["pymc_parallelism"] = str(exc)
    else:
        raise RuntimeError("PyMC parallelism negative control did not fail")
    finally:
        os.environ["B24_PYMC_CORES"] = "1"
    static_dir = (
        Path(os.getenv("B24_PYTENSOR_ROOT", "/tmp/skeldir-b24-pytensor")) / "worker"
    )
    try:
        os.environ["B24_PYTENSOR_COMPILEDIR"] = str(static_dir)
        apply_native_runtime_environment()
    except RuntimeError as exc:
        controls["static_compiledir"] = str(exc)
    else:
        raise RuntimeError("static compiledir negative control did not fail")
    finally:
        os.environ.pop("B24_PYTENSOR_COMPILEDIR", None)
    return {"probe": "behavioral_negative_controls", "controls": controls}


COMMANDS = {
    "import-smoke": import_smoke,
    "pytensor-compile": pytensor_compile,
    "tiny-benchmark": tiny_benchmark,
    "thread-budget": thread_budget,
    "compiledir-concurrency": compiledir_concurrency,
    "compiledir-lifecycle": compiledir_lifecycle,
    "reaper-probe": reaper_probe,
    "supervisor-kill": supervisor_kill,
    "child-env-airgap": child_env_airgap,
    "child-boot-airgap": child_boot_airgap,
    "child-import-airgap": child_import_airgap,
    "fork-multiprocessing-negative-controls": fork_multiprocessing_negative_controls,
    "parent-death": parent_death,
    "parent-death-parent": _parent_death_parent,
    "behavioral-negative-controls": behavioral_negative_controls,
    "runtime-report": runtime_report,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "parent-death-parent":
        if args.output is None:
            parser.error("parent-death-parent requires --output")
        return _parent_death_parent(args.output)
    payload = COMMANDS[args.command]()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
    _print_json(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
