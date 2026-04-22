from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _script_path() -> Path:
    return (
        _repo_root()
        / "scripts"
        / "ci"
        / "enforce_b22_p5_webhook_benchmark_adjudication.py"
    )


def _run_enforcer(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_script_path()), *args],
        cwd=_repo_root(),
        check=False,
        capture_output=True,
        text=True,
    )


def _base_payload(
    *, p95_ms: float, canonical_p95_ms: float, alias_p95_ms: float
) -> dict[str, Any]:
    mounted_routes = [
        "/api/webhooks/shopify/order_create",
        "/api/webhooks/stripe/payment_intent_succeeded",
        "/api/webhooks/stripe/payment_intent/succeeded",
        "/api/webhooks/paypal/sale_completed",
        "/api/webhooks/woocommerce/order_completed",
    ]
    unsupported_cases = {
        route: {
            "http_status": 200,
            "status": "unsupported_event_family_ignored",
            "error": "unsupported_event_family",
        }
        for route in mounted_routes
    }
    per_route = {
        "/api/webhooks/shopify/order_create": {"count": 25, "p95_ms": 280.0},
        "/api/webhooks/stripe/payment_intent_succeeded": {
            "count": 25,
            "p95_ms": canonical_p95_ms,
        },
        "/api/webhooks/stripe/payment_intent/succeeded": {
            "count": 25,
            "p95_ms": alias_p95_ms,
        },
        "/api/webhooks/paypal/sale_completed": {"count": 25, "p95_ms": 300.0},
        "/api/webhooks/woocommerce/order_completed": {"count": 25, "p95_ms": 275.0},
    }
    return {
        "schema_version": "b22_p5_webhook_ingress_benchmark.v1",
        "phase": "B2.2-P5",
        "mode": "measure",
        "result": "PASS",
        "timing_boundary": "mounted_http_request_to_ack_response",
        "mounted_routes": mounted_routes,
        "task_always_eager": False,
        "component_integrity": {"passes": True, "violations": []},
        "integrity_probe": {
            "forged_signature_http_status": 401,
            "duplicate_replay_event_id_stable": True,
            "unsupported_event_family_cases": unsupported_cases,
        },
        "persistence_counts": {
            "attribution_events": 12,
            "webhook_ingress_identities": 12,
            "raw_event_payloads": 12,
            "latest_raw_payload_minimized": 1,
        },
        "latency": {
            "sample_count": 125,
            "success_count": 125,
            "p95_ms": p95_ms,
            "per_route": per_route,
        },
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_b22_p5_webhook_benchmark_adjudication_passes_with_valid_payload(
    tmp_path: Path,
) -> None:
    measure_file = tmp_path / "measure.json"
    _write(
        measure_file,
        _base_payload(p95_ms=320.0, canonical_p95_ms=290.0, alias_p95_ms=315.0),
    )

    result = _run_enforcer("--measure-file", str(measure_file))
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    assert "result=PASS" in result.stdout


def test_b22_p5_webhook_benchmark_adjudication_fails_when_p95_regresses(
    tmp_path: Path,
) -> None:
    measure_file = tmp_path / "measure.slow.json"
    _write(
        measure_file,
        _base_payload(p95_ms=620.0, canonical_p95_ms=290.0, alias_p95_ms=315.0),
    )

    result = _run_enforcer("--measure-file", str(measure_file))
    assert result.returncode != 0
    assert "p95_threshold_exceeded" in (result.stdout + result.stderr)


def test_b22_p5_webhook_benchmark_adjudication_fails_when_alias_parity_regresses(
    tmp_path: Path,
) -> None:
    measure_file = tmp_path / "measure.alias-drift.json"
    _write(
        measure_file,
        _base_payload(p95_ms=320.0, canonical_p95_ms=220.0, alias_p95_ms=380.0),
    )

    result = _run_enforcer("--measure-file", str(measure_file))
    assert result.returncode != 0
    assert "stripe_alias_canonical_p95_delta_exceeded" in (
        result.stdout + result.stderr
    )


def test_b22_p5_webhook_benchmark_adjudication_fails_when_eager_cheat_present(
    tmp_path: Path,
) -> None:
    measure_file = tmp_path / "measure.eager.json"
    payload = _base_payload(p95_ms=320.0, canonical_p95_ms=290.0, alias_p95_ms=315.0)
    payload["task_always_eager"] = True
    _write(measure_file, payload)

    result = _run_enforcer("--measure-file", str(measure_file))
    assert result.returncode != 0
    assert "task_always_eager_enabled" in (result.stdout + result.stderr)


def test_b22_p5_webhook_benchmark_adjudication_fails_when_unsupported_family_semantics_missing(
    tmp_path: Path,
) -> None:
    measure_file = tmp_path / "measure.unsupported-regression.json"
    payload = _base_payload(p95_ms=320.0, canonical_p95_ms=290.0, alias_p95_ms=315.0)
    payload["integrity_probe"]["unsupported_event_family_cases"][
        "/api/webhooks/shopify/order_create"
    ]["status"] = "success"
    _write(measure_file, payload)

    result = _run_enforcer("--measure-file", str(measure_file))
    assert result.returncode != 0
    assert (
        "integrity_probe_unsupported_status_invalid:/api/webhooks/shopify/order_create"
        in (result.stdout + result.stderr)
    )
