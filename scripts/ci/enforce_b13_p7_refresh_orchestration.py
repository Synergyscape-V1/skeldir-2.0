#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_CONTEXT = "B1.3 P7 Refresh Orchestration Proofs"
REQUIRED_TASK_NAMES = (
    "schedule_provider_oauth_refresh_all_tenants",
    "schedule_provider_oauth_refresh_for_tenant",
    "refresh_provider_oauth_credential",
)
REQUIRED_TASK_FULL_NAMES = (
    "app.tasks.maintenance.schedule_provider_oauth_refresh_for_tenant",
    "app.tasks.maintenance.refresh_provider_oauth_credential",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P7 refresh orchestration enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--maintenance-task-file", default="backend/app/tasks/maintenance.py")
    parser.add_argument("--beat-schedule-file", default="backend/app/tasks/beat_schedule.py")
    parser.add_argument("--enqueue-file", default="backend/app/tasks/enqueue.py")
    parser.add_argument("--refresh-service-file", default="backend/app/services/provider_token_refresh.py")
    parser.add_argument("--token-resolver-file", default="backend/app/services/provider_valid_token_resolution.py")
    parser.add_argument("--provider-runtime-file", default="backend/app/services/provider_oauth_runtime.py")
    parser.add_argument("--realtime-provider-file", default="backend/app/services/realtime_revenue_providers.py")
    parser.add_argument("--celery-app-file", default="backend/app/celery_app.py")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "maintenance": Path(args.maintenance_task_file),
        "beat": Path(args.beat_schedule_file),
        "enqueue": Path(args.enqueue_file),
        "refresh_service": Path(args.refresh_service_file),
        "token_resolver": Path(args.token_resolver_file),
        "provider_runtime": Path(args.provider_runtime_file),
        "realtime_provider": Path(args.realtime_provider_file),
        "celery_app": Path(args.celery_app_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P7 refresh orchestration gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    checks_contract = _load_json(paths["required_checks"])
    maintenance_text = _read_text(paths["maintenance"])
    beat_text = _read_text(paths["beat"])
    enqueue_text = _read_text(paths["enqueue"])
    refresh_service_text = _read_text(paths["refresh_service"])
    token_resolver_text = _read_text(paths["token_resolver"])
    provider_runtime_text = _read_text(paths["provider_runtime"])
    realtime_provider_text = _read_text(paths["realtime_provider"])
    celery_app_text = _read_text(paths["celery_app"])

    errors: list[str] = []

    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = checks_contract.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
    elif REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")

    for task_name in REQUIRED_TASK_NAMES:
        if f"def {task_name}(" not in maintenance_text:
            errors.append(f"maintenance task file missing function: {task_name}")
    for full_name in REQUIRED_TASK_FULL_NAMES:
        if full_name not in enqueue_text:
            errors.append(f"tenant enqueue registry missing task name: {full_name}")

    if "provider-oauth-refresh-orchestration" not in beat_text:
        errors.append("beat schedule missing provider oauth refresh orchestration entry")
    if "schedule_provider_oauth_refresh_all_tenants" not in beat_text:
        errors.append("beat schedule missing global provider refresh task binding")

    if "ProviderValidTokenResolver" not in realtime_provider_text:
        errors.append("realtime revenue provider path missing ProviderValidTokenResolver usage")
    if "PlatformCredentialService.get_credentials(" in realtime_provider_text:
        errors.append("realtime revenue provider path must not bypass canonical valid-token resolver")
    if "self._dispatcher.refresh_token(" in provider_runtime_text:
        errors.append("runtime lifecycle service must not perform inline refresh in request path")

    required_refresh_service_fragments = (
        "pg_try_advisory_xact_lock",
        "runtime_dispatcher.refresh_token(",
        "PlatformCredentialStore.mark_refresh_success(",
        "PlatformCredentialStore.record_refresh_failure(",
        "PlatformCredentialStore.mark_revoked(",
    )
    for fragment in required_refresh_service_fragments:
        if fragment not in refresh_service_text:
            errors.append(f"refresh orchestration service missing fragment: {fragment}")

    required_resolver_fragments = (
        "claim_refresh_window",
        "enqueue_tenant_task_by_name",
        "app.tasks.maintenance.refresh_provider_oauth_credential",
    )
    for fragment in required_resolver_fragments:
        if fragment not in token_resolver_text:
            errors.append(f"valid-token resolver missing fragment: {fragment}")

    if "assert_no_sensitive_material(task_kwargs" not in enqueue_text:
        errors.append("enqueue choke-point missing structural sensitive-material guard")
    if "sanitize_for_transport" not in celery_app_text:
        errors.append("celery task failure serialization missing sanitize_for_transport")
    if "redact_text_fragments" not in celery_app_text:
        errors.append("celery task failure serialization missing redact_text_fragments")

    if errors:
        print("B1.3-P7 refresh orchestration gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P7 refresh orchestration gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print("  canonical_valid_token_path=ProviderValidTokenResolver")
    print("  orchestration=beat -> tenant scheduler -> credential refresh task")
    print("  single_flight=advisory_xact_lock")
    print("  failure_policy=terminal_revocation + transient_backoff")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
