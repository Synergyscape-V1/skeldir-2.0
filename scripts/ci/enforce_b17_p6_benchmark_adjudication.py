#!/usr/bin/env python3
"""B1.7-P6 benchmark adjudication enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, failures: list[str], message: str) -> None:
    if not condition:
        failures.append(message)


def _latency(summary: dict[str, Any], key: str) -> float | None:
    try:
        return float(summary.get("latency_ms", {}).get(key))
    except (TypeError, ValueError):
        return None


def _cache_hit_ratio(summary: dict[str, Any]) -> float | None:
    payload = summary.get("cache_hit_rate", {})
    try:
        return float(payload.get("ratio"))
    except (TypeError, ValueError):
        return None


def _state_count(summary: dict[str, Any], state: str) -> int:
    try:
        return int(summary.get("execution_path_counts", {}).get(state, 0))
    except (TypeError, ValueError):
        return 0


def _int_field(summary: dict[str, Any], key: str, *, section: str = "workload_profile") -> int | None:
    try:
        if section:
            return int(summary.get(section, {}).get(key))
        return int(summary.get(key))
    except (TypeError, ValueError):
        return None


def _float_field(summary: dict[str, Any], key: str, *, section: str = "workload_profile") -> float | None:
    try:
        if section:
            return float(summary.get(section, {}).get(key))
        return float(summary.get(key))
    except (TypeError, ValueError):
        return None


def _load_latency_model(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    required_keys = (
        "provider_delay_ms",
        "minimum_provider_delay_ms",
        "calibration_procedure",
        "calibration_evidence",
    )
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise ValueError(f"latency_model_missing_required_keys:{','.join(missing)}")
    procedure = payload.get("calibration_procedure")
    evidence = payload.get("calibration_evidence")
    if not isinstance(procedure, dict):
        raise ValueError("latency_model_missing_empirical_calibration_procedure")
    if not isinstance(evidence, dict):
        raise ValueError("latency_model_missing_empirical_calibration_evidence")
    command = procedure.get("command")
    artifact_refs = evidence.get("artifact_refs")
    if not isinstance(command, str) or not command.strip():
        raise ValueError("latency_model_calibration_procedure_command_missing")
    if not isinstance(artifact_refs, list) or not artifact_refs:
        raise ValueError("latency_model_calibration_evidence_artifact_refs_missing")
    return payload


def _adjudicate(
    *,
    baseline: dict[str, Any],
    prewarm: dict[str, Any],
    overall_p95_max_ms: float,
    cache_hit_ratio_min: float,
    provider_delay_min_ms: float,
    latency_model_provider_delay_ms: int,
    latency_model_min_provider_delay_ms: int,
    min_total_requests: int,
    min_cold_path_samples: int,
    min_distinct_allocations: int,
    min_distinct_determinants: int,
    min_distinct_users: int,
    max_requests_per_determinant: int,
    max_duplicate_request_ratio: float,
    min_unique_determinant_ratio: float,
) -> tuple[int, list[str]]:
    failures: list[str] = []

    prewarm_overall_p95 = _latency(prewarm, "overall_p95")
    prewarm_warm_p95 = _latency(prewarm, "warm_p95")
    prewarm_cold_p95 = _latency(prewarm, "cold_p95")
    prewarm_hit_ratio = _cache_hit_ratio(prewarm)
    prewarm_provider_delay = _int_field(prewarm, "provider_delay_ms", section="")
    baseline_provider_delay = _int_field(baseline, "provider_delay_ms", section="")

    _require(prewarm.get("prewarm_enabled") is True, failures, "prewarm_summary_not_enabled")
    _require(prewarm_overall_p95 is not None, failures, "prewarm_missing_overall_p95")
    _require(prewarm_warm_p95 is not None, failures, "prewarm_missing_warm_p95")
    _require(prewarm_cold_p95 is not None, failures, "prewarm_missing_cold_p95")
    _require(prewarm_hit_ratio is not None, failures, "prewarm_missing_cache_hit_ratio")
    _require(prewarm_provider_delay is not None, failures, "prewarm_missing_provider_delay_ms")
    _require(baseline_provider_delay is not None, failures, "baseline_missing_provider_delay_ms")
    authoritative_provider_delay_floor = max(
        float(provider_delay_min_ms), float(latency_model_min_provider_delay_ms)
    )
    if prewarm_provider_delay is not None:
        _require(
            prewarm_provider_delay >= authoritative_provider_delay_floor,
            failures,
            (
                "prewarm_provider_delay_below_min:"
                f"{prewarm_provider_delay}<{authoritative_provider_delay_floor:.0f}"
            ),
        )
        _require(
            prewarm_provider_delay == int(latency_model_provider_delay_ms),
            failures,
            (
                "prewarm_provider_delay_not_authoritative:"
                f"{prewarm_provider_delay}!={int(latency_model_provider_delay_ms)}"
            ),
        )
    if baseline_provider_delay is not None:
        _require(
            baseline_provider_delay >= authoritative_provider_delay_floor,
            failures,
            (
                "baseline_provider_delay_below_min:"
                f"{baseline_provider_delay}<{authoritative_provider_delay_floor:.0f}"
            ),
        )
        _require(
            baseline_provider_delay == int(latency_model_provider_delay_ms),
            failures,
            (
                "baseline_provider_delay_not_authoritative:"
                f"{baseline_provider_delay}!={int(latency_model_provider_delay_ms)}"
            ),
        )

    if prewarm_overall_p95 is not None:
        _require(
            prewarm_overall_p95 < overall_p95_max_ms,
            failures,
            f"overall_p95_not_below_target:{prewarm_overall_p95:.2f}>={overall_p95_max_ms:.2f}",
        )
    if prewarm_hit_ratio is not None:
        _require(
            prewarm_hit_ratio > cache_hit_ratio_min,
            failures,
            f"cache_hit_ratio_not_above_target:{prewarm_hit_ratio:.4f}<={cache_hit_ratio_min:.4f}",
        )

    baseline_overall_p95 = _latency(baseline, "overall_p95")
    baseline_hit_ratio = _cache_hit_ratio(baseline)
    baseline_warm_hits = _state_count(baseline, "warm_cache_hit") + _state_count(
        baseline, "prewarm_assisted_cache_hit"
    )
    prewarm_warm_hits = _state_count(prewarm, "warm_cache_hit") + _state_count(
        prewarm, "prewarm_assisted_cache_hit"
    )
    prewarm_assisted_hits = _state_count(prewarm, "prewarm_assisted_cache_hit")

    _require(
        baseline.get("prewarm_enabled") is False,
        failures,
        "baseline_summary_prewarm_expected_disabled",
    )
    _require(baseline_overall_p95 is not None, failures, "baseline_missing_overall_p95")
    _require(baseline_hit_ratio is not None, failures, "baseline_missing_cache_hit_ratio")

    for payload, label in ((baseline, "baseline"), (prewarm, "prewarm")):
        total_requests = _int_field(payload, "requests", section="")
        distinct_allocations = _int_field(payload, "distinct_allocation_count")
        distinct_determinants = _int_field(payload, "distinct_cache_determinant_count")
        distinct_users = _int_field(payload, "distinct_user_count")
        max_per_determinant = _int_field(payload, "max_requests_per_determinant")
        duplicate_ratio = _float_field(payload, "duplicate_request_ratio")
        unique_ratio = _float_field(payload, "unique_determinant_ratio")
        configured_cold_requests = _int_field(payload, "configured_cold_request_count")
        cold_path_samples = (
            configured_cold_requests
            if configured_cold_requests is not None
            else _state_count(payload, "cold_path_generated")
        )
        _require(total_requests is not None, failures, f"{label}_missing_total_requests")
        _require(
            distinct_allocations is not None,
            failures,
            f"{label}_missing_distinct_allocation_count",
        )
        _require(
            distinct_determinants is not None,
            failures,
            f"{label}_missing_distinct_cache_determinant_count",
        )
        _require(distinct_users is not None, failures, f"{label}_missing_distinct_user_count")
        _require(
            max_per_determinant is not None,
            failures,
            f"{label}_missing_max_requests_per_determinant",
        )
        _require(
            duplicate_ratio is not None,
            failures,
            f"{label}_missing_duplicate_request_ratio",
        )
        _require(
            unique_ratio is not None,
            failures,
            f"{label}_missing_unique_determinant_ratio",
        )
        if total_requests is not None:
            _require(
                total_requests >= min_total_requests,
                failures,
                f"{label}_total_requests_below_min:{total_requests}<{min_total_requests}",
            )
        _require(
            cold_path_samples >= min_cold_path_samples,
            failures,
            (
                f"{label}_configured_cold_request_count_below_min:"
                f"{cold_path_samples}<{min_cold_path_samples}"
            ),
        )
        if distinct_allocations is not None:
            _require(
                distinct_allocations >= min_distinct_allocations,
                failures,
                (
                    f"{label}_distinct_allocation_count_below_min:"
                    f"{distinct_allocations}<{min_distinct_allocations}"
                ),
            )
        if distinct_determinants is not None:
            _require(
                distinct_determinants >= min_distinct_determinants,
                failures,
                (
                    f"{label}_distinct_cache_determinant_count_below_min:"
                    f"{distinct_determinants}<{min_distinct_determinants}"
                ),
            )
        if distinct_users is not None:
            _require(
                distinct_users >= min_distinct_users,
                failures,
                f"{label}_distinct_user_count_below_min:{distinct_users}<{min_distinct_users}",
            )
        if max_per_determinant is not None:
            _require(
                max_per_determinant <= max_requests_per_determinant,
                failures,
                (
                    f"{label}_max_requests_per_determinant_above_max:"
                    f"{max_per_determinant}>{max_requests_per_determinant}"
                ),
            )
        if duplicate_ratio is not None:
            _require(
                duplicate_ratio <= max_duplicate_request_ratio,
                failures,
                (
                    f"{label}_duplicate_request_ratio_above_max:"
                    f"{duplicate_ratio:.4f}>{max_duplicate_request_ratio:.4f}"
                ),
            )
        if unique_ratio is not None:
            _require(
                unique_ratio >= min_unique_determinant_ratio,
                failures,
                (
                    f"{label}_unique_determinant_ratio_below_min:"
                    f"{unique_ratio:.4f}<{min_unique_determinant_ratio:.4f}"
                ),
            )

    _require(
        prewarm_assisted_hits > 0,
        failures,
        "prewarm_efficacy_missing_assisted_cache_hits",
    )
    _require(
        prewarm_warm_hits >= baseline_warm_hits,
        failures,
        "prewarm_efficacy_no_warm_cache_gain",
    )

    efficacy_overall_latency = (
        baseline_overall_p95 is not None
        and prewarm_overall_p95 is not None
        and prewarm_overall_p95 < baseline_overall_p95
    )
    efficacy_cache_ratio = (
        baseline_hit_ratio is not None
        and prewarm_hit_ratio is not None
        and prewarm_hit_ratio > baseline_hit_ratio
    )
    _require(
        efficacy_overall_latency,
        failures,
        "prewarm_efficacy_no_comparative_overall_p95_improvement",
    )
    _require(
        efficacy_cache_ratio,
        failures,
        "prewarm_efficacy_no_comparative_cache_hit_improvement",
    )

    return (1 if failures else 0), failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.7-P6 benchmark adjudication enforcer")
    parser.add_argument("--baseline-file", required=True)
    parser.add_argument("--prewarm-file", required=True)
    parser.add_argument("--overall-p95-max-ms", type=float, default=500.0)
    parser.add_argument("--cache-hit-ratio-min", type=float, default=0.60)
    parser.add_argument("--provider-delay-min-ms", type=float, default=50.0)
    parser.add_argument(
        "--latency-model-file",
        default="contracts-internal/governance/b17_p6_benchmark_latency_model.main.json",
    )
    parser.add_argument("--min-total-requests", type=int, default=100)
    parser.add_argument("--min-cold-path-samples", type=int, default=30)
    parser.add_argument("--min-distinct-allocations", type=int, default=10)
    parser.add_argument("--min-distinct-determinants", type=int, default=50)
    parser.add_argument("--min-distinct-users", type=int, default=25)
    parser.add_argument("--max-requests-per-determinant", type=int, default=4)
    parser.add_argument("--max-duplicate-request-ratio", type=float, default=0.50)
    parser.add_argument("--min-unique-determinant-ratio", type=float, default=0.50)
    args = parser.parse_args(argv[1:])

    baseline_path = Path(args.baseline_file).resolve()
    prewarm_path = Path(args.prewarm_file).resolve()
    latency_model_path = Path(args.latency_model_file).resolve()
    for required in (baseline_path, prewarm_path, latency_model_path):
        if not required.exists():
            sys.stdout.write(
                "b17_p6_benchmark_adjudication\n"
                "result=FAIL\n"
                f"missing_file:{required}\n"
            )
            return 1

    baseline = _load_json(baseline_path)
    prewarm = _load_json(prewarm_path)
    try:
        latency_model = _load_latency_model(latency_model_path)
    except ValueError as exc:
        sys.stdout.write(
            "b17_p6_benchmark_adjudication\n"
            "result=FAIL\n"
            f"{exc}\n"
        )
        return 1
    status, failures = _adjudicate(
        baseline=baseline,
        prewarm=prewarm,
        overall_p95_max_ms=float(args.overall_p95_max_ms),
        cache_hit_ratio_min=float(args.cache_hit_ratio_min),
        provider_delay_min_ms=float(args.provider_delay_min_ms),
        latency_model_provider_delay_ms=int(latency_model["provider_delay_ms"]),
        latency_model_min_provider_delay_ms=int(latency_model["minimum_provider_delay_ms"]),
        min_total_requests=int(args.min_total_requests),
        min_cold_path_samples=int(args.min_cold_path_samples),
        min_distinct_allocations=int(args.min_distinct_allocations),
        min_distinct_determinants=int(args.min_distinct_determinants),
        min_distinct_users=int(args.min_distinct_users),
        max_requests_per_determinant=int(args.max_requests_per_determinant),
        max_duplicate_request_ratio=float(args.max_duplicate_request_ratio),
        min_unique_determinant_ratio=float(args.min_unique_determinant_ratio),
    )
    lines = ["b17_p6_benchmark_adjudication"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(failures)
    else:
        lines.append("result=PASS")
        lines.append("adjudication=overall_p95_cache_hit_warm_cold_prewarm_efficacy_closed")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
