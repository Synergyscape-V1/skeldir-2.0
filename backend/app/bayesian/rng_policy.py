"""Deterministic RNG policy for B2.4-P6 sampler auditability."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from app.bayesian.sampling_policy import SamplingPolicy


RNG_POLICY_VERSION = "b24-p6-rng-policy-v1"


@dataclass(frozen=True)
class RngSeedMaterial:
    tenant_id: UUID
    fit_id: UUID
    source_snapshot_hash: str
    model_type: str
    model_version: str
    source_window_start: str
    source_window_end: str
    sampling_policy_version: str
    seed_derivation_version: str = RNG_POLICY_VERSION

    def canonical_material(self) -> str:
        parts = [
            self.seed_derivation_version,
            str(self.tenant_id),
            str(self.fit_id),
            self.source_snapshot_hash,
            self.model_type,
            self.model_version,
            self.source_window_start,
            self.source_window_end,
            self.sampling_policy_version,
        ]
        return "|".join(parts)


def derive_rng_seed(material: RngSeedMaterial) -> int:
    digest = hashlib.sha256(material.canonical_material().encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def chain_seeds(seed: int, policy: SamplingPolicy) -> list[int]:
    return [((int(seed) + idx * 104729) & 0x7FFFFFFF) for idx in range(policy.chains)]
