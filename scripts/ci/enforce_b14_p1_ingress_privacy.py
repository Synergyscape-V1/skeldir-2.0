#!/usr/bin/env python3
"""B1.4-P1 ingress privacy semantic enforcement."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

BANNED_DIRECT_PII_KEYS = (
    "email",
    "email_address",
    "phone",
    "phone_number",
    "ssn",
    "social_security_number",
    "ip_address",
    "ip",
    "first_name",
    "last_name",
    "full_name",
    "address",
    "street_address",
    "receipt_email",
    "customer_email",
    "user_agent",
)

INTERNAL_CONTRACT_FILES = (
    REPO_ROOT / "api-contracts/openapi/v1/attribution.yaml",
    REPO_ROOT / "api-contracts/openapi/v1/export.yaml",
    REPO_ROOT / "api-contracts/openapi/v1/reconciliation.yaml",
)

SOURCE_REQUIREMENTS = (
    (
        REPO_ROOT / "backend/app/ingestion/event_service.py",
        (
            "enforce_ingress_privacy_boundary(",
            "mode=\"strip\"",
            "raw_payload=durable_payload",
        ),
    ),
    (
        REPO_ROOT / "backend/app/ingestion/dlq_handler.py",
        (
            "enforce_ingress_privacy_boundary(",
            "mode=\"redact\"",
            "raw_payload=boundary.sanitized_payload",
            "build_dlq_retry_payload(",
        ),
    ),
    (
        REPO_ROOT / "backend/app/api/webhooks.py",
        (
            "identity_payload=identity_payload or payload",
            "request_headers=request_headers",
        ),
    ),
)

SOURCE_FORBIDDEN_PATTERNS = (
    (
        REPO_ROOT / "backend/app/ingestion/event_service.py",
        re.compile(r"raw_payload\s*=\s*event_data\b"),
    ),
    (
        REPO_ROOT / "backend/app/ingestion/dlq_handler.py",
        re.compile(r"raw_payload\s*=\s*original_payload\b"),
    ),
    (
        REPO_ROOT / "backend/app/ingestion/dlq_handler.py",
        re.compile(r"retry_payload\s*=\s*dead_event\.raw_payload\b"),
    ),
    (
        REPO_ROOT / "backend/app/api/webhooks.py",
        re.compile(r'error_type\s*=\s*"pii_violation"'),
    ),
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _scan_internal_contract(path: Path) -> list[str]:
    text = _read(path)
    violations: list[str] = []
    for key in BANNED_DIRECT_PII_KEYS:
        # Block schema-style property keys (provider contact metadata with inline
        # values like "email: engineering@..." is intentionally ignored).
        pattern = re.compile(rf"(?mi)^\s*{re.escape(key)}\s*:\s*$")
        if pattern.search(text):
            violations.append(f"internal_contract_pii_key: {path}:{key}")
    return violations


def run_enforcement(extra_contract_files: list[Path]) -> tuple[int, list[str]]:
    violations: list[str] = []

    for path, required_tokens in SOURCE_REQUIREMENTS:
        text = _read(path)
        for token in required_tokens:
            if token not in text:
                violations.append(f"missing_required_token: {path}:{token}")

    for path, forbidden_pattern in SOURCE_FORBIDDEN_PATTERNS:
        text = _read(path)
        if forbidden_pattern.search(text):
            violations.append(
                f"forbidden_pattern_detected: {path}:{forbidden_pattern.pattern}"
            )

    app_source_root = REPO_ROOT / "backend" / "app"
    raw_payload_model_validate = re.compile(r"model_validate\(\s*dead_event\.raw_payload")
    for source_file in app_source_root.rglob("*.py"):
        text = _read(source_file)
        if raw_payload_model_validate.search(text):
            violations.append(
                f"forbidden_pattern_detected: {source_file}:{raw_payload_model_validate.pattern}"
            )

    for contract in (*INTERNAL_CONTRACT_FILES, *extra_contract_files):
        if not contract.exists():
            violations.append(f"missing_contract_file: {contract}")
            continue
        violations.extend(_scan_internal_contract(contract))

    status = 1 if violations else 0
    return status, violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P1 ingress privacy enforcer")
    parser.add_argument(
        "--simulate-regression",
        action="store_true",
        help="Emit a synthetic regression violation and exit non-zero.",
    )
    parser.add_argument(
        "--additional-contract-file",
        action="append",
        default=[],
        help="Additional internal contract files to scan (used for negative controls).",
    )
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p1_ingress_privacy_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forbidden_pattern_detected\n"
        )
        return 1

    extra_contract_files = [Path(item).resolve() for item in args.additional_contract_file]
    status, violations = run_enforcement(extra_contract_files)

    lines = ["b14_p1_ingress_privacy_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=all ingress privacy invariants satisfied")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
