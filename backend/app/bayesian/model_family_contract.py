"""B2.4 model-family feature-dimension contract.

This module is the machine-owned boundary between P4 profiling and future fit
materialization. A model family may only use dimensions that P4 declares active
and profiles from the source contract.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping


CHANNEL_DIMENSION = "channel"
CURRENCY_DIMENSION = "currency"
PROVIDER_DIMENSION = "provider"
CAMPAIGN_OR_FEATURE_DIMENSION = "campaign_or_feature"

B24_ACTIVE_FEATURE_DIMENSIONS = frozenset(
    {
        CHANNEL_DIMENSION,
        CURRENCY_DIMENSION,
        PROVIDER_DIMENSION,
        CAMPAIGN_OR_FEATURE_DIMENSION,
    }
)

B24_MODEL_FAMILY_DIMENSION_CONTRACT: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "mmm": B24_ACTIVE_FEATURE_DIMENSIONS,
        "bayesian_attribution_confidence": B24_ACTIVE_FEATURE_DIMENSIONS,
    }
)


class ModelFamilyDimensionContractError(ValueError):
    """Raised when a model family requests an unprofiled feature dimension."""


def active_dimensions_for_model_type(model_type: str) -> frozenset[str]:
    """Return active graph-relevant dimensions for a known B2.4 model family."""

    try:
        return B24_MODEL_FAMILY_DIMENSION_CONTRACT[model_type]
    except KeyError as exc:
        raise ModelFamilyDimensionContractError(
            f"unknown B2.4 model family dimension contract: {model_type}"
        ) from exc


def assert_profiled_dimensions_cover_model(
    *,
    model_type: str,
    profiled_dimensions: tuple[str, ...],
) -> None:
    """Fail closed when an active model dimension lacks a P4 live profile."""

    active_dimensions = active_dimensions_for_model_type(model_type)
    profiled = frozenset(profiled_dimensions)
    missing = sorted(active_dimensions - profiled)
    if missing:
        raise ModelFamilyDimensionContractError(
            "active B2.4 model dimensions lack P4 profiling: "
            + ", ".join(missing)
        )


def assert_candidate_dimensions_allowed_for_graph_build(
    *,
    model_type: str,
    requested_dimensions: tuple[str, ...],
    profiled_dimensions: tuple[str, ...],
) -> None:
    """Guard future graph build paths against inactive or unprofiled dimensions."""

    active_dimensions = active_dimensions_for_model_type(model_type)
    requested = frozenset(requested_dimensions)
    inactive = sorted(requested - active_dimensions)
    if inactive:
        raise ModelFamilyDimensionContractError(
            "requested inactive B2.4 model dimensions: " + ", ".join(inactive)
        )
    assert_profiled_dimensions_cover_model(
        model_type=model_type,
        profiled_dimensions=profiled_dimensions,
    )
