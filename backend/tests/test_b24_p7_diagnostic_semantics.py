from __future__ import annotations

import ast
import importlib.util
import math
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.bayesian.diagnostics import (
    DEFAULT_P7_DIAGNOSTIC_POLICY,
    compute_arviz_diagnostic_summary,
)
from app.bayesian.fit_execution import _diagnostic_stage_failure_reason
from app.bayesian.intervals import adjudicate_interval
from app.bayesian.result_contract import validate_result_summary


ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTICS = ROOT / "backend/app/bayesian/diagnostics.py"
INTERVALS = ROOT / "backend/app/bayesian/intervals.py"
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
SAMPLER_CHILD = ROOT / "backend/app/bayesian/sampler_child.py"
RESULT_CONTRACT = ROOT / "backend/app/bayesian/result_contract.py"
MIGRATION = (
    ROOT
    / "alembic/versions/007_skeldir_foundation/202606041200_b24_p7_diagnostic_semantics.py"
)
VALIDATOR = ROOT / "scripts/ci/validate_b24_p7_diagnostics.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _passing_interval():
    return adjudicate_interval(
        r_hat_max=1.0,
        ess_min=500.0,
        divergence_count=0,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[],
        interval_element_count=1,
    )


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p7_diagnostics", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b24_p7_bad_rhat_blocks_interval() -> None:
    result = adjudicate_interval(
        r_hat_max=1.02,
        ess_min=500.0,
        divergence_count=0,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[],
        interval_element_count=1,
    )

    assert result.credible_interval_status == "not_available"
    assert result.diagnostic_status == "failed"
    assert result.diagnostic_failure_reason == "bad_rhat"
    assert result.hdi_lower is None
    assert result.hdi_upper is None


def test_b24_p7_low_ess_blocks_interval() -> None:
    result = adjudicate_interval(
        r_hat_max=1.0,
        ess_min=399.0,
        divergence_count=0,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[],
        interval_element_count=1,
    )

    assert result.credible_interval_status == "not_available"
    assert result.diagnostic_failure_reason == "low_ess"


def test_b24_p7_divergence_blocks_interval() -> None:
    result = adjudicate_interval(
        r_hat_max=1.0,
        ess_min=500.0,
        divergence_count=1,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[],
        interval_element_count=1,
    )

    assert result.credible_interval_status == "not_available"
    assert result.diagnostic_failure_reason == "divergence"


def test_b24_p7_positive_interval_requires_all_governed_conditions() -> None:
    result = _passing_interval()

    assert result.credible_interval_status == "available"
    assert result.diagnostic_status == "passed"
    assert result.diagnostic_failure_reason is None
    assert result.hdi_lower == pytest.approx(-0.1)
    assert result.hdi_upper == pytest.approx(0.1)
    assert result.interval_element_count == 1


def test_b24_p7_nonfinite_governed_diagnostics_cannot_pass() -> None:
    result = adjudicate_interval(
        r_hat_max=math.nan,
        ess_min=500.0,
        divergence_count=0,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[],
        interval_element_count=1,
    )

    assert result.credible_interval_status == "not_available"
    assert result.diagnostic_failure_reason == "nonfinite_diagnostic"


def test_b24_p7_interval_payload_bounds_are_enforced() -> None:
    result = adjudicate_interval(
        r_hat_max=1.0,
        ess_min=500.0,
        divergence_count=0,
        n_chains=2,
        n_samples_actual=1000,
        hdi_lower=-0.1,
        hdi_upper=0.1,
        interval_shape=[2, 2],
        interval_element_count=4,
    )

    assert result.credible_interval_status == "not_available"
    assert result.diagnostic_failure_reason == "interval_dimension_exceeded"


def test_b24_p7_policy_versions_and_target_scope_are_centralized() -> None:
    policy = DEFAULT_P7_DIAGNOSTIC_POLICY

    assert policy.diagnostic_policy_version == "b24-p7-diagnostic-policy-v1"
    assert policy.diagnostic_target_filter_version == "b24-p7-target-filter-v1"
    assert policy.interval_policy_version == "b24-p7-interval-policy-v1"
    assert policy.r_hat_max_threshold == pytest.approx(1.01)
    assert policy.ess_min_threshold == pytest.approx(400.0)
    assert policy.divergence_count_threshold == 0
    assert policy.diagnostic_target_var_names == ("mu",)
    assert policy.interval_target_var_names == ("mu",)
    assert "observed_signal" in policy.excluded_deterministic_var_names


def test_b24_p7_parent_imports_no_native_diagnostic_stack() -> None:
    for path in (FIT_EXECUTION, RESULT_CONTRACT, INTERVALS):
        tree = ast.parse(_read(path), filename=str(path))
        imported = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imported = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        assert not ({"arviz", "pymc", "pytensor"} & imported)
        assert not ({"arviz", "pymc", "pytensor"} & from_imported)


def test_b24_p7_arviz_calls_are_child_scoped_and_governed() -> None:
    diagnostics = _read(DIAGNOSTICS)
    child = _read(SAMPLER_CHILD)

    assert "import arviz as az" in diagnostics
    assert "az.summary(" not in diagnostics
    assert "_select_coords(idata, policy.diagnostic_target_coords)" in diagnostics
    assert "_select_coords(idata, policy.interval_target_coords)" in diagnostics
    assert "var_names=list(policy.diagnostic_target_var_names)" in diagnostics
    assert "var_names=list(policy.interval_target_var_names)" in diagnostics
    assert "compute_arviz_diagnostic_summary(" in child
    assert "return_inferencedata=True" in child


def test_b24_p7_stage_markers_are_ordered_and_classified() -> None:
    child = _read(SAMPLER_CHILD)
    fit_execution = _read(FIT_EXECUTION)
    for token in (
        '"sampling_completed"',
        '"diagnostics_started"',
        '"diagnostics_completed"',
        '"intervals_started"',
        '"intervals_completed"',
        '"result_summary_written"',
    ):
        assert token in child
    assert "_diagnostic_stage_failure_reason" in fit_execution
    assert "diagnostics_timeout" in fit_execution
    assert "diagnostics_failed" in fit_execution
    assert "FallbackReason.WORKER_FAILURE" in fit_execution


def test_b24_p7_result_contract_rejects_trace_payloads_and_nonfinite_values() -> None:
    base = {
        "schema_version": "b24-p6-child-result-v1",
        "status": "sampled_unvalidated",
        "n_chains": 2,
        "n_samples_actual": 1000,
    }
    with pytest.raises(ValueError, match="posterior"):
        validate_result_summary({**base, "posterior": [1, 2, 3]})
    with pytest.raises(ValueError, match="non-finite"):
        validate_result_summary({**base, "r_hat_max": math.inf})
    for key in (
        "inference_data_blob",
        "posterior_array",
        "posterior_draws",
        "netcdf",
        "zarr",
    ):
        with pytest.raises(ValueError, match="posterior|trace"):
            validate_result_summary({**base, key: "forbidden"})


def test_b24_p7_sampled_unvalidated_alone_is_not_interval_valid() -> None:
    with pytest.raises(ValueError, match="non-finite|posterior|unknown|summary"):
        validate_result_summary(
            {
                "schema_version": "b24-p6-child-result-v1",
                "status": "sampled_unvalidated",
                "credible_interval_status": "available",
                "diagnostic_status": "not_computed",
                "n_chains": 2,
                "n_samples_actual": 1000,
                "r_hat_max": math.nan,
            }
        )


def test_b24_p7_diagnostic_stage_timeout_is_classified(tmp_path: Path) -> None:
    marker = tmp_path / "markers.jsonl"
    marker.write_text('{"stage":"sampling_completed"}\n{"stage":"diagnostics_started"}\n')

    assert (
        _diagnostic_stage_failure_reason(marker, timed_out=True)
        == "diagnostics_timeout"
    )
    assert (
        _diagnostic_stage_failure_reason(marker, timed_out=False)
        == "diagnostics_failed"
    )


class _FakePosterior(dict):
    pass


class _FakeDataArray:
    size = 1
    dims = ("chain", "draw")
    sizes = {"chain": 1, "draw": 1}

    def sel(self, **_coords):
        return self


def test_b24_p7_oversized_scope_fails_before_arviz_diagnostic_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _forbidden_call(*_args, **_kwargs):
        raise AssertionError("ArviZ diagnostic call should not execute")

    monkeypatch.setitem(
        sys.modules,
        "arviz",
        SimpleNamespace(rhat=_forbidden_call, ess=_forbidden_call, hdi=_forbidden_call),
    )
    policy = replace(
        DEFAULT_P7_DIAGNOSTIC_POLICY,
        diagnostic_target_var_names=("a", "b"),
        interval_target_var_names=("a",),
        max_diagnostic_variables=1,
    )
    idata = SimpleNamespace(
        posterior=_FakePosterior({"a": _FakeDataArray(), "b": _FakeDataArray()})
    )

    summary = compute_arviz_diagnostic_summary(
        idata,
        fit_metadata={
            "schema_version": "b24-p6-child-result-v1",
            "status": "sampled_unvalidated",
            "fit_id": "fit",
            "tenant_id": "tenant",
            "model_type": "bayesian_attribution_confidence",
            "model_version": "test",
            "source_snapshot_hash": "a" * 64,
            "n_chains": 2,
            "n_samples_actual": 1000,
            "execution_success": True,
        },
        policy=policy,
    )

    assert summary["credible_interval_status"] == "not_available"
    assert summary["diagnostic_failure_reason"] == "diagnostic_scope_too_large"


def test_b24_p7_non_target_deterministic_nan_does_not_poison_governed_target() -> None:
    np = pytest.importorskip("numpy")
    az = pytest.importorskip("arviz")

    rng = np.random.default_rng(7)
    chain_draws = rng.normal(0.0, 1.0, size=(2, 600))
    idata = az.from_dict(
        posterior={
            "mu": chain_draws,
            "auxiliary_nan": np.full((2, 600), np.nan),
        },
        sample_stats={"diverging": np.zeros((2, 600), dtype=bool)},
    )

    summary = compute_arviz_diagnostic_summary(
        idata,
        fit_metadata={
            "schema_version": "b24-p6-child-result-v1",
            "status": "sampled_unvalidated",
            "fit_id": "fit",
            "tenant_id": "tenant",
            "model_type": "bayesian_attribution_confidence",
            "model_version": "test",
            "source_snapshot_hash": "a" * 64,
            "n_chains": 2,
            "n_samples_actual": 1200,
            "execution_success": True,
        },
        policy=replace(
            DEFAULT_P7_DIAGNOSTIC_POLICY,
            min_chains=2,
            min_samples_actual=1000,
        ),
    )

    assert summary["diagnostic_target_var_names"] == ["mu"]
    assert summary["interval_target_var_names"] == ["mu"]
    assert summary["credible_interval_status"] == "available"
    assert summary["diagnostic_status"] == "passed"
    assert summary["diagnostic_failure_reason"] is None


def test_b24_p7_migration_contains_interval_conditionality_constraints() -> None:
    migration = _read(MIGRATION)
    for token in (
        "diagnostic_status",
        "diagnostic_failure_reason",
        "diagnostic_policy_version",
        "diagnostic_target_filter_version",
        "interval_policy_version",
        "diagnostics_computed_at",
        "hdi_lower",
        "hdi_upper",
        "interval_shape jsonb",
        "credible_interval_status <> 'available'",
        "diagnostic_status = 'passed'",
        "r_hat_max <= 1.01",
        "ess_min >= 400",
        "divergence_count = 0",
    ):
        assert token in migration


def test_b24_p7_ci_validator_negative_controls() -> None:
    validator = _load_validator()
    validator.validate_all()
    validator.run_negative_controls()
