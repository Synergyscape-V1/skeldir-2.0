"""B2.4-P6 bounded sampler policy."""

from __future__ import annotations

from dataclasses import asdict, dataclass


SAMPLING_POLICY_VERSION = "b24-p6-sampling-policy-v1"
MAX_P6_SAMPLES = 16_000
MAX_P6_CORES = 4
MAX_P6_CHAINS = 4


@dataclass(frozen=True)
class SamplingPolicy:
    draws: int = 64
    tune: int = 40
    chains: int = 1
    cores: int = 1
    blas_cores: int = 1
    target_accept: float = 0.9
    init: str = "jitter+adapt_diag"
    policy_version: str = SAMPLING_POLICY_VERSION

    @property
    def sample_count(self) -> int:
        return self.draws + self.tune

    def validate(self) -> None:
        if self.draws < 1 or self.tune < 0:
            raise ValueError("draws and tune must be positive/non-negative")
        if self.sample_count > MAX_P6_SAMPLES:
            raise ValueError("P6 sample cap exceeded")
        if self.cores < 1 or self.cores > MAX_P6_CORES:
            raise ValueError("P6 core cap exceeded")
        if self.chains < 1 or self.chains > MAX_P6_CHAINS:
            raise ValueError("P6 chain cap exceeded")
        if self.blas_cores != 1 or self.cores != 1 or self.chains != 1:
            raise ValueError("P6 preserves P5 single-process runtime cage")
        if not (0.5 <= self.target_accept < 1.0):
            raise ValueError("target_accept out of bounded policy range")
        if not self.init.strip():
            raise ValueError("sampler init policy must be explicit")

    def as_dict(self) -> dict[str, object]:
        self.validate()
        return asdict(self)


DEFAULT_P6_SAMPLING_POLICY = SamplingPolicy()
