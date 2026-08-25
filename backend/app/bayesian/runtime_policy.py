"""B2.4-P5 native runtime policy for the Bayesian worker lane."""

from __future__ import annotations

import json
import os
import platform
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4

from app.inference_policy_registry import RUNTIME_POLICY_VERSION


#: The governed identity of the P5 containment contract.
#:
#: P6 and P7 have carried policy versions since they existed; P5 never did, and
#: the absence was not cosmetic. A confidence is only interpretable against the
#: containment that produced it -- how many chains ran, in how many processes,
#: against which deadlines -- and without an identifier for that contract there
#: is no way to reconstruct, after the fact, which runtime governed a fit.
#:
#: This versions *semantics*, not deployment particulars. Container hostname,
#: PID, image digest and build timestamp are audit metadata; they do not change
#: what a confidence means. The chain topology, the process cage and the
#: deadline hierarchy do.
B24_RUNTIME_POLICY_VERSION = RUNTIME_POLICY_VERSION

THREAD_ENV_VARS = (
    "OMP_NUM_THREADS",
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
)


def _safe_home_path() -> Path | None:
    try:
        return Path.home()
    except RuntimeError:
        return None


@dataclass(frozen=True)
class B24RuntimePolicy:
    worker_runtime_id: str
    worker_concurrency: int
    pymc_cores: int
    pymc_chains: int
    blas_total_threads: int
    sampler_supervisor_deadline_s: int
    celery_soft_time_limit_s: int
    celery_hard_time_limit_s: int
    benchmark_threshold_s: float
    compiledir: str
    execution_id: str
    runtime_policy_version: str = B24_RUNTIME_POLICY_VERSION

    def containment_identity(self) -> dict[str, object]:
        """The resolved containment contract, as this process actually has it.

        Every field here was resolved from the environment this worker is
        running in, not read from a module default. That distinction is the
        whole of Corrective Action X: a policy default describes what was
        intended, and only a resolved value describes what will execute.
        """

        return {
            "runtime_policy_version": self.runtime_policy_version,
            "chains": self.pymc_chains,
            "cores": self.pymc_cores,
            "blas_cores": self.blas_total_threads,
            "worker_concurrency": self.worker_concurrency,
            "sampler_supervisor_deadline_seconds": (self.sampler_supervisor_deadline_s),
            "celery_soft_time_limit_seconds": self.celery_soft_time_limit_s,
            "celery_hard_time_limit_seconds": self.celery_hard_time_limit_s,
        }

    def validate(self) -> None:
        if self.worker_concurrency < 1:
            raise RuntimeError("B24_BAYESIAN_WORKER_CONCURRENCY must be >= 1")
        if self.pymc_cores < 1 or self.pymc_chains < 1:
            raise RuntimeError("B24_PYMC_CORES and B24_PYMC_CHAINS must be >= 1")
        if self.blas_total_threads < 1:
            raise RuntimeError("B24_BLAS_TOTAL_THREADS must be >= 1")
        total_native_threads = (
            self.worker_concurrency * self.pymc_cores * self.blas_total_threads
        )
        cpu_budget = int(
            os.getenv("B24_BAYESIAN_CPU_BUDGET", str(max(1, os.cpu_count() or 1)))
        )
        if total_native_threads > cpu_budget:
            raise RuntimeError(
                "B2.4-P5 native thread budget exceeded "
                f"({total_native_threads} > {cpu_budget})"
            )
        if (
            not self.sampler_supervisor_deadline_s
            < self.celery_soft_time_limit_s
            < self.celery_hard_time_limit_s
        ):
            raise RuntimeError(
                "B2.4-P5 timeout hierarchy must be supervisor_deadline < "
                "celery_soft_time_limit < celery_hard_time_limit"
            )
        compiledir = Path(self.compiledir)
        home_path = _safe_home_path()
        forbidden_compiledirs = {"", "."}
        if home_path is not None:
            forbidden_compiledirs.add(str(home_path))
        if compiledir == home_path or str(compiledir) in forbidden_compiledirs:
            raise RuntimeError(
                "PyTensor compiledir must not be global home/current directory"
            )
        expected_parent_pid = os.getenv("B24_PYTENSOR_PARENT_PID", str(os.getpid()))
        parts = {part for part in compiledir.parts}
        if (
            self.worker_runtime_id not in parts
            or f"parent-{expected_parent_pid}" not in parts
            or self.execution_id not in parts
        ):
            raise RuntimeError(
                "PyTensor compiledir must be scoped by worker runtime, parent PID, and execution identity"
            )

    @property
    def thread_env(self) -> dict[str, str]:
        return {name: str(self.blas_total_threads) for name in THREAD_ENV_VARS}

    def as_runtime_record(self) -> dict[str, object]:
        record = asdict(self)
        record.update(
            {
                "os": platform.platform(),
                "python": platform.python_version(),
                "processor": platform.processor(),
                "thread_env": {name: os.environ.get(name) for name in THREAD_ENV_VARS},
                "PYTENSOR_FLAGS": os.environ.get("PYTENSOR_FLAGS"),
            }
        )
        return record


def _int_env(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


def resolved_runtime_authority_from_env(
    source_env: dict[str, str] | None = None,
) -> dict[str, object]:
    """Resolve decision-significant runtime authority without process state.

    The worker writes this record into the sampler input.  The child resolves
    its own environment independently and must match this record exactly before
    PyMC is imported.  Paths, PIDs, and benchmark metadata are deliberately not
    authority dimensions.
    """

    from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY

    source = source_env if source_env is not None else os.environ

    def _value(name: str, default: int) -> int:
        return int(source.get(name, str(default)))

    return {
        "runtime_policy_version": B24_RUNTIME_POLICY_VERSION,
        "chains": _value("B24_PYMC_CHAINS", DEFAULT_P6_SAMPLING_POLICY.chains),
        "cores": _value("B24_PYMC_CORES", 1),
        "blas_cores": _value("B24_BLAS_TOTAL_THREADS", 1),
        "worker_concurrency": _value("B24_BAYESIAN_WORKER_CONCURRENCY", 1),
        "sampler_supervisor_deadline_seconds": _value(
            "B24_SAMPLER_SUPERVISOR_DEADLINE_S", 240
        ),
        "celery_soft_time_limit_seconds": _value(
            "BAYESIAN_TASK_SOFT_TIME_LIMIT_S", 270
        ),
        "celery_hard_time_limit_seconds": _value("BAYESIAN_TASK_TIME_LIMIT_S", 300),
    }


def build_runtime_policy() -> B24RuntimePolicy:
    # Imported here rather than at module scope: runtime_policy is loaded by
    # the sampler child bootstrap before the application package is fully
    # importable, and only this function needs the sampling policy.
    from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY

    worker_runtime_id = os.getenv(
        "B24_BAYESIAN_WORKER_RUNTIME_ID", "local-bayesian-worker"
    )
    execution_id = os.getenv("B24_PYTENSOR_EXECUTION_ID", f"probe-{uuid4().hex}")
    compiledir_default = str(
        Path(
            os.getenv(
                "B24_PYTENSOR_ROOT",
                str(Path(tempfile.gettempdir()) / "skeldir-b24-pytensor"),
            )
        )
        / worker_runtime_id
        / f"parent-{os.getpid()}"
        / execution_id
    )
    policy = B24RuntimePolicy(
        worker_runtime_id=worker_runtime_id,
        worker_concurrency=_int_env("B24_BAYESIAN_WORKER_CONCURRENCY", 1),
        pymc_cores=_int_env("B24_PYMC_CORES", 1),
        # Read from the sampling policy rather than restated. These two
        # numbers describe the same sampler, and the whole of F-11 was two
        # policies drifting apart while each stayed internally consistent.
        pymc_chains=_int_env("B24_PYMC_CHAINS", DEFAULT_P6_SAMPLING_POLICY.chains),
        blas_total_threads=_int_env("B24_BLAS_TOTAL_THREADS", 1),
        sampler_supervisor_deadline_s=_int_env(
            "B24_SAMPLER_SUPERVISOR_DEADLINE_S", 240
        ),
        celery_soft_time_limit_s=_int_env("BAYESIAN_TASK_SOFT_TIME_LIMIT_S", 270),
        celery_hard_time_limit_s=_int_env("BAYESIAN_TASK_TIME_LIMIT_S", 300),
        benchmark_threshold_s=_float_env("B24_TINY_BENCHMARK_THRESHOLD_S", 60.0),
        compiledir=os.getenv("B24_PYTENSOR_COMPILEDIR", compiledir_default),
        execution_id=execution_id,
    )
    policy.validate()
    return policy


def apply_native_runtime_environment(
    policy: B24RuntimePolicy | None = None,
) -> B24RuntimePolicy:
    """Set native numerical and PyTensor cache controls before scientific imports."""

    policy = policy or build_runtime_policy()
    for name, value in policy.thread_env.items():
        os.environ[name] = value
    compiledir = Path(policy.compiledir)
    compiledir.mkdir(parents=True, exist_ok=True)
    flags = os.environ.get("PYTENSOR_FLAGS", "")
    required_flag = f"base_compiledir={compiledir.as_posix()}"
    if "base_compiledir=" in flags:
        flags = re.sub(r"base_compiledir=[^,]+", required_flag, flags, count=1)
        os.environ["PYTENSOR_FLAGS"] = flags
    else:
        os.environ["PYTENSOR_FLAGS"] = ",".join(
            part for part in (required_flag, flags) if part
        )
    return policy


def pymc_single_process_sample_kwargs(
    policy: B24RuntimePolicy,
) -> dict[str, int]:
    """Return the only allowed PyMC parallelism kwargs for P5 execution.

    The cage is about parallelism, and it is unchanged: one execution core, one
    BLAS thread, one fenced sampler process, no multiprocessing fan-out.

    What changed is that it used to also demand ``chains == 1``, and that was a
    conflation rather than an isolation requirement. PyMC separates the two
    explicitly -- ``chains`` is how many independent Markov chains exist,
    ``cores`` is how many of them run at once -- and with ``cores=1`` it walks
    the chains sequentially inside the same process. Nothing about the physical
    containment depends on the chain count, which is visible in this module's own
    thread-budget arithmetic: ``worker_concurrency x pymc_cores x
    blas_total_threads``. Chains do not appear in it, because they do not
    consume a thread.

    Demanding one chain therefore bought no isolation and cost the diagnostics
    their most important statistic: R-hat compares variance *between* chains, so
    with one chain it does not exist. Every real fit this system produced failed
    as ``nonfinite_diagnostic``, and no amount of data could have changed that.
    """

    if policy.pymc_cores != 1 or policy.blas_total_threads != 1:
        raise RuntimeError(
            "B2.4-P5 sampler runtime is single-process-only: "
            f"cores={policy.pymc_cores}, "
            f"blas_cores={policy.blas_total_threads}"
        )
    if policy.pymc_chains < 1:
        raise RuntimeError(
            f"B2.4-P5 requires at least one chain: chains={policy.pymc_chains}"
        )
    return {
        "chains": policy.pymc_chains,
        "cores": policy.pymc_cores,
        "blas_cores": policy.blas_total_threads,
    }


def runtime_policy_json() -> str:
    policy = apply_native_runtime_environment()
    return json.dumps(policy.as_runtime_record(), sort_keys=True)
