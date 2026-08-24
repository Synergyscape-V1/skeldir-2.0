"""B2.4-P6 bounded sampler policy.

Version 2 exists because version 1 could not produce a fit its own diagnostics
would accept, and neither policy was individually wrong about anything.

P6-v1 drew 64 samples from **one** chain. P7 requires a finite R-hat at or below
1.01 and an effective sample size of at least 400. R-hat compares variance
*between* chains, so with one chain it is undefined, and every real fit failed as
``nonfinite_diagnostic`` before the sample size was even considered. Sixty-four
draws against a threshold of four hundred could not have passed either.

The resolution is not to lower the diagnostic standard. It is that P5's
isolation cage was written as though *one process* meant *one chain*, and those
are different things. PyMC distinguishes them explicitly: ``chains`` is how many
independent Markov chains exist, ``cores`` is how many run in parallel. With
``cores=1`` PyMC samples the chains **sequentially**, in one process, with one
BLAS thread and no multiprocessing fan-out. The cage is about parallelism; the
chain count is about statistics; and only the first was ever the constraint.

So this policy runs four chains sequentially and spends more bounded compute
before spending trust.

Sample-budget vocabulary is explicit here, because it stopped being obvious the
moment ``chains`` exceeded one. Version 1 had a single ``sample_count`` meaning
``draws + tune`` -- per chain, with no chain factor -- which was harmless while
there was exactly one chain and silently wrong afterwards:

    draws_per_chain          retained posterior draws, per chain
    tune_per_chain           tuning iterations, per chain, discarded
    posterior_draws_total    chains x draws_per_chain      -> n_samples_actual
    total_chain_iterations   chains x (draws + tune)       -> max_samples budget

``max_samples`` on a fit governs ``total_chain_iterations``: the whole sampling
workload the fit is authorised to perform, tuning included, because tuning costs
the same wall clock as drawing. ``n_samples_actual`` reports
``posterior_draws_total``: what was kept. Neither is ever called
``sample_count``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


SAMPLING_POLICY_VERSION = "b24-p6-sampling-policy-v2"

#: Retained for provenance. A signed confidence produced under the old policy
#: must stay interpretable after this one supersedes it.
SUPERSEDED_SAMPLING_POLICY_VERSIONS = ("b24-p6-sampling-policy-v1",)

MAX_P6_SAMPLES = 16_000
MAX_P6_CORES = 4
MAX_P6_CHAINS = 4


@dataclass(frozen=True)
class SamplingPolicy:
    """How much sampling work one fit performs, and in what topology."""

    draws_per_chain: int = 1000
    tune_per_chain: int = 1000
    chains: int = 4
    cores: int = 1
    blas_cores: int = 1
    target_accept: float = 0.90
    init: str = "jitter+adapt_diag"
    policy_version: str = SAMPLING_POLICY_VERSION

    @property
    def posterior_draws_total(self) -> int:
        """Retained draws across all chains. This is ``n_samples_actual``."""

        return self.draws_per_chain * self.chains

    @property
    def total_chain_iterations(self) -> int:
        """Every iteration the sampler performs, tuning included.

        This is what a fit's ``max_samples`` budget authorises, because tuning
        is not free: it costs the same wall clock as drawing and it is the
        larger half of the work for a well-tuned model.
        """

        return (self.draws_per_chain + self.tune_per_chain) * self.chains

    def validate(self) -> None:
        if self.draws_per_chain < 1 or self.tune_per_chain < 0:
            raise ValueError("draws must be positive and tuning non-negative")
        if self.posterior_draws_total > MAX_P6_SAMPLES:
            raise ValueError("P6 posterior draw cap exceeded")
        if self.cores < 1 or self.cores > MAX_P6_CORES:
            raise ValueError("P6 core cap exceeded")
        if self.chains < 1 or self.chains > MAX_P6_CHAINS:
            raise ValueError("P6 chain cap exceeded")
        # The P5 cage, stated as what it actually constrains. One execution core
        # and one BLAS thread keep the sampler inside a single fenced process
        # with no multiprocessing fan-out. The number of chains does not enter
        # that product -- with cores=1 PyMC walks them one after another -- and
        # requiring chains == 1 here was the conflation that made R-hat
        # impossible to compute.
        if self.blas_cores != 1 or self.cores != 1:
            raise ValueError(
                "P6 preserves the P5 single-process runtime cage: "
                "cores and blas_cores must both be 1"
            )
        if not (0.5 <= self.target_accept < 1.0):
            raise ValueError("target_accept out of bounded policy range")
        if not self.init.strip():
            raise ValueError("sampler init policy must be explicit")

    def as_dict(self) -> dict[str, object]:
        self.validate()
        payload = asdict(self)
        payload["posterior_draws_total"] = self.posterior_draws_total
        payload["total_chain_iterations"] = self.total_chain_iterations
        return payload


DEFAULT_P6_SAMPLING_POLICY = SamplingPolicy()
