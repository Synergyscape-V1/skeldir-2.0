"""B1.7-P6 benchmark adjudication enforcer tests.

Includes regression guards for benchmark-lane fail-closed thresholds.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return _repo_root() / "scripts" / "ci" / "enforce_b17_p6_benchmark_adjudication.py"


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _write_payload(
    path: Path,
    *,
    prewarm_enabled: bool,
    overall_p95: float,
    warm_p95: float,
    cold_p95: float,
    hit_ratio: float,
    cold_count: int,
    prewarm_assisted: int,
    provider_delay_ms: int = 120,
    distinct_allocations: int = 12,
    distinct_determinants: int = 60,
    distinct_users: int = 30,
    max_requests_per_determinant: int = 4,
    duplicate_request_ratio: float = 0.5,
    unique_determinant_ratio: float = 0.5,
) -> None:
    payload = {
        "prewarm_enabled": prewarm_enabled,
        "provider_delay_ms": provider_delay_ms,
        "latency_ms": {
            "overall_p95": overall_p95,
            "warm_p95": warm_p95,
            "cold_p95": cold_p95,
        },
        "cache_hit_rate": {"ratio": hit_ratio},
        "execution_path_counts": {
            "cold_path_generated": cold_count,
            "prewarm_assisted_cache_hit": prewarm_assisted,
            "warm_cache_hit": 75,
        },
        "workload_profile": {
            "distinct_allocation_count": distinct_allocations,
            "distinct_cache_determinant_count": distinct_determinants,
            "distinct_user_count": distinct_users,
            "max_requests_per_determinant": max_requests_per_determinant,
            "duplicate_request_ratio": duplicate_request_ratio,
            "unique_determinant_ratio": unique_determinant_ratio,
        },
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_latency_model(
    path: Path, *, provider_delay_ms: int = 120, minimum_provider_delay_ms: int = 50
) -> None:
    payload = {
        "provider_delay_ms": provider_delay_ms,
        "minimum_provider_delay_ms": minimum_provider_delay_ms,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_b17_p6_benchmark_adjudication_enforcer_passes_with_valid_payloads(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    prewarm = tmp_path / "prewarm.json"
    latency_model = tmp_path / "latency_model.json"
    _write_latency_model(latency_model)
    _write_payload(
        baseline,
        prewarm_enabled=False,
        overall_p95=490.0,
        warm_p95=120.0,
        cold_p95=720.0,
        hit_ratio=0.62,
        cold_count=35,
        prewarm_assisted=0,
    )
    _write_payload(
        prewarm,
        prewarm_enabled=True,
        overall_p95=470.0,
        warm_p95=115.0,
        cold_p95=500.0,
        hit_ratio=0.72,
        cold_count=15,
        prewarm_assisted=18,
    )

    result = _run_enforcer(
        "--baseline-file",
        str(baseline),
        "--prewarm-file",
        str(prewarm),
        "--latency-model-file",
        str(latency_model),
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b17_p6_benchmark_adjudication_enforcer_fails_on_slo_regression(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    prewarm = tmp_path / "prewarm.json"
    latency_model = tmp_path / "latency_model.json"
    _write_latency_model(latency_model, provider_delay_ms=120, minimum_provider_delay_ms=50)
    _write_payload(
        baseline,
        prewarm_enabled=False,
        overall_p95=480.0,
        warm_p95=130.0,
        cold_p95=710.0,
        hit_ratio=0.65,
        cold_count=28,
        prewarm_assisted=0,
    )
    _write_payload(
        prewarm,
        prewarm_enabled=True,
        overall_p95=520.0,
        warm_p95=125.0,
        cold_p95=620.0,
        hit_ratio=0.58,
        cold_count=30,
        prewarm_assisted=0,
        provider_delay_ms=0,
        distinct_allocations=2,
        distinct_determinants=8,
        distinct_users=5,
    )

    result = _run_enforcer(
        "--baseline-file",
        str(baseline),
        "--prewarm-file",
        str(prewarm),
        "--latency-model-file",
        str(latency_model),
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "overall_p95_not_below_target" in combined
    assert "cache_hit_ratio_not_above_target" in combined
    assert "prewarm_provider_delay_below_min" in combined
    assert "prewarm_efficacy_no_comparative_overall_p95_improvement" in combined
    assert "prewarm_efficacy_no_comparative_cache_hit_improvement" in combined


def test_b17_p6_benchmark_adjudication_enforcer_fails_when_prewarm_does_not_improve_comparatively(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    prewarm = tmp_path / "prewarm.json"
    latency_model = tmp_path / "latency_model.json"
    _write_latency_model(latency_model)
    _write_payload(
        baseline,
        prewarm_enabled=False,
        overall_p95=335.63,
        warm_p95=184.84,
        cold_p95=368.89,
        hit_ratio=0.70,
        cold_count=24,
        prewarm_assisted=0,
    )
    _write_payload(
        prewarm,
        prewarm_enabled=True,
        overall_p95=398.53,
        warm_p95=244.15,
        cold_p95=400.83,
        hit_ratio=0.70,
        cold_count=24,
        prewarm_assisted=16,
    )

    result = _run_enforcer(
        "--baseline-file",
        str(baseline),
        "--prewarm-file",
        str(prewarm),
        "--latency-model-file",
        str(latency_model),
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "prewarm_efficacy_no_comparative_overall_p95_improvement" in combined
    assert "prewarm_efficacy_no_comparative_cache_hit_improvement" in combined


def test_b17_p6_benchmark_adjudication_enforcer_fails_on_latency_model_mismatch(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    prewarm = tmp_path / "prewarm.json"
    latency_model = tmp_path / "latency_model.json"
    _write_latency_model(latency_model, provider_delay_ms=120, minimum_provider_delay_ms=50)
    _write_payload(
        baseline,
        prewarm_enabled=False,
        overall_p95=480.0,
        warm_p95=120.0,
        cold_p95=700.0,
        hit_ratio=0.61,
        cold_count=30,
        prewarm_assisted=0,
        provider_delay_ms=100,
    )
    _write_payload(
        prewarm,
        prewarm_enabled=True,
        overall_p95=460.0,
        warm_p95=110.0,
        cold_p95=520.0,
        hit_ratio=0.70,
        cold_count=20,
        prewarm_assisted=10,
        provider_delay_ms=100,
    )

    result = _run_enforcer(
        "--baseline-file",
        str(baseline),
        "--prewarm-file",
        str(prewarm),
        "--latency-model-file",
        str(latency_model),
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "baseline_provider_delay_not_authoritative" in combined
    assert "prewarm_provider_delay_not_authoritative" in combined


def test_b17_p6_benchmark_adjudication_enforcer_fails_on_workload_anti_cheat_regression(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    prewarm = tmp_path / "prewarm.json"
    latency_model = tmp_path / "latency_model.json"
    _write_latency_model(latency_model)
    _write_payload(
        baseline,
        prewarm_enabled=False,
        overall_p95=480.0,
        warm_p95=120.0,
        cold_p95=690.0,
        hit_ratio=0.62,
        cold_count=30,
        prewarm_assisted=0,
        max_requests_per_determinant=5,
        duplicate_request_ratio=0.70,
        unique_determinant_ratio=0.30,
    )
    _write_payload(
        prewarm,
        prewarm_enabled=True,
        overall_p95=460.0,
        warm_p95=110.0,
        cold_p95=510.0,
        hit_ratio=0.70,
        cold_count=20,
        prewarm_assisted=12,
        max_requests_per_determinant=5,
        duplicate_request_ratio=0.70,
        unique_determinant_ratio=0.30,
    )

    result = _run_enforcer(
        "--baseline-file",
        str(baseline),
        "--prewarm-file",
        str(prewarm),
        "--latency-model-file",
        str(latency_model),
    )
    assert result.returncode != 0
    combined = result.stdout + result.stderr
    assert "baseline_max_requests_per_determinant_above_max" in combined
    assert "baseline_duplicate_request_ratio_above_max" in combined
    assert "baseline_unique_determinant_ratio_below_min" in combined
