#!/usr/bin/env python3
"""Compare the P2 candidate scope authority with the production image bytes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))


def _run(*command: str) -> str:
    return subprocess.run(
        command,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


_P2_IN_IMAGE_PROBE = r"""
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

report = {}

from app.finance_reconciliation.scope_authority import (
    B26_P2_SCOPE_POLICY_VERSION,
    classify_candidate,
    load_b26_p2_scope_policy,
    normalize_provider_set,
    scope_policy_identity,
)

identity = scope_policy_identity()
report["policy_version_ok"] = identity.scope_policy_version == B26_P2_SCOPE_POLICY_VERSION
report["policy_phase_ok"] = identity.phase == "B2.6-P2"
document = load_b26_p2_scope_policy()
report["contract_pin_ok"] = document.get("module_ast_sha256") is not None
report["corrective_law_ok"] = (
    document.get("refusal_representation")
    == "exception_fail_closed_never_returned_disposition"
    and document.get("rail_authority")
    == "p2_design_partner_maturity_definition_delegated_by_p1_unsupported_rail_doctrine"
    and document.get("exclusion_priority_authority")
    == "p2_governed_deterministic_priority_versioned"
)
report["corrective_ii_law_ok"] = (
    document.get("money_semantics") == "source_verified_gross_not_canonical_net"
    and document.get("money_authority") == "b2.2_ingress_verified_amount_minor"
    and document.get("canonical_net_authority")
    == "b2.3_match_verdicts.canonical_net_verified_amount_minor_only"
    and document.get("snapshot_isolation")
    == "repeatable_read_single_snapshot_per_derivation"
    and document.get("dispatch_authority_law")
    == "worker_admits_via_constrained_resolver_before_b23_fail_closed"
    and document.get("window_authority")
    == "dispatch_bound_ingress_event_day_half_open_utc"
    and document.get("identity_law")
    == "semantically_complete_scope_identity_v3_binds_provider_rail_currency_policy_semantic_sha_money_labels_source_bytes_excluded"
    and document.get("identity_version") == "b2.6-p2-scope-identity-v3"
    and document.get("provenance_law")
    == "policy_source_bytes_are_provenance_evidence_never_scope_semantics"
    and document.get("delivery_law")
    == "acceptance_acquires_durable_recoverable_execution_intent_atomically"
)
report["corrective_iii_law_ok"] = (
    document.get("window_oracle_law")
    == "independent_normative_oracle_pins_utc_day_half_open_without_importing_production_quantizer"
    and document.get("supersession", {}).get("supersedes")
    == "b2.6-p2-scope-policy-v1"
)
report["dispositions_ok"] = set(document.get("dispositions", [])) == {
    "SUPPORTED_AND_IN_SCOPE",
    "SUPPORTED_BUT_UNRESOLVED",
    "EXPLICITLY_EXCLUDED",
    "INVALID_OR_REFUSED",
}

ws = datetime(2026, 1, 1, tzinfo=timezone.utc)
we = datetime(2026, 2, 1, tzinfo=timezone.utc)
occ = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
tenant = UUID("11111111-2222-3333-4444-555555555555")
ver = B26_P2_SCOPE_POLICY_VERSION

def classify(**over):
    base = {
        "tenant_id": tenant,
        "provider_raw": "stripe",
        "currency_raw": "USD",
        "event_time": occ,
        "window_start": ws,
        "window_end": we,
        "scope_policy_version": ver,
        "source_reference": "ord-1",
    }
    base.update(over)
    return classify_candidate(**base)

vectors_ok = True
if classify().disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(provider_raw="square").disposition != "EXPLICITLY_EXCLUDED":
    vectors_ok = False
if classify(currency_raw="EUR").reason != "unsupported_currency_excluded":
    vectors_ok = False
if classify(event_time=we).reason != "outside_governed_window_excluded":
    vectors_ok = False
if classify(event_time=ws).disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(event_time=we - timedelta(microseconds=1)).disposition != "SUPPORTED_AND_IN_SCOPE":
    vectors_ok = False
if classify(source_reference=None).disposition != "SUPPORTED_BUT_UNRESOLVED":
    vectors_ok = False
try:
    classify(tenant_id="bad")
except Exception:
    pass
else:
    vectors_ok = False
report["vectors_ok"] = vectors_ok
report["universe_ok"] = normalize_provider_set(None) == ("paypal", "shopify", "stripe", "woocommerce")

from app.finance_reconciliation.coverage_authority import _normalize_platforms
report["delegation_ok"] = _normalize_platforms(None) == normalize_provider_set(None)

sink_source = open("app/finance_reconciliation/canonical_sink.py", encoding="utf-8").read()
# Corrective X single authority: the sink observes aggregate coherence
# through the thin SQL-backed adapter.
report["wiring_ok"] = (
    "_p2_conduction.assert_aggregate_scope_supported_via_authority("
    in sink_source
)
report["conduction_wiring_ok"] = "derive_governed_scope(" in sink_source
report["conduction_observation_ok"] = "b26_p2_candidate_scope_derived" in sink_source

from app.finance_reconciliation import candidate_conduction as conduction
report["conduction_import_ok"] = (
    callable(conduction.derive_governed_scope)
    and callable(conduction.derive_single_candidate_scope)
)
from app.finance_reconciliation import conduction_state as conduction_v
report["corrective_v_conduction_state_ok"] = (
    callable(conduction_v.record_conduction_receipt)
    and callable(conduction_v.mark_conducted_via_gate)
    and callable(conduction_v.staleness_snapshot)
    and callable(conduction_v.staleness_threshold_seconds)
)
report["conduction_ii_ok"] = (
    conduction.P2_MONEY_SEMANTICS == "source_verified_gross_not_canonical_net"
    and conduction.P2_MONEY_AUTHORITY == "b2.2_ingress_verified_amount_minor"
    and "scope_identity" in conduction.CanonicalReconciliationScope.__dataclass_fields__
    and "snapshot_isolation" in conduction.CanonicalReconciliationScope.__dataclass_fields__
)
from app.finance_reconciliation import dispatch_authority as dispatch
report["dispatch_import_ok"] = (
    callable(dispatch.resolve_dispatch_authority)
    and callable(dispatch.derive_reconciliation_window)
    and callable(dispatch.admit_execution_before_b23)
)
from app.finance_reconciliation.tenant_authority import (
    open_governed_b23_snapshot_session,
)
report["snapshot_session_ok"] = callable(open_governed_b23_snapshot_session)
from app.core.day_window import quantize_utc_day_iso
report["shared_window_ok"] = callable(quantize_utc_day_iso)
webhook_source = open("app/api/webhooks.py", encoding="utf-8").read()
report["webhook_phase_ok"] = (
    "finance_reconciliation" not in webhook_source
    and "candidate_conduction" not in webhook_source
    and "p2_scope" not in webhook_source
    and "from app.core.day_window import" in webhook_source
    and "dispatch_task_id" in webhook_source
)
task_source = open("app/tasks/revenue_verification.py", encoding="utf-8").read()
report["task_conduction_ok"] = (
    "_derive_p2_scope_for_window(" in task_source and "p2_scope" in task_source
)
report["task_dispatch_ok"] = (
    "resolve_dispatch_authority(" in task_source
    and "broker_task_id" in task_source
    and "open_governed_b23_snapshot_session" in task_source
    and "p2_scope: Dict[str, Any] | None = None" not in task_source
)
report["corrective_iii_wiring_ok"] = (
    callable(getattr(dispatch, "admit_execution_before_b23", None))
    and "authority = run_in_worker_loop(_admit())" in task_source
    and "INSERT INTO public.b26_p2_execution_outbox (" in webhook_source
    and "INSERT INTO public.b26_p2_task_authority_directory (" in webhook_source
    and "relay_b26_p2_pending_dispatches"
    in open("app/tasks/b26_p2_relay.py", encoding="utf-8").read()
    and conduction.SCOPE_IDENTITY_VERSION == "b2.6-p2-scope-identity-v3"
    # Corrective X single authority: per-item provider/rail/currency are
    # bound from the authority-observed classification (thin adapter).
    and "classification.provider" in open(
        "app/finance_reconciliation/candidate_conduction.py", encoding="utf-8"
    ).read()
    and "classification.rail" in open(
        "app/finance_reconciliation/candidate_conduction.py", encoding="utf-8"
    ).read()
)
from app.tasks.beat_schedule import build_beat_schedule
_beat = build_beat_schedule()
report["corrective_iv_recovery_motor_ok"] = (
    "b26-p2-relay-sweep" in _beat
    and _beat["b26-p2-relay-sweep"]["task"]
    == "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches"
    and _beat["b26-p2-relay-sweep"]["options"]["queue"] == "b26_p2_relay"
)
report["corrective_iv_relay_role_ok"] = (
    "if role == _BAYESIAN_WORKER_ROLE_P2_RELAY:"
    in open("app/tasks/bayesian.py", encoding="utf-8").read()
)
report["corrective_iv_conducted_ok"] = (
    "mark_conducted_via_gate" in task_source
    and "record_conduction_receipt" in task_source
    and "SET state = 'conducted'" not in task_source
    and "delivery_state = 'conducted'" not in task_source
)
report["corrective_iv_beat_healer_ok"] = (
    "class HealingBeatScheduler" in open("app/celery_beat.py", encoding="utf-8").read()
    and 'beat_scheduler = "app.celery_beat:HealingBeatScheduler"'
    in open("app/celery_app.py", encoding="utf-8").read()
    and "def reset_broker_pools_after_fault" in open("app/celery_app.py", encoding="utf-8").read()
    and 'reset_broker_pools_after_fault(reason="relay_publish")'
    in open("app/tasks/b26_p2_relay.py", encoding="utf-8").read()
)
report["corrective_iv_semantic_identity_ok"] = (
    'str(policy_source_sha256 or "")' not in open(
        "app/finance_reconciliation/candidate_conduction.py", encoding="utf-8"
    ).read()
)

print("P2_IN_IMAGE_BATTERY " + json.dumps(report, sort_keys=True))
"""


def _in_image_p2_battery(image: str) -> dict[str, object]:
    proc = subprocess.run(
        ["docker", "run", "--rm", "-i", image, "python", "-"],
        input=_P2_IN_IMAGE_PROBE,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"container_p2_battery_failed:{proc.stderr[-800:]}")
    line = next(
        (
            ln
            for ln in proc.stdout.splitlines()
            if ln.startswith("P2_IN_IMAGE_BATTERY ")
        ),
        None,
    )
    if line is None:
        raise RuntimeError(f"container_p2_battery_output_missing:{proc.stdout[-400:]}")
    report = json.loads(line[len("P2_IN_IMAGE_BATTERY ") :])
    failed = sorted(k for k, v in report.items() if v is not True)
    if failed:
        raise RuntimeError(f"container_p2_battery_red:{failed}")
    return report


def validate(image: str) -> dict[str, object]:
    sys.path.insert(0, str(BACKEND))
    from app.finance_reconciliation.scope_authority import (  # noqa: PLC0415
        scope_policy_identity,
    )

    host = scope_policy_identity().__dict__
    probe = (
        "import json;"
        "from app.finance_reconciliation.scope_authority import scope_policy_identity;"
        "print(json.dumps(scope_policy_identity().__dict__,sort_keys=True))"
    )
    output = _run("docker", "run", "--rm", image, "python", "-c", probe)
    try:
        container = json.loads(output.splitlines()[-1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"container_p2_identity_malformed:{output}") from exc
    if container != host:
        raise RuntimeError(
            f"container_p2_identity_mismatch:host={host}:container={container}"
        )
    battery = _in_image_p2_battery(image)
    inspect = json.loads(_run("docker", "image", "inspect", image))[0]
    return {
        "image": image,
        "image_id": inspect["Id"],
        "host_scope_policy_identity": host,
        "container_scope_policy_identity": container,
        "container_p2_battery": battery,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    parser.add_argument("--evidence-out", type=Path)
    args = parser.parse_args()
    try:
        details = validate(args.image)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"B26_P2_CONTAINER_EQUIVALENCE_FAIL {exc}")
        return 1
    if args.evidence_out:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_out,
            gate_id="B26-P2-G9-PRODUCTION-ARTIFACT-EQUIVALENCE",
            producer="b26-p2-container-equivalence",
            scenario_id="candidate-production-image",
            falsifier_id="p2-stale-artifact-substitution",
            details=details,
        )
    print("B26_P2_CONTAINER_EQUIVALENCE_PASS")
    print(json.dumps(details, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
