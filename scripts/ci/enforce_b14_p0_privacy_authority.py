#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CONTEXTS = (
    "B1.4 P0 Privacy Authority Lock",
    "Contract Semantic Drift Gate",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.4-P0 privacy authority lock enforcement")
    parser.add_argument(
        "--authority-artifact",
        default="contracts-internal/governance/b14_p0_privacy_authority.main.json",
    )
    parser.add_argument(
        "--workflow-file",
        default=".github/workflows/ci.yml",
    )
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--event-service-file",
        default="backend/app/ingestion/event_service.py",
    )
    parser.add_argument(
        "--webhooks-file",
        default="backend/app/api/webhooks.py",
    )
    parser.add_argument(
        "--maintenance-file",
        default="backend/app/tasks/maintenance.py",
    )
    parser.add_argument(
        "--privacy-task-file",
        default="backend/app/tasks/privacy.py",
    )
    parser.add_argument(
        "--privacy-module-file",
        default="backend/app/privacy/authority.py",
    )
    parser.add_argument(
        "--migration-file",
        default="alembic/versions/007_skeldir_foundation/202603141700_b14_p0_event_payload_authority_lock.py",
    )
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    args = _parse_args()

    authority_path = Path(args.authority_artifact)
    workflow_path = Path(args.workflow_file)
    checks_path = Path(args.required_checks_contract)
    event_service_path = Path(args.event_service_file)
    webhooks_path = Path(args.webhooks_file)
    maintenance_path = Path(args.maintenance_file)
    privacy_task_path = Path(args.privacy_task_file)
    privacy_module_path = Path(args.privacy_module_file)
    migration_path = Path(args.migration_file)

    files = (
        authority_path,
        workflow_path,
        checks_path,
        event_service_path,
        webhooks_path,
        maintenance_path,
        privacy_task_path,
        privacy_module_path,
        migration_path,
    )
    missing = [path for path in files if not path.exists()]
    if missing:
        print("B1.4-P0 privacy authority lock failed:")
        for path in missing:
            print(f"  - file not found: {path}")
        return 1

    authority = _load_json(authority_path)
    workflow_text = _read_text(workflow_path)
    checks_contract = _load_json(checks_path)
    event_service_text = _read_text(event_service_path)
    webhooks_text = _read_text(webhooks_path)
    maintenance_text = _read_text(maintenance_path)
    privacy_task_text = _read_text(privacy_task_path)
    privacy_module_text = _read_text(privacy_module_path)
    migration_text = _read_text(migration_path)

    errors: list[str] = []

    _require(authority.get("status") == "authoritative", "authority.status must be 'authoritative'", errors)
    _require(
        isinstance(authority.get("banned_direct_identifier_keys"), list)
        and len(authority["banned_direct_identifier_keys"]) > 0,
        "authority.banned_direct_identifier_keys must be a non-empty list",
        errors,
    )
    _require(
        isinstance(authority.get("banned_proxy_identifier_keys"), list)
        and len(authority["banned_proxy_identifier_keys"]) > 0,
        "authority.banned_proxy_identifier_keys must be a non-empty list",
        errors,
    )

    lifecycle = authority.get("event_lifecycle", {})
    durable_store = lifecycle.get("durable_store", {})
    session_boundary = lifecycle.get("session_boundary", {})
    deletion_contract = authority.get("deletion_contract", {})
    export_contract = authority.get("export_contract", {})
    log_contract = authority.get("log_artifact_no_leak", {})

    _require(
        isinstance(durable_store.get("payload_allowlist_keys"), list)
        and len(durable_store["payload_allowlist_keys"]) > 0,
        "event_lifecycle.durable_store.payload_allowlist_keys must be non-empty",
        errors,
    )
    _require(
        isinstance(durable_store.get("payload_forbidden_keys"), list)
        and len(durable_store["payload_forbidden_keys"]) > 0,
        "event_lifecycle.durable_store.payload_forbidden_keys must be non-empty",
        errors,
    )
    _require(
        session_boundary.get("derivation") == "uuid4_nondeterministic",
        "session_boundary.derivation must be uuid4_nondeterministic",
        errors,
    )
    _require(
        int(session_boundary.get("max_duration_minutes", 0)) <= 30,
        "session_boundary.max_duration_minutes must be <= 30",
        errors,
    )
    _require(
        deletion_contract.get("exposure_model") == "internal_control_plane_worker",
        "deletion_contract.exposure_model must be internal_control_plane_worker",
        errors,
    )
    _require(
        deletion_contract.get("public_api_exposed") is False,
        "deletion_contract.public_api_exposed must be false",
        errors,
    )
    _require(
        deletion_contract.get("authority_task_name") == "app.tasks.privacy.erase_tenant_privacy_surfaces",
        "deletion_contract.authority_task_name must match privacy worker task",
        errors,
    )
    _require(
        isinstance(export_contract.get("allowed_fields"), list) and len(export_contract["allowed_fields"]) > 0,
        "export_contract.allowed_fields must be non-empty",
        errors,
    )
    _require(
        isinstance(log_contract.get("forbidden_keys"), list) and len(log_contract["forbidden_keys"]) > 0,
        "log_artifact_no_leak.forbidden_keys must be non-empty",
        errors,
    )

    _require(
        "minimize_event_payload_for_storage" in event_service_text
        and "raw_payload=durable_payload" in event_service_text,
        "event_service must store minimized durable payload",
        errors,
    )
    _require(
        "generate_privacy_session_id" in webhooks_text,
        "webhooks must consume generate_privacy_session_id",
        errors,
    )
    _require(
        "uuid5(NAMESPACE_URL, f\"stripe:" not in webhooks_text
        and "uuid5(NAMESPACE_URL, f\"shopify:" not in webhooks_text
        and "uuid5(NAMESPACE_URL, f\"paypal:" not in webhooks_text
        and "uuid5(NAMESPACE_URL, f\"woocommerce:" not in webhooks_text,
        "webhooks must not derive session ids deterministically from provider ids",
        errors,
    )
    _require(
        "dead_events_payload_redacted" in maintenance_text
        and "dead_events_quarantine_payload_redacted" in maintenance_text,
        "maintenance retention must redact old raw payload envelopes",
        errors,
    )
    _require(
        "app.tasks.privacy.erase_tenant_privacy_surfaces" in privacy_task_text,
        "privacy task module must expose authority-controlled erasure task",
        errors,
    )
    _require(
        "_AUTHORITY_PATH" in privacy_module_text
        and "b14_p0_privacy_authority.main.json" in privacy_module_text,
        "privacy runtime module must load the canonical authority artifact",
        errors,
    )
    _require(
        "fn_guard_attribution_events_payload_identity" in migration_text
        and "trg_guard_attribution_events_payload_identity" in migration_text,
        "migration must install payload authority trigger",
        errors,
    )

    for context in REQUIRED_CONTEXTS:
        _require(context in workflow_text, f"workflow missing required context: {context}", errors)

    required_contexts = checks_contract.get("required_contexts")
    _require(isinstance(required_contexts, list), "required checks contract missing required_contexts list", errors)
    if isinstance(required_contexts, list):
        for context in REQUIRED_CONTEXTS:
            _require(context in required_contexts, f"required checks contract missing context: {context}", errors)

    _require(
        "pytest tests/contract/test_contract_semantics.py -q" in workflow_text,
        "workflow must contain merge-blocking contract semantic drift test command",
        errors,
    )

    if errors:
        print("B1.4-P0 privacy authority lock failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.4-P0 privacy authority lock passed.")
    print(f"  authority={authority_path}")
    print(f"  migration={migration_path}")
    print(f"  required_contexts={', '.join(REQUIRED_CONTEXTS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

