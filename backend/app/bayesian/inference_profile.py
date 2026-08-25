"""B2.4 inference compatibility profile.

F-11 was not a bug in any policy. The P5 runtime cage, the P6 sampling policy
and the P7 diagnostic policy were each internally consistent, separately
versioned, and jointly impossible: P5 required one chain, P7 required a finite
R-hat, and R-hat does not exist for one chain. Nothing in the system was
responsible for noticing that, so nothing did -- for as long as the only proof
that a fit could execute wrote its own fit row and asserted nothing about
diagnostics.

Merging the three policies would be the wrong repair. They answer different
questions, they are owned by different concerns, and they should keep evolving
independently. What was missing is a fourth authority that says which exact
versions are authorised to operate *together*, and refuses combinations that
cannot produce a result:

    b24-p5-runtime-policy       how the sampler is contained
    b24-p6-sampling-policy      how much sampling work is performed
    b24-p7-diagnostic-policy    what makes a posterior acceptable
            |
            v
    b24-inference-profile       which exact versions may run as one system

The invariants below are the ones whose violation makes a fit structurally
impossible rather than merely unlikely. They are deliberately not a quality
judgement -- whether a particular posterior converges is an empirical question
the diagnostics answer at runtime. These reject configurations where *no* data
could succeed.

The distinction matters most for effective sample size. ESS is not synonymous
with the draw count: it can edge slightly above it when NUTS samples
antithetically, and is usually below. So this profile does not assert an
arithmetic bound. It asserts that the retained draws leave a *plausible*
efficiency margin, and treats a configuration demanding better than one
effective sample per retained draw as structurally implausible.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.bayesian.diagnostics import DEFAULT_P7_DIAGNOSTIC_POLICY
from app.bayesian.runtime_policy import B24_RUNTIME_POLICY_VERSION
from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY
from app.inference_policy_registry import (
    CURRENT_POLICY_BUNDLE_HASH,
    INFERENCE_PROFILE_VERSION,
    current_manifest,
)


B24_INFERENCE_PROFILE_VERSION = INFERENCE_PROFILE_VERSION

#: The sampler is given the runtime envelope P5 already authorises, rather than
#: a smaller number that drifted independently. Before this, a planner-created
#: fit carried max_runtime_seconds = 60 while P5 permitted a 240-second sampler
#: deadline inside a 270/300 Celery hierarchy -- four numbers describing one
#: containment boundary, only three of which agreed.
FIT_EXECUTION_BUDGET_SECONDS = 240
SAMPLER_SUPERVISOR_DEADLINE_SECONDS = 240
CELERY_SOFT_TIME_LIMIT_SECONDS = 270
CELERY_HARD_TIME_LIMIT_SECONDS = 300

#: A fit's lease must outlive the worst-case execution it authorises, or a still
#: running fit can be reclaimed and executed twice.
DISPATCH_LEASE_RECOVERY_MARGIN_SECONDS = 30


class InferenceProfileError(RuntimeError):
    """Raised when the authorised policies cannot operate as one system."""


@dataclass(frozen=True)
class InferenceCompatibilityProfile:
    """One authorised tuple of independently versioned inference policies."""

    profile_version: str
    runtime_policy_version: str
    sampling_policy_version: str
    diagnostic_policy_version: str
    chains: int
    draws_per_chain: int
    tune_per_chain: int
    posterior_draws_total: int
    total_chain_iterations: int
    cores: int
    blas_cores: int
    target_accept: float
    min_chains: int
    r_hat_max_threshold: float
    ess_min_threshold: float
    divergence_count_threshold: int
    fit_execution_budget_seconds: int
    sampler_supervisor_deadline_seconds: int
    celery_soft_time_limit_seconds: int
    celery_hard_time_limit_seconds: int

    def as_provenance(self) -> dict[str, object]:
        """The versions a signed confidence must be interpretable against.

        A confidence produced today has to remain readable after these policies
        evolve, which means the artefact records *which* versions produced it
        rather than the values they happened to hold.
        """

        return {
            "inference_profile_version": self.profile_version,
            "runtime_policy_version": self.runtime_policy_version,
            "sampling_policy_version": self.sampling_policy_version,
            "diagnostic_policy_version": self.diagnostic_policy_version,
        }

    def policy_bundle_hash(self) -> str:
        """Content identity of the complete governed semantic manifest."""

        return CURRENT_POLICY_BUNDLE_HASH

    def validate(self) -> None:
        """Reject combinations in which no posterior could ever be accepted."""

        # 1. R-hat requires more than one chain. This is the F-11 defect itself.
        if self.r_hat_max_threshold > 0 and self.chains < 2:
            raise InferenceProfileError(
                "diagnostics require a finite R-hat but the sampler runs "
                f"{self.chains} chain(s); R-hat compares variance between "
                "chains and does not exist below two"
            )

        # 2. The two policies must agree on how many chains there are, not
        #    merely both permit the number independently.
        if self.chains != self.min_chains:
            raise InferenceProfileError(
                f"sampler runs {self.chains} chains while diagnostics require "
                f"{self.min_chains}; these describe one sampler and must match"
            )

        # 3. Structural plausibility, not an arithmetic bound. Demanding more
        #    effective samples than there are retained draws asks for better
        #    than one effective sample per draw, which no sampler delivers
        #    reliably. Whether a given posterior reaches the threshold stays an
        #    empirical question for the diagnostics.
        if self.ess_min_threshold > self.posterior_draws_total:
            raise InferenceProfileError(
                f"diagnostics require an effective sample size of "
                f"{self.ess_min_threshold} from {self.posterior_draws_total} "
                "retained draws; that demands better than one effective sample "
                "per draw and no configuration of data can satisfy it"
            )

        # 4. The P5 cage: one execution core, one BLAS thread. Chains are not
        #    part of this product -- with cores=1 they run sequentially.
        if self.cores != 1 or self.blas_cores != 1:
            raise InferenceProfileError(
                "the P5 single-process cage requires cores=1 and blas_cores=1; "
                f"got cores={self.cores}, blas_cores={self.blas_cores}"
            )

        # 5. The runtime envelope, as one ordered hierarchy rather than four
        #    numbers maintained separately.
        if not (
            self.fit_execution_budget_seconds
            <= self.sampler_supervisor_deadline_seconds
            < self.celery_soft_time_limit_seconds
            < self.celery_hard_time_limit_seconds
        ):
            raise InferenceProfileError(
                "runtime envelope must satisfy fit budget <= supervisor "
                "deadline < celery soft limit < celery hard limit; got "
                f"{self.fit_execution_budget_seconds} <= "
                f"{self.sampler_supervisor_deadline_seconds} < "
                f"{self.celery_soft_time_limit_seconds} < "
                f"{self.celery_hard_time_limit_seconds}"
            )

        # 6. Divergences are a hard refusal, not a tolerance to be tuned upward
        #    when acceptance rates disappoint.
        if self.divergence_count_threshold != 0:
            raise InferenceProfileError(
                "divergences must remain a hard refusal; got "
                f"{self.divergence_count_threshold}"
            )


def build_inference_profile() -> InferenceCompatibilityProfile:
    """Assemble the profile from the policies themselves, never from literals."""

    sampling = DEFAULT_P6_SAMPLING_POLICY
    thresholds = DEFAULT_P7_DIAGNOSTIC_POLICY.thresholds()
    return InferenceCompatibilityProfile(
        profile_version=B24_INFERENCE_PROFILE_VERSION,
        runtime_policy_version=B24_RUNTIME_POLICY_VERSION,
        sampling_policy_version=sampling.policy_version,
        diagnostic_policy_version=(
            DEFAULT_P7_DIAGNOSTIC_POLICY.diagnostic_policy_version
        ),
        chains=sampling.chains,
        draws_per_chain=sampling.draws_per_chain,
        tune_per_chain=sampling.tune_per_chain,
        posterior_draws_total=sampling.posterior_draws_total,
        total_chain_iterations=sampling.total_chain_iterations,
        cores=sampling.cores,
        blas_cores=sampling.blas_cores,
        target_accept=sampling.target_accept,
        min_chains=thresholds.min_chains,
        r_hat_max_threshold=thresholds.r_hat_max_threshold,
        ess_min_threshold=thresholds.ess_min_threshold,
        divergence_count_threshold=thresholds.divergence_count_threshold,
        fit_execution_budget_seconds=FIT_EXECUTION_BUDGET_SECONDS,
        sampler_supervisor_deadline_seconds=SAMPLER_SUPERVISOR_DEADLINE_SECONDS,
        celery_soft_time_limit_seconds=CELERY_SOFT_TIME_LIMIT_SECONDS,
        celery_hard_time_limit_seconds=CELERY_HARD_TIME_LIMIT_SECONDS,
    )


#: Every dimension the profile authorises that the *environment* can also
#: resolve independently, paired as (profile attribute, runtime attribute).
#:
#: This list is the answer to "why did F-11 survive its own remediation". The
#: profile validated that P6 and P7 agree, which they did. Nothing validated
#: that the process about to spend compute had resolved those same values, and
#: the shipped image had resolved a different one. Any field a deployment can
#: set belongs here; a special case for B24_PYMC_CHAINS alone would leave the
#: identical hole open for the deadlines, which are equally environment-driven
#: and today merely happen to agree.
RUNTIME_BOUND_DIMENSIONS: tuple[tuple[str, str], ...] = (
    ("chains", "pymc_chains"),
    ("cores", "pymc_cores"),
    ("blas_cores", "blas_total_threads"),
    ("sampler_supervisor_deadline_seconds", "sampler_supervisor_deadline_s"),
    ("celery_soft_time_limit_seconds", "celery_soft_time_limit_s"),
    ("celery_hard_time_limit_seconds", "celery_hard_time_limit_s"),
)


class RuntimeProfileMismatchError(InferenceProfileError):
    """The resolved runtime is not the runtime the profile authorised."""


def assert_runtime_matches_profile(
    runtime_policy: object,
    profile: InferenceCompatibilityProfile | None = None,
) -> dict[str, object]:
    """Refuse to sample unless the executing runtime *is* the authorised one.

    Called immediately before consequence-bearing computation, on the policy
    object the worker actually resolved from its own environment -- never on a
    module default. The profile is an authority only if something checks it
    against reality at the moment reality is about to be spent.

    Returns the AUTHORIZED-equals-RESOLVED record so callers can persist the
    correspondence rather than assert it and discard the evidence.
    """

    active = profile if profile is not None else B24_INFERENCE_PROFILE

    divergences: list[str] = []
    correspondence: dict[str, object] = {}
    for profile_field, runtime_field in RUNTIME_BOUND_DIMENSIONS:
        authorized = getattr(active, profile_field)
        resolved = getattr(runtime_policy, runtime_field)
        correspondence[profile_field] = {
            "authorized": authorized,
            "resolved": resolved,
        }
        if authorized != resolved:
            divergences.append(
                f"{profile_field}: authorized={authorized} resolved={resolved}"
            )

    if divergences:
        raise RuntimeProfileMismatchError(
            "resolved runtime diverges from the authorised inference profile "
            f"{active.profile_version}; refusing to sample. " + "; ".join(divergences)
        )

    correspondence["policy_bundle_hash"] = active.policy_bundle_hash()
    correspondence["runtime_policy_version"] = getattr(
        runtime_policy, "runtime_policy_version", None
    )
    return correspondence


def assert_observed_topology_matches_profile(
    *,
    observed_chains: int,
    observed_draws_per_chain: int,
    profile: InferenceCompatibilityProfile | None = None,
) -> dict[str, int]:
    """Check the posterior that exists against the one that was authorised.

    The runtime check above happens before sampling and can only see intent
    resolved from configuration. This one happens after, and reads the physical
    dimensions of the object PyMC returned. Both are necessary: a sampler that
    is interrupted, or that silently produces fewer chains than requested, is
    not caught by any amount of pre-flight agreement.
    """

    active = profile if profile is not None else B24_INFERENCE_PROFILE
    observed_total = observed_chains * observed_draws_per_chain

    if (
        observed_chains != active.chains
        or observed_draws_per_chain != active.draws_per_chain
    ):
        raise RuntimeProfileMismatchError(
            "observed posterior does not match the authorised topology: "
            f"authorized chains={active.chains} "
            f"draws_per_chain={active.draws_per_chain}; "
            f"observed chains={observed_chains} "
            f"draws_per_chain={observed_draws_per_chain}"
        )

    return {
        "observed_chains": observed_chains,
        "observed_draws_per_chain": observed_draws_per_chain,
        "observed_posterior_draws_total": observed_total,
    }


B24_INFERENCE_PROFILE = build_inference_profile()

# Fail at import rather than at the end of a four-minute sampling run. A
# configuration in which no posterior could be accepted is not a runtime
# condition to be reported; it is a deployment that should not start.
B24_INFERENCE_PROFILE.validate()


def assert_live_policy_registry_correspondence() -> None:
    """Prove producer objects still mean exactly what their labels declare."""

    manifest = current_manifest()["components"]
    sampling = DEFAULT_P6_SAMPLING_POLICY.as_dict()
    sampling_version = sampling.pop("policy_version")
    diagnostics = DEFAULT_P7_DIAGNOSTIC_POLICY.as_dict()
    diagnostic_version = diagnostics.pop("diagnostic_policy_version")
    confidence = manifest["confidence_policy"]
    from app.confidence_projection.policy import (
        CONFIDENCE_POLICY_VERSION,
        CONFIDENCE_SEMANTICS_VERSION,
        confidence_policy_semantics,
    )

    expected_profile = {
        "fit_execution_budget_seconds": B24_INFERENCE_PROFILE.fit_execution_budget_seconds,
        "sampler_supervisor_deadline_seconds": (
            B24_INFERENCE_PROFILE.sampler_supervisor_deadline_seconds
        ),
        "celery_soft_time_limit_seconds": (
            B24_INFERENCE_PROFILE.celery_soft_time_limit_seconds
        ),
        "celery_hard_time_limit_seconds": (
            B24_INFERENCE_PROFILE.celery_hard_time_limit_seconds
        ),
        "dispatch_lease_recovery_margin_seconds": (
            DISPATCH_LEASE_RECOVERY_MARGIN_SECONDS
        ),
        "runtime_correspondence_required": True,
        "observed_posterior_correspondence_required": True,
    }
    expected_runtime = {
        "worker_concurrency": 1,
        "pymc_cores": B24_INFERENCE_PROFILE.cores,
        "pymc_chains": B24_INFERENCE_PROFILE.chains,
        "blas_total_threads": B24_INFERENCE_PROFILE.blas_cores,
        "sampler_supervisor_deadline_seconds": (
            B24_INFERENCE_PROFILE.sampler_supervisor_deadline_seconds
        ),
        "celery_soft_time_limit_seconds": (
            B24_INFERENCE_PROFILE.celery_soft_time_limit_seconds
        ),
        "celery_hard_time_limit_seconds": (
            B24_INFERENCE_PROFILE.celery_hard_time_limit_seconds
        ),
        "worker_sampler_explicit_runtime_record": True,
    }
    checks = (
        (
            manifest["inference_profile"]["version"],
            B24_INFERENCE_PROFILE.profile_version,
        ),
        (manifest["inference_profile"]["semantics"], expected_profile),
        (
            manifest["runtime_policy"]["version"],
            B24_INFERENCE_PROFILE.runtime_policy_version,
        ),
        (manifest["runtime_policy"]["semantics"], expected_runtime),
        (manifest["sampling_policy"]["version"], sampling_version),
        (manifest["sampling_policy"]["semantics"], sampling),
        (manifest["diagnostic_policy"]["version"], diagnostic_version),
        (manifest["diagnostic_policy"]["semantics"], diagnostics),
        (confidence["version"], CONFIDENCE_POLICY_VERSION),
        (confidence["semantics_version"], CONFIDENCE_SEMANTICS_VERSION),
        (confidence["semantics"], confidence_policy_semantics()),
    )
    if any(actual != expected for actual, expected in checks):
        raise InferenceProfileError("live_policy_semantics_registry_mismatch")


assert_live_policy_registry_correspondence()
