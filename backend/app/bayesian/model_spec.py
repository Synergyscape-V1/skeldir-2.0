"""Versioned real-model contract for B2.4-P6."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.bayesian.input_contract import SOURCE_CONTRACT_VERSION
from app.bayesian.sampling_policy import SAMPLING_POLICY_VERSION


B24_P6_MODEL_TYPE = "bayesian_attribution_confidence"
B24_P6_MODEL_VERSION = "b24-p6-real-fit-v1"


@dataclass(frozen=True)
class B24P6ModelSpec:
    model_type: str = B24_P6_MODEL_TYPE
    model_version: str = B24_P6_MODEL_VERSION
    source_contract_version: str = SOURCE_CONTRACT_VERSION
    sampling_policy_version: str = SAMPLING_POLICY_VERSION
    likelihood: str = "normal_observation_smoke_model"
    observed_target: str = "standardized_aggregate_revenue_signal"
    priors: tuple[str, ...] = (
        "mu ~ Normal(0, 1)",
        "sigma ~ HalfNormal(1)",
    )
    dimensions: tuple[str, ...] = ("observation",)
    feature_mapping: tuple[str, ...] = (
        "source_row_count",
        "conversion_count",
        "touchpoint_count",
    )

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


B24_P6_MODEL_SPEC = B24P6ModelSpec()
