"""B2.5-P13 C10-O: assert the shipped Bayesian artifact's real topology.

This runs *inside* the production image, through the production code path, and
it exists because of a specific failure. F-11 was declared resolved on evidence
from a CI job that pip-installs onto a GitHub runner. That job never built
``backend/Dockerfile.bayesian``, which set ``B24_PYMC_CHAINS=1`` and therefore
resolved one chain, undefined R-hat, and a fit that could never pass its own
diagnostics. Both the policy fix and its proof were correct; neither touched the
artifact that ships, and nothing in CI could tell the difference.

So the assertion here is deliberately not "the policy says four". It is: the
environment this container resolved, the kwargs the production function built
from it, and the dimensions of the posterior PyMC actually returned, are all the
same four chains -- measured in that order, on this artifact, at this moment.

Exit code is the gate. Any divergence exits non-zero with the observation that
produced it.
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")


def _fail(message: str, observations: dict[str, object]) -> None:
    print(f"B24_ARTIFACT_TOPOLOGY_FAIL: {message}", file=sys.stderr)
    print(
        "OBSERVATIONS " + json.dumps(observations, sort_keys=True, default=str),
        file=sys.stderr,
    )
    sys.exit(1)


def main() -> int:
    observations: dict[str, object] = {
        "env_B24_PYMC_CHAINS": os.environ.get("B24_PYMC_CHAINS", "<unset>"),
        "env_B24_PYMC_CORES": os.environ.get("B24_PYMC_CORES", "<unset>"),
        "env_B24_BLAS_TOTAL_THREADS": os.environ.get(
            "B24_BLAS_TOTAL_THREADS", "<unset>"
        ),
        "env_B24_SAMPLER_SUPERVISOR_DEADLINE_S": os.environ.get(
            "B24_SAMPLER_SUPERVISOR_DEADLINE_S", "<unset>"
        ),
    }

    from app.bayesian.inference_profile import (
        B24_INFERENCE_PROFILE,
        RuntimeProfileMismatchError,
        assert_observed_topology_matches_profile,
        assert_runtime_matches_profile,
    )
    from app.bayesian.runtime_policy import (
        build_runtime_policy,
        pymc_single_process_sample_kwargs,
    )

    profile = B24_INFERENCE_PROFILE
    observations["profile_version"] = profile.profile_version
    observations["policy_bundle_hash"] = profile.policy_bundle_hash()
    observations["authorized_chains"] = profile.chains
    observations["authorized_cores"] = profile.cores
    observations["authorized_blas_cores"] = profile.blas_cores

    runtime = build_runtime_policy()
    observations["resolved_chains"] = runtime.pymc_chains
    observations["resolved_cores"] = runtime.pymc_cores
    observations["resolved_blas_cores"] = runtime.blas_total_threads
    observations["resolved_supervisor_deadline_s"] = (
        runtime.sampler_supervisor_deadline_s
    )
    observations["resolved_celery_soft_s"] = runtime.celery_soft_time_limit_s
    observations["resolved_celery_hard_s"] = runtime.celery_hard_time_limit_s

    # 1. The binding the worker itself performs before spending compute.
    try:
        correspondence = assert_runtime_matches_profile(runtime)
    except RuntimeProfileMismatchError as exc:
        _fail(f"runtime/profile binding refused this artifact: {exc}", observations)
        return 1
    observations["runtime_correspondence"] = correspondence

    # 2. The kwargs production actually hands PyMC.
    kwargs = pymc_single_process_sample_kwargs(runtime)
    observations["production_sample_kwargs"] = kwargs
    if kwargs["chains"] != profile.chains:
        _fail(
            f"production sample kwargs request {kwargs['chains']} chains, "
            f"profile authorises {profile.chains}",
            observations,
        )

    # 3. What PyMC physically produces in this container.
    import numpy as np
    import pymc as pm

    signal = np.array([0.0, 0.25, -0.25, 0.1, -0.1, 0.3, -0.3, 0.05], dtype=float)
    started = time.monotonic()
    with pm.Model():
        mu = pm.Normal("mu", mu=0.0, sigma=1.0)
        pm.Normal("observed_signal", mu=mu, sigma=1.0, observed=signal)
        idata = pm.sample(
            draws=profile.draws_per_chain,
            tune=profile.tune_per_chain,
            **kwargs,
            random_seed=20260824,
            progressbar=False,
            compute_convergence_checks=False,
            discard_tuned_samples=True,
            return_inferencedata=True,
        )

    observations["runtime_seconds"] = round(time.monotonic() - started, 6)
    observed_chains = int(idata.posterior.sizes["chain"])
    observed_draws = int(idata.posterior.sizes["draw"])
    observations["observed_posterior_chains"] = observed_chains
    observations["observed_posterior_draws_per_chain"] = observed_draws
    observations["observed_posterior_draws_total"] = observed_chains * observed_draws

    if observed_chains != profile.chains:
        _fail(
            f"posterior has {observed_chains} chains; profile authorises "
            f"{profile.chains}",
            observations,
        )

    # 4. Full governed statistical adjudication, inside this artifact.
    import arviz as az

    r_hat = float(az.rhat(idata).to_array().max())
    ess_min = float(az.ess(idata).to_array().min())
    divergence_count = int(idata.sample_stats["diverging"].values.sum())
    observations["r_hat_max"] = r_hat
    observations["ess_min"] = ess_min
    observations["divergence_count"] = divergence_count
    observations["r_hat_is_finite"] = bool(np.isfinite(r_hat))
    if not np.isfinite(r_hat):
        _fail(
            "R-hat is not finite in this artifact; the posterior cannot be "
            "adjudicated and no fit produced here could ever be accepted",
            observations,
        )
    if r_hat > profile.r_hat_max_threshold:
        _fail(f"R-hat {r_hat} exceeds {profile.r_hat_max_threshold}", observations)
    if ess_min < profile.ess_min_threshold:
        _fail(f"ESS {ess_min} is below {profile.ess_min_threshold}", observations)
    if divergence_count != profile.divergence_count_threshold:
        _fail(
            f"divergences {divergence_count} do not equal "
            f"{profile.divergence_count_threshold}",
            observations,
        )

    chain_values = np.asarray(idata.posterior["mu"].values, dtype=float)
    identical_pairs = [
        [left, right]
        for left in range(observed_chains)
        for right in range(left + 1, observed_chains)
        if np.array_equal(chain_values[left], chain_values[right])
    ]
    observations["identical_chain_pairs"] = identical_pairs
    if identical_pairs:
        _fail("posterior chains are not independent trajectories", observations)

    # 5. The observational check the sampler child performs, exercised here at
    #    the artifact's actual draw count so the mechanism itself is proven live.
    try:
        assert_observed_topology_matches_profile(
            observed_chains=observed_chains,
            observed_draws_per_chain=observed_draws,
        )
    except RuntimeProfileMismatchError as exc:
        _fail(f"observed-topology binding refused: {exc}", observations)

    # 6. Single-process containment: chains rose, parallelism did not.
    if runtime.pymc_cores != 1 or runtime.blas_total_threads != 1:
        _fail(
            "four chains were obtained by raising parallelism rather than by "
            "sampling sequentially; the P5 cage is broken",
            observations,
        )

    print("B24_ARTIFACT_TOPOLOGY_PASS")
    print("OBSERVATIONS " + json.dumps(observations, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
