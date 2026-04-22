#!/usr/bin/env python3
"""B2.2-P5 webhook benchmark adjudication enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


MOUNTED_ROUTES = {
    "/api/webhooks/shopify/order_create",
    "/api/webhooks/stripe/payment_intent_succeeded",
    "/api/webhooks/stripe/payment_intent/succeeded",
    "/api/webhooks/paypal/sale_completed",
    "/api/webhooks/woocommerce/order_completed",
}
STRIPE_CANONICAL_ROUTE = "/api/webhooks/stripe/payment_intent_succeeded"
STRIPE_ALIAS_ROUTE = "/api/webhooks/stripe/payment_intent/succeeded"
SCHEMA_VERSION = "b22_p5_webhook_ingress_benchmark.v1"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _require(condition: bool, failures: list[str], message: str) -> None:
    if not condition:
        failures.append(message)


def _validate_payload(
    *,
    payload: dict[str, Any],
    threshold_ms: float,
    max_alias_delta_ms: float,
) -> tuple[int, list[str]]:
    failures: list[str] = []
    _require(
        payload.get("schema_version") == SCHEMA_VERSION,
        failures,
        "schema_version_mismatch",
    )
    _require(payload.get("phase") == "B2.2-P5", failures, "phase_mismatch")
    _require(payload.get("mode") == "measure", failures, "mode_not_measure")
    _require(
        payload.get("timing_boundary") == "mounted_http_request_to_ack_response",
        failures,
        "timing_boundary_invalid",
    )
    _require(
        str(payload.get("result", "")) == "PASS", failures, "benchmark_harness_not_pass"
    )
    _require(
        payload.get("task_always_eager") is False, failures, "task_always_eager_enabled"
    )

    mounted_routes = payload.get("mounted_routes")
    if not isinstance(mounted_routes, list):
        failures.append("mounted_routes_invalid")
    else:
        route_set = {str(item).strip() for item in mounted_routes}
        _require(route_set == MOUNTED_ROUTES, failures, "mounted_routes_mismatch")

    component_integrity = payload.get("component_integrity")
    if not isinstance(component_integrity, dict):
        failures.append("component_integrity_invalid")
    else:
        _require(
            component_integrity.get("passes") is True,
            failures,
            "component_integrity_failed",
        )
        violations = component_integrity.get("violations")
        if isinstance(violations, list):
            _require(
                len(violations) == 0, failures, "component_integrity_violations_present"
            )
        else:
            failures.append("component_integrity_violations_invalid")

    integrity_probe = payload.get("integrity_probe")
    if not isinstance(integrity_probe, dict):
        failures.append("integrity_probe_invalid")
    else:
        _require(
            _int(integrity_probe.get("forged_signature_http_status")) == 401,
            failures,
            "integrity_probe_forged_signature_not_401",
        )
        _require(
            integrity_probe.get("duplicate_replay_event_id_stable") is True,
            failures,
            "integrity_probe_duplicate_stability_missing",
        )
        unsupported_cases = integrity_probe.get("unsupported_event_family_cases")
        if not isinstance(unsupported_cases, dict):
            failures.append("integrity_probe_unsupported_cases_invalid")
        else:
            _require(
                set(unsupported_cases.keys()) == MOUNTED_ROUTES,
                failures,
                "integrity_probe_unsupported_case_routes_mismatch",
            )
            for route, case_payload in unsupported_cases.items():
                if not isinstance(case_payload, dict):
                    failures.append(f"integrity_probe_unsupported_case_invalid:{route}")
                    continue
                _require(
                    _int(case_payload.get("http_status")) == 200,
                    failures,
                    f"integrity_probe_unsupported_http_not_200:{route}",
                )
                _require(
                    str(case_payload.get("status"))
                    == "unsupported_event_family_ignored",
                    failures,
                    f"integrity_probe_unsupported_status_invalid:{route}",
                )
                _require(
                    str(case_payload.get("error")) == "unsupported_event_family",
                    failures,
                    f"integrity_probe_unsupported_error_invalid:{route}",
                )

    persistence = payload.get("persistence_counts")
    if not isinstance(persistence, dict):
        failures.append("persistence_counts_invalid")
    else:
        for required_counter in (
            "attribution_events",
            "webhook_ingress_identities",
            "raw_event_payloads",
        ):
            count_value = _int(persistence.get(required_counter))
            _require(
                count_value is not None,
                failures,
                f"persistence_counter_missing:{required_counter}",
            )
            if count_value is not None:
                _require(
                    count_value > 0,
                    failures,
                    f"persistence_counter_not_positive:{required_counter}",
                )
        _require(
            _int(persistence.get("latest_raw_payload_minimized")) == 1,
            failures,
            "post_auth_minimization_not_proven",
        )

    latency = payload.get("latency")
    if not isinstance(latency, dict):
        failures.append("latency_payload_invalid")
        return 1, failures

    sample_count = _int(latency.get("sample_count"))
    success_count = _int(latency.get("success_count"))
    p95_ms = _float(latency.get("p95_ms"))
    _require(
        sample_count is not None and sample_count > 0,
        failures,
        "latency_sample_count_invalid",
    )
    _require(
        success_count is not None and success_count == sample_count,
        failures,
        "latency_success_count_mismatch",
    )
    _require(p95_ms is not None, failures, "latency_p95_missing")
    if p95_ms is not None:
        _require(
            p95_ms <= threshold_ms,
            failures,
            f"p95_threshold_exceeded:{p95_ms}>{threshold_ms}",
        )

    per_route = latency.get("per_route")
    if not isinstance(per_route, dict):
        failures.append("latency_per_route_invalid")
        return 1, failures
    _require(
        set(per_route.keys()) == MOUNTED_ROUTES,
        failures,
        "latency_per_route_routes_mismatch",
    )
    for route, route_payload in per_route.items():
        if not isinstance(route_payload, dict):
            failures.append(f"latency_per_route_payload_invalid:{route}")
            continue
        route_p95 = _float(route_payload.get("p95_ms"))
        route_count = _int(route_payload.get("count"))
        _require(
            route_p95 is not None, failures, f"latency_per_route_p95_missing:{route}"
        )
        _require(
            route_count is not None and route_count > 0,
            failures,
            f"latency_per_route_count_invalid:{route}",
        )

    canonical_p95 = _float((per_route.get(STRIPE_CANONICAL_ROUTE) or {}).get("p95_ms"))
    alias_p95 = _float((per_route.get(STRIPE_ALIAS_ROUTE) or {}).get("p95_ms"))
    _require(canonical_p95 is not None, failures, "stripe_canonical_p95_missing")
    _require(alias_p95 is not None, failures, "stripe_alias_p95_missing")
    if canonical_p95 is not None and alias_p95 is not None:
        delta = abs(alias_p95 - canonical_p95)
        _require(
            delta <= max_alias_delta_ms,
            failures,
            f"stripe_alias_canonical_p95_delta_exceeded:{delta}>{max_alias_delta_ms}",
        )

    return (1 if failures else 0), failures


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="B2.2-P5 webhook benchmark adjudication"
    )
    parser.add_argument("--measure-file", required=True)
    parser.add_argument("--threshold-ms", type=float, default=500.0)
    parser.add_argument("--max-stripe-alias-delta-ms", type=float, default=75.0)
    args = parser.parse_args(argv[1:])

    measure_path = Path(args.measure_file).resolve()
    if not measure_path.exists():
        sys.stdout.write(
            "b22_p5_webhook_benchmark_adjudication\n"
            "result=FAIL\n"
            f"missing_file:{measure_path}\n"
        )
        return 1

    payload = _load_json(measure_path)
    status, failures = _validate_payload(
        payload=payload,
        threshold_ms=float(args.threshold_ms),
        max_alias_delta_ms=float(args.max_stripe_alias_delta_ms),
    )
    lines = ["b22_p5_webhook_benchmark_adjudication"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(failures)
    else:
        lines.append("result=PASS")
        lines.append(
            "adjudication=mounted_composed_path_latency_and_alias_parity_closed"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
