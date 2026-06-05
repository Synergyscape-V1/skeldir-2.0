"""Bounded interval conditionality for B2.4-P7 diagnostics."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class DiagnosticThresholds:
    r_hat_max_threshold: float = 1.01
    ess_min_threshold: float = 400.0
    divergence_count_threshold: int = 0
    min_chains: int = 1
    min_samples_actual: int = 1


@dataclass(frozen=True)
class IntervalPayloadBounds:
    max_interval_dimensions: int = 1
    max_interval_elements: int = 4
    max_interval_summary_bytes: int = 2048


@dataclass(frozen=True)
class IntervalAdjudication:
    credible_interval_status: str
    diagnostic_status: str
    diagnostic_failure_reason: str | None
    hdi_lower: float | None
    hdi_upper: float | None
    interval_shape: list[int]
    interval_element_count: int
    interval_summary_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _finite_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _valid_divergence_count(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = int(value)
    except (TypeError, ValueError):
        return None
    if float(value) != float(converted) or converted < 0:
        return None
    return converted


def _summary_size_bytes(payload: dict[str, Any]) -> int:
    return len(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        .encode("utf-8")
    )


def _unavailable(
    *,
    reason: str,
    diagnostic_status: str = "failed",
    r_hat_max: float | None = None,
    ess_min: float | None = None,
    divergence_count: int | None = None,
    bounds: IntervalPayloadBounds,
) -> IntervalAdjudication:
    size = _summary_size_bytes(
        {
            "credible_interval_status": "not_available",
            "diagnostic_status": diagnostic_status,
            "diagnostic_failure_reason": reason,
            "r_hat_max": r_hat_max,
            "ess_min": ess_min,
            "divergence_count": divergence_count,
            "hdi_lower": None,
            "hdi_upper": None,
            "interval_shape": [],
            "interval_element_count": 0,
        }
    )
    return IntervalAdjudication(
        credible_interval_status="not_available",
        diagnostic_status=diagnostic_status,
        diagnostic_failure_reason=reason,
        hdi_lower=None,
        hdi_upper=None,
        interval_shape=[],
        interval_element_count=0,
        interval_summary_bytes=min(size, bounds.max_interval_summary_bytes + 1),
    )


def adjudicate_interval(
    *,
    r_hat_max: Any,
    ess_min: Any,
    divergence_count: Any,
    n_chains: Any,
    n_samples_actual: Any,
    hdi_lower: Any,
    hdi_upper: Any,
    interval_shape: list[int] | tuple[int, ...] | None,
    interval_element_count: Any,
    thresholds: DiagnosticThresholds | None = None,
    bounds: IntervalPayloadBounds | None = None,
) -> IntervalAdjudication:
    """Return the P7 interval verdict after finite and structural validation."""

    thresholds = thresholds or DiagnosticThresholds()
    bounds = bounds or IntervalPayloadBounds()

    rhat = _finite_float(r_hat_max)
    ess = _finite_float(ess_min)
    divergences = _valid_divergence_count(divergence_count)
    chains = _valid_divergence_count(n_chains)
    samples = _valid_divergence_count(n_samples_actual)
    lower = _finite_float(hdi_lower)
    upper = _finite_float(hdi_upper)

    if rhat is None or ess is None or divergences is None:
        return _unavailable(
            reason="nonfinite_diagnostic",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if chains is None or samples is None:
        return _unavailable(
            reason="invalid_diagnostic_summary",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if chains < thresholds.min_chains or samples < thresholds.min_samples_actual:
        return _unavailable(
            reason="invalid_diagnostic_summary",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if rhat > thresholds.r_hat_max_threshold:
        return _unavailable(
            reason="bad_rhat",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if ess < thresholds.ess_min_threshold:
        return _unavailable(
            reason="low_ess",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if divergences > thresholds.divergence_count_threshold:
        return _unavailable(
            reason="divergence",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )

    shape = [int(value) for value in (interval_shape or [])]
    element_count = _valid_divergence_count(interval_element_count)
    if (
        element_count is None
        or element_count < 1
        or len(shape) > bounds.max_interval_dimensions
    ):
        return _unavailable(
            reason="interval_dimension_exceeded",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if element_count > bounds.max_interval_elements:
        return _unavailable(
            reason="interval_payload_too_large",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    if lower is None or upper is None or lower > upper:
        return _unavailable(
            reason="nonfinite_diagnostic",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )

    candidate = {
        "credible_interval_status": "available",
        "diagnostic_status": "passed",
        "diagnostic_failure_reason": None,
        "r_hat_max": rhat,
        "ess_min": ess,
        "divergence_count": divergences,
        "hdi_lower": lower,
        "hdi_upper": upper,
        "interval_shape": shape,
        "interval_element_count": element_count,
    }
    size = _summary_size_bytes(candidate)
    if size > bounds.max_interval_summary_bytes:
        return _unavailable(
            reason="interval_payload_too_large",
            r_hat_max=rhat,
            ess_min=ess,
            divergence_count=divergences,
            bounds=bounds,
        )
    return IntervalAdjudication(
        credible_interval_status="available",
        diagnostic_status="passed",
        diagnostic_failure_reason=None,
        hdi_lower=lower,
        hdi_upper=upper,
        interval_shape=shape,
        interval_element_count=element_count,
        interval_summary_bytes=size,
    )
