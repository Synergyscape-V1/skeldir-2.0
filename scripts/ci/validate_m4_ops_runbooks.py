"""Validate M4 operational runbook authority and drift controls."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

RUNBOOKS = [
    "docs/ops/README.md",
    "docs/ops/dlq_inspection_and_replay.md",
    "docs/ops/celery_worker_diagnosis.md",
    "docs/ops/queue_topology.md",
    "docs/ops/rls_guc_verification.md",
    "docs/ops/webhook_replay.md",
    "docs/ops/b23_match_diagnosis.md",
    "docs/ops/common_failure_signatures.md",
]

REQUIRED_MAKE_TARGETS = [
    "validate-ops-runbooks",
    "ops-dlq-inspect",
    "ops-queues",
    "ops-worker-inspect",
    "ops-rls-check",
    "ops-b23-trace",
    "ops-webhook-replay-local",
    "ops-seed-diagnostics",
    "ops-clear-diagnostics",
    "ops-runtime-proof",
]

REQUIRED_SCRIPTS = [
    "scripts/ops/common.py",
    "scripts/ops/dlq_inspect.py",
    "scripts/ops/queue_topology.py",
    "scripts/ops/rls_check.py",
    "scripts/ops/b23_trace.py",
    "scripts/ops/webhook_replay_local.py",
    "scripts/ops/seed_diagnostics.py",
    "scripts/ops/clear_diagnostics.py",
    "scripts/ops/runtime_proof_harness.py",
]

ALLOWED_CONTEXTS = {
    "container_api",
    "container_worker",
    "container_postgres",
    "container_celery",
    "container_network_curl",
    "ci_static",
    "manual_production_diagnostic",
    "manual_local_host_debug",
}

ALLOWED_CLASSES = {
    "read_only_inspection",
    "local_fixture_replay",
    "duplicate_detection_probe",
    "manual_production_diagnostic",
    "forbidden_production_replay",
}

METADATA_KEYS = {
    "command",
    "execution_context",
    "command_class",
    "requires_seeded_fixture",
    "mutates_state",
    "tenant_scope_required",
    "idempotency_sensitive",
    "signature_sensitive",
}

FIXTURE_TOKENS = [
    "m4-dlq-positive",
    "m4-dlq-missing-control",
    "m4-b23-trace-positive",
    "m4-b23-unknown-control",
    "m4-rls-positive",
    "m4-rls-missing-context",
    "m4-rls-bare-select-isolation",
    "m4-webhook-valid",
    "m4-webhook-tampered",
    "m4-webhook-duplicate",
]

TABLE_TOKENS = [
    "worker_failed_jobs",
    "webhook_ingress_identities",
    "b23_match_task_dispatches",
    "b23_match_verdicts",
    "b23_exception_records",
    "b23_revenue_events",
    "attribution_events",
]

SYMPTOMS = [
    "failed task",
    "stuck queue",
    "worker offline",
    "missing match verdict",
    "webhook accepted but no downstream task",
    "webhook rejected",
    "tenant isolation concern",
    "RLS/GUC missing context",
    "duplicate idempotency issue",
    "DLQ row present",
    "pooler/transaction context issue",
]


def fail(message: str) -> None:
    print(f"M4_OPS_VALIDATION_FAIL: {message}")
    raise SystemExit(1)


def read(path: str) -> str:
    full = ROOT / path
    if not full.exists():
        fail(f"missing required path: {path}")
    return full.read_text(encoding="utf-8")


def metadata_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for match in re.finditer(r"```yaml\n(.*?)\n```", text, re.DOTALL):
        data: dict[str, str] = {}
        for raw_line in match.group(1).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip("\"'")
        if "command" in data or "execution_context" in data:
            blocks.append(data)
    return blocks


def validate_paths() -> None:
    for runbook in RUNBOOKS:
        read(runbook)
    for script in REQUIRED_SCRIPTS:
        read(script)
    read(".github/workflows/m4-operational-runbooks.yml")
    read("M4.1_Remediation_Completion_Record.md")


def validate_make_targets() -> None:
    makefile = read("Makefile")
    for target in REQUIRED_MAKE_TARGETS:
        if not re.search(rf"^{re.escape(target)}:", makefile, re.MULTILINE):
            fail(f"missing Make target: {target}")


def validate_metadata() -> None:
    for runbook in RUNBOOKS:
        text = read(runbook)
        blocks = metadata_blocks(text)
        if not blocks:
            fail(f"{runbook} has no command metadata")
        for block in blocks:
            missing = METADATA_KEYS - set(block)
            if missing:
                fail(f"{runbook} command metadata missing keys {sorted(missing)}")
            if block["execution_context"] not in ALLOWED_CONTEXTS:
                fail(f"{runbook} invalid execution_context {block['execution_context']}")
            if block["command_class"] not in ALLOWED_CLASSES:
                fail(f"{runbook} invalid command_class {block['command_class']}")
            for bool_key in (
                "requires_seeded_fixture",
                "tenant_scope_required",
                "idempotency_sensitive",
                "signature_sensitive",
            ):
                if block[bool_key] not in {"true", "false"}:
                    fail(f"{runbook} invalid boolean {bool_key}: {block[bool_key]}")
            if block["mutates_state"] not in {"false", "local_fixture_only", "manual_production"}:
                fail(f"{runbook} invalid mutates_state: {block['mutates_state']}")
            command = block["command"]
            if (
                command.startswith("make ")
                and command.split()[1] not in REQUIRED_MAKE_TARGETS
                and command.split()[1] not in {"worker", "logs", "health", "migrate"}
            ):
                fail(f"{runbook} references unregistered Make command: {command}")


def validate_host_native_drift() -> None:
    forbidden = [
        r"(?m)^```(?:bash|sh|shell)?\n\s*python scripts/ops/",
        r"(?m)^```(?:bash|sh|shell)?\n\s*psql\s",
        r"(?m)^```(?:bash|sh|shell)?\n\s*celery -A ",
        r"(?m)^```(?:bash|sh|shell)?\n\s*curl localhost",
    ]
    for runbook in RUNBOOKS:
        text = read(runbook)
        for pattern in forbidden:
            if re.search(pattern, text):
                fail(f"{runbook} contains host-native canonical command drift")


def queue_names() -> list[str]:
    text = read("backend/app/core/queues.py")
    return sorted(set(re.findall(r'QUEUE_[A-Z0-9_]+\s*=\s*"([^"]+)"', text)))


def validate_queues_tasks_tables() -> None:
    queue_text = read("docs/ops/queue_topology.md")
    for queue in queue_names():
        if f"`{queue}`" not in queue_text and queue not in queue_text:
            fail(f"queue topology missing canonical queue {queue}")

    task_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "backend/app/tasks").glob("*.py")
    )
    required_task = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
    if required_task not in task_source:
        fail(f"source missing required B2.3 task {required_task}")
    docs_text = "\n".join(read(path) for path in RUNBOOKS)
    if required_task not in docs_text:
        fail(f"runbooks missing required B2.3 task {required_task}")

    migrations = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (ROOT / "alembic/versions").rglob("*.py")
    )
    for table in TABLE_TOKENS:
        if table not in migrations:
            fail(f"table token not found in migrations: {table}")
        if table not in docs_text:
            fail(f"table token not found in runbooks: {table}")


def validate_fixtures_and_safety() -> None:
    docs_text = "\n".join(read(path) for path in RUNBOOKS)
    for token in FIXTURE_TOKENS:
        if token not in docs_text:
            fail(f"missing fixture reference: {token}")
    for runbook in RUNBOOKS:
        text = read(runbook)
        if not re.search(r"(?i)safety|safe restart|unsafe restart|do not|forbidden", text):
            fail(f"{runbook} missing safety section or safety language")
    if "production replay endpoint" not in docs_text:
        fail("runbooks missing explicit production replay endpoint prohibition")
    if "B2.4" not in docs_text:
        fail("runbooks missing phase-boundary/B2.4 statement")


def validate_scripts_for_secret_and_replay_risk() -> None:
    scripts_text = "\n".join(read(path) for path in REQUIRED_SCRIPTS)
    bad_secret = re.search(
        r"(?i)(webhook|stripe|shopify|paypal|woocommerce).*secret\s*=\s*['\"][^'\"]{8,}",
        scripts_text,
    )
    if bad_secret:
        fail("scripts appear to hardcode a webhook secret")
    if "authenticity" not in scripts_text and "signature" not in scripts_text:
        fail("scripts do not expose signature/authenticity-sensitive handling")

    replay_script = read("scripts/ops/webhook_replay_local.py")
    for token in (
        "UNSAFE_REPLAY_TARGET_MESSAGE",
        "validate_local_api_base_url",
        "ALLOWED_LOCAL_REPLAY_HOSTS",
        "parsed.scheme != \"http\"",
        "rejected host",
    ):
        if token not in replay_script:
            fail(f"webhook replay target guard missing token: {token}")

    rls_script = read("scripts/ops/rls_check.py")
    for token in (
        "physical_rls_enforcement_proof",
        "m4-rls-bare-select-isolation",
        "role_bypasses_rls",
        "table_rls_enabled",
        "no tenant_id predicate",
        "connect_runtime",
    ):
        if token not in rls_script:
            fail(f"RLS physical proof missing token: {token}")

    api_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (ROOT / "backend/app").rglob("*.py")
    )
    if re.search(r"@router\.(post|put|patch)\([^)]*replay", api_text, re.IGNORECASE):
        fail("production replay endpoint detected")


def validate_readme_symptoms() -> None:
    readme = read("docs/ops/README.md")
    for symptom in SYMPTOMS:
        if symptom not in readme:
            fail(f"README missing symptom mapping: {symptom}")


def validate_runtime_harness_and_workflow() -> None:
    workflow = read(".github/workflows/m4-operational-runbooks.yml")
    if "paths:" in workflow:
        fail("M4 workflow must not use path filters once validate-ops-runbooks is required")
    for token in (
        "runtime-ops-proofs",
        "make ops-runtime-proof",
        "prepare_migration_authority_boundary.py",
        "DATABASE_URL=postgresql+asyncpg://app_user:app_user@postgres",
        "MIGRATION_DATABASE_URL=postgresql://migration_owner:migration_owner@postgres",
    ):
        if token not in workflow:
            fail(f"M4 runtime workflow missing token: {token}")

    harness = read("scripts/ops/runtime_proof_harness.py")
    for token in (
        "dlq_missing_negative",
        "rls_physical_boundary",
        "b23_unknown_negative",
        "webhook_valid_tampered_duplicate",
        "webhook_unsafe_target_negative",
        "clear_diagnostics.py",
    ):
        if token not in harness:
            fail(f"M4 runtime proof harness missing step: {token}")

    record = read("M4.1_Remediation_Completion_Record.md")
    if "PENDING_PROTECTED_BRANCH_MERGE_VERIFICATION" in record:
        fail("M4.1 completion record contains stale protected-branch placeholder")
    for token in (
        "Physical Trust-Boundary Proof",
        "Non-Vacuous Runtime Proof Harness",
        "Merge-Blocking Governance",
        "Scope Preservation",
        "Final Evidence Closure",
    ):
        if token not in record:
            fail(f"M4.1 completion record missing exit gate: {token}")


def main() -> None:
    validate_paths()
    validate_make_targets()
    validate_metadata()
    validate_host_native_drift()
    validate_queues_tasks_tables()
    validate_fixtures_and_safety()
    validate_scripts_for_secret_and_replay_risk()
    validate_readme_symptoms()
    validate_runtime_harness_and_workflow()
    print("M4_OPS_RUNBOOK_VALIDATION_PASS")


if __name__ == "__main__":
    main()
