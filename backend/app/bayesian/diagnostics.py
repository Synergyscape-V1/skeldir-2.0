"""Governed B2.4-P7 diagnostic policy and child-side ArviZ reduction."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.bayesian.intervals import (
    DiagnosticThresholds,
    IntervalPayloadBounds,
    adjudicate_interval,
)


B24_P7_DIAGNOSTIC_POLICY_VERSION = "b24-p7-diagnostic-policy-v1"
B24_P7_DIAGNOSTIC_TARGET_FILTER_VERSION = "b24-p7-target-filter-v1"
B24_P7_INTERVAL_POLICY_VERSION = "b24-p7-interval-policy-v1"


@dataclass(frozen=True)
class DiagnosticTargetPolicy:
    diagnostic_policy_version: str = B24_P7_DIAGNOSTIC_POLICY_VERSION
    diagnostic_target_filter_version: str = B24_P7_DIAGNOSTIC_TARGET_FILTER_VERSION
    interval_policy_version: str = B24_P7_INTERVAL_POLICY_VERSION
    hdi_probability: float = 0.95
    diagnostic_target_var_names: tuple[str, ...] = ("mu",)
    diagnostic_target_coords: dict[str, Any] = field(default_factory=dict)
    interval_target_var_names: tuple[str, ...] = ("mu",)
    interval_target_coords: dict[str, Any] = field(default_factory=dict)
    excluded_deterministic_var_names: tuple[str, ...] = ("observed_signal",)
    allowed_interval_targets: tuple[str, ...] = ("mu",)
    max_diagnostic_variables: int = 4
    max_diagnostic_elements: int = 4096
    max_diagnostic_coords: int = 8
    max_hdi_elements: int = 4
    max_interval_dimensions: int = 1
    max_interval_elements: int = 4
    max_interval_summary_bytes: int = 2048
    r_hat_max_threshold: float = 1.01
    ess_min_threshold: float = 400.0
    divergence_count_threshold: int = 0
    min_chains: int = 1
    min_samples_actual: int = 1
    finite_value_policy: str = "required"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "diagnostic_target_var_names",
            "interval_target_var_names",
            "excluded_deterministic_var_names",
            "allowed_interval_targets",
        ):
            payload[key] = list(payload[key])
        return payload

    def thresholds(self) -> DiagnosticThresholds:
        return DiagnosticThresholds(
            r_hat_max_threshold=self.r_hat_max_threshold,
            ess_min_threshold=self.ess_min_threshold,
            divergence_count_threshold=self.divergence_count_threshold,
            min_chains=self.min_chains,
            min_samples_actual=self.min_samples_actual,
        )

    def interval_bounds(self) -> IntervalPayloadBounds:
        return IntervalPayloadBounds(
            max_interval_dimensions=self.max_interval_dimensions,
            max_interval_elements=self.max_interval_elements,
            max_interval_summary_bytes=self.max_interval_summary_bytes,
        )


DEFAULT_P7_DIAGNOSTIC_POLICY = DiagnosticTargetPolicy()


def _target_array(idata: Any, variable: str, coords: dict[str, Any]) -> Any:
    posterior = getattr(idata, "posterior")
    if variable not in posterior:
        raise ValueError(f"governed diagnostic target missing: {variable}")
    data = posterior[variable]
    return data.sel(**coords) if coords else data


def _select_coords(idata: Any, coords: dict[str, Any]) -> Any:
    return idata.sel(**coords) if coords else idata


def _scope_counts(idata: Any, policy: DiagnosticTargetPolicy) -> dict[str, int]:
    variable_names = set(policy.diagnostic_target_var_names) | set(
        policy.interval_target_var_names
    )
    elements = 0
    coord_count = 0
    for variable in variable_names:
        coords = (
            policy.interval_target_coords
            if variable in policy.interval_target_var_names
            else policy.diagnostic_target_coords
        )
        data = _target_array(idata, variable, coords)
        elements += int(data.size)
        coord_count += sum(
            1
            for dim in data.dims
            if dim not in {"chain", "draw"} and int(data.sizes.get(dim, 0)) > 0
        )
    return {
        "variable_count": len(variable_names),
        "element_count": elements,
        "coord_count": coord_count,
    }


def _as_floats(value: Any) -> list[float]:
    import numpy as np

    array = np.asarray(value, dtype=float)
    return [float(item) for item in array.reshape(-1)]


def _extract_scalar_hdi(hdi_dataset: Any, variable: str) -> tuple[float, float, list[int], int]:
    values = _as_floats(hdi_dataset[variable].values)
    if len(values) != 2:
        raise ValueError("interval_dimension_exceeded")
    return values[0], values[1], [], 1


def compute_arviz_diagnostic_summary(
    idata: Any,
    *,
    fit_metadata: dict[str, Any],
    policy: DiagnosticTargetPolicy = DEFAULT_P7_DIAGNOSTIC_POLICY,
) -> dict[str, Any]:
    """Reduce in-child InferenceData to a bounded diagnostic summary."""

    import arviz as az
    import numpy as np

    scope = _scope_counts(idata, policy)
    if scope["variable_count"] > policy.max_diagnostic_variables:
        reason = "diagnostic_scope_too_large"
        adjudication = adjudicate_interval(
            r_hat_max=None,
            ess_min=None,
            divergence_count=None,
            n_chains=fit_metadata.get("n_chains"),
            n_samples_actual=fit_metadata.get("n_samples_actual"),
            hdi_lower=None,
            hdi_upper=None,
            interval_shape=[],
            interval_element_count=0,
            thresholds=policy.thresholds(),
            bounds=policy.interval_bounds(),
        ).as_dict()
        adjudication["diagnostic_failure_reason"] = reason
        return _summary_payload(fit_metadata, policy, adjudication, scope)
    if (
        scope["element_count"] > policy.max_diagnostic_elements
        or scope["coord_count"] > policy.max_diagnostic_coords
    ):
        reason = "diagnostic_scope_too_large"
        adjudication = adjudicate_interval(
            r_hat_max=None,
            ess_min=None,
            divergence_count=None,
            n_chains=fit_metadata.get("n_chains"),
            n_samples_actual=fit_metadata.get("n_samples_actual"),
            hdi_lower=None,
            hdi_upper=None,
            interval_shape=[],
            interval_element_count=0,
            thresholds=policy.thresholds(),
            bounds=policy.interval_bounds(),
        ).as_dict()
        adjudication["diagnostic_failure_reason"] = reason
        return _summary_payload(fit_metadata, policy, adjudication, scope)

    diagnostic_idata = _select_coords(idata, policy.diagnostic_target_coords)
    interval_idata = _select_coords(idata, policy.interval_target_coords)
    rhat = az.rhat(
        diagnostic_idata,
        var_names=list(policy.diagnostic_target_var_names),
    )
    ess = az.ess(
        diagnostic_idata,
        var_names=list(policy.diagnostic_target_var_names),
    )
    hdi = az.hdi(
        interval_idata,
        var_names=list(policy.interval_target_var_names),
        hdi_prob=policy.hdi_probability,
    )
    r_hat_values = _as_floats(rhat.to_array().values)
    ess_values = _as_floats(ess.to_array().values)
    r_hat_max = float(np.max(r_hat_values)) if r_hat_values else float("nan")
    ess_min = float(np.min(ess_values)) if ess_values else float("nan")
    divergence_count = 0
    sample_stats = getattr(idata, "sample_stats", None)
    if sample_stats is not None and "diverging" in sample_stats:
        divergence_count = int(np.asarray(sample_stats["diverging"].values).sum())
    hdi_lower, hdi_upper, interval_shape, interval_element_count = _extract_scalar_hdi(
        hdi, policy.interval_target_var_names[0]
    )
    if interval_element_count > policy.max_hdi_elements:
        hdi_lower = None
        hdi_upper = None
        interval_shape = []
        interval_element_count = 0
    adjudication = adjudicate_interval(
        r_hat_max=r_hat_max,
        ess_min=ess_min,
        divergence_count=divergence_count,
        n_chains=fit_metadata.get("n_chains"),
        n_samples_actual=fit_metadata.get("n_samples_actual"),
        hdi_lower=hdi_lower,
        hdi_upper=hdi_upper,
        interval_shape=interval_shape,
        interval_element_count=interval_element_count,
        thresholds=policy.thresholds(),
        bounds=policy.interval_bounds(),
    ).as_dict()
    return _summary_payload(
        fit_metadata,
        policy,
        {
            **adjudication,
            "r_hat_max": r_hat_max,
            "ess_min": ess_min,
            "divergence_count": divergence_count,
        },
        scope,
    )


def _summary_payload(
    fit_metadata: dict[str, Any],
    policy: DiagnosticTargetPolicy,
    adjudication: dict[str, Any],
    scope: dict[str, int],
) -> dict[str, Any]:
    adjudication.setdefault("r_hat_max", None)
    adjudication.setdefault("ess_min", None)
    adjudication.setdefault("divergence_count", 0)
    adjudication.setdefault("hdi_lower", None)
    adjudication.setdefault("hdi_upper", None)
    adjudication.setdefault("interval_shape", [])
    adjudication.setdefault("interval_element_count", 0)
    adjudication.setdefault("interval_summary_bytes", 0)
    for key in ("r_hat_max", "ess_min", "hdi_lower", "hdi_upper"):
        value = adjudication.get(key)
        if isinstance(value, int | float) and not math.isfinite(float(value)):
            adjudication[key] = None
    return {
        **fit_metadata,
        "diagnostics_computed_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_policy_version": policy.diagnostic_policy_version,
        "diagnostic_target_filter_version": policy.diagnostic_target_filter_version,
        "interval_policy_version": policy.interval_policy_version,
        "hdi_probability": policy.hdi_probability,
        "diagnostic_target_var_names": list(policy.diagnostic_target_var_names),
        "interval_target_var_names": list(policy.interval_target_var_names),
        "diagnostic_scope": scope,
        **adjudication,
    }
