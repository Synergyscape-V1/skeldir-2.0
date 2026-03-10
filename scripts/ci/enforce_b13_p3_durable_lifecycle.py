#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_CONTEXT = "B1.3 P3 Durable Lifecycle Schema Proofs"

REQUIRED_MIGRATION_FRAGMENTS = (
    "ADD COLUMN IF NOT EXISTS next_refresh_due_at timestamptz",
    "ADD COLUMN IF NOT EXISTS lifecycle_status text NOT NULL DEFAULT 'active'",
    "ADD COLUMN IF NOT EXISTS refresh_failure_count integer NOT NULL DEFAULT 0",
    "ADD COLUMN IF NOT EXISTS last_failure_class text",
    "ADD COLUMN IF NOT EXISTS last_failure_at timestamptz",
    "ADD COLUMN IF NOT EXISTS last_refresh_at timestamptz",
    "ADD COLUMN IF NOT EXISTS revoked_at timestamptz",
    "ck_platform_credentials_lifecycle_status_valid",
    "ck_platform_credentials_refresh_failure_count_nonnegative",
    "ck_platform_credentials_revoked_status_consistency",
    "idx_platform_credentials_refresh_due",
    "FORCE ROW LEVEL SECURITY",
    "tenant_isolation_policy ON public.platform_credentials",
)

REQUIRED_MODEL_FRAGMENTS = (
    '__tablename__ = "platform_credentials"',
    "next_refresh_due_at",
    "lifecycle_status",
    "refresh_failure_count",
    "last_failure_class",
    "last_failure_at",
    "last_refresh_at",
    "revoked_at",
    "idx_platform_credentials_refresh_due",
)

REQUIRED_SERVICE_PATTERNS = (
    ("list_refresh_due", re.compile(r"def\s+list_refresh_due\(", re.MULTILINE)),
    ("record_refresh_failure", re.compile(r"def\s+record_refresh_failure\(", re.MULTILINE)),
    ("mark_refresh_success", re.compile(r"def\s+mark_refresh_success\(", re.MULTILINE)),
    ("mark_revoked", re.compile(r"def\s+mark_revoked\(", re.MULTILINE)),
)

FORBIDDEN_PARALLEL_STORE_PATTERNS = (
    re.compile(r"CREATE\s+TABLE\s+(?:public\.)?platform_tokens\b", re.IGNORECASE),
    re.compile(r"CREATE\s+TABLE\s+(?:public\.)?provider_tokens\b", re.IGNORECASE),
    re.compile(r"CREATE\s+TABLE\s+(?:public\.)?provider_credentials\b", re.IGNORECASE),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P3 durable lifecycle schema enforcement")
    parser.add_argument(
        "--migration-file",
        default="alembic/versions/007_skeldir_foundation/202603101530_b13_p3_platform_credentials_lifecycle_metadata.py",
    )
    parser.add_argument(
        "--model-file",
        default="backend/app/models/platform_credential.py",
    )
    parser.add_argument(
        "--service-file",
        default="backend/app/services/platform_credentials.py",
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
        "--migrations-dir",
        default="alembic/versions",
    )
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_method_block(source: str, method_name: str) -> str:
    marker = f"def {method_name}("
    start = source.find(marker)
    if start < 0:
        return ""
    next_def = source.find("\n    @staticmethod", start + len(marker))
    if next_def < 0:
        next_def = source.find("\ndef ", start + len(marker))
    if next_def < 0:
        next_def = len(source)
    return source[start:next_def]


def _count_platform_credentials_table_creates(migrations_dir: Path) -> int:
    pattern = re.compile(r"CREATE\s+TABLE\s+(?:public\.)?platform_credentials\b", re.IGNORECASE)
    count = 0
    for path in sorted(migrations_dir.rglob("*.py")):
        text = _read_text(path)
        count += len(pattern.findall(text))
    return count


def main() -> int:
    args = _parse_args()

    migration_path = Path(args.migration_file)
    model_path = Path(args.model_file)
    service_path = Path(args.service_file)
    workflow_path = Path(args.workflow_file)
    checks_contract_path = Path(args.required_checks_contract)
    migrations_dir = Path(args.migrations_dir)

    files = (
        migration_path,
        model_path,
        service_path,
        workflow_path,
        checks_contract_path,
        migrations_dir,
    )
    missing = [path for path in files if not path.exists()]
    if missing:
        print("B1.3-P3 durable lifecycle gate failed:")
        for path in missing:
            print(f"  - file not found: {path}")
        return 1

    migration_text = _read_text(migration_path)
    model_text = _read_text(model_path)
    service_text = _read_text(service_path)
    workflow_text = _read_text(workflow_path)
    checks_contract = json.loads(checks_contract_path.read_text(encoding="utf-8"))

    errors: list[str] = []

    for fragment in REQUIRED_MIGRATION_FRAGMENTS:
        if fragment not in migration_text:
            errors.append(f"migration missing required fragment: {fragment}")

    if "CREATE TABLE" in migration_text:
        errors.append("P3 migration must extend durable hierarchy in place (CREATE TABLE detected)")

    for fragment in REQUIRED_MODEL_FRAGMENTS:
        if fragment not in model_text:
            errors.append(f"model missing required fragment: {fragment}")

    for label, pattern in REQUIRED_SERVICE_PATTERNS:
        if not pattern.search(service_text):
            errors.append(f"service missing required method: {label}")

    due_block = _extract_method_block(service_text, "list_refresh_due")
    if not due_block:
        errors.append("unable to isolate list_refresh_due method block")
    else:
        if "encrypted_access_token" in due_block or "_decrypt_ciphertext_once" in due_block:
            errors.append("list_refresh_due must not decrypt or read encrypted token columns")

    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required P3 context: {REQUIRED_CONTEXT}")

    required_contexts = checks_contract.get("required_contexts")
    if not isinstance(required_contexts, list):
        errors.append("required status checks contract missing required_contexts list")
    elif REQUIRED_CONTEXT not in required_contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")

    platform_credentials_creates = _count_platform_credentials_table_creates(migrations_dir)
    if platform_credentials_creates != 1:
        errors.append(
            "expected exactly one platform_credentials CREATE TABLE across migrations; "
            f"found={platform_credentials_creates}"
        )

    for path in sorted(migrations_dir.rglob("*.py")):
        text = _read_text(path)
        for pattern in FORBIDDEN_PARALLEL_STORE_PATTERNS:
            if pattern.search(text):
                errors.append(f"forbidden parallel durable token store pattern detected in {path}: {pattern.pattern}")

    if errors:
        print("B1.3-P3 durable lifecycle gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P3 durable lifecycle gate passed.")
    print(f"  migration={migration_path}")
    print(f"  model={model_path}")
    print(f"  service={service_path}")
    print(f"  required_context={REQUIRED_CONTEXT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
