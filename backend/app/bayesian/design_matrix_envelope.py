"""B2.4-P4 arithmetic-only design-matrix and tensor memory envelope."""

from __future__ import annotations

from dataclasses import dataclass

from app.bayesian.input_profile import B24InputProfile
from app.bayesian.model_family_contract import assert_profiled_dimensions_cover_model
from app.bayesian.resource_bounds import B24_MEMORY_ESTIMATE_SAFETY_FACTOR


FLOAT64_BYTES = 8
FIXED_INPUT_OVERHEAD_BYTES = 16 * 1024 * 1024


@dataclass(frozen=True)
class DesignMatrixEnvelope:
    estimated_design_matrix_rows: int
    estimated_design_matrix_columns: int
    estimated_design_matrix_cells: int
    estimated_tensor_shape: tuple[int, ...]
    estimated_tensor_elements: int
    estimated_tensor_rank: int
    estimated_input_memory_bytes: int


def _product(values: tuple[int, ...]) -> int:
    product = 1
    for value in values:
        product *= max(1, int(value))
    return product


def estimate_design_matrix_envelope(profile: B24InputProfile) -> DesignMatrixEnvelope:
    """Estimate matrix/tensor size using integer formulas only."""

    assert_profiled_dimensions_cover_model(
        model_type=profile.model_type,
        profiled_dimensions=profile.cardinality_profiled_dimensions,
    )
    rows = max(1, profile.touchpoint_count + profile.conversion_count)
    columns = max(
        1,
        1
        + profile.channel_count
        + profile.currency_count
        + profile.provider_count
        + profile.campaign_or_feature_count,
    )
    cells = rows * columns
    tensor_shape = (
        rows,
        max(1, profile.channel_count),
        max(1, profile.currency_count),
        max(1, profile.provider_count + profile.campaign_or_feature_count),
    )
    tensor_elements = _product(tensor_shape)
    memory_bytes = (
        tensor_elements * FLOAT64_BYTES * B24_MEMORY_ESTIMATE_SAFETY_FACTOR
        + FIXED_INPUT_OVERHEAD_BYTES
    )
    return DesignMatrixEnvelope(
        estimated_design_matrix_rows=rows,
        estimated_design_matrix_columns=columns,
        estimated_design_matrix_cells=cells,
        estimated_tensor_shape=tensor_shape,
        estimated_tensor_elements=tensor_elements,
        estimated_tensor_rank=len(tensor_shape),
        estimated_input_memory_bytes=memory_bytes,
    )
