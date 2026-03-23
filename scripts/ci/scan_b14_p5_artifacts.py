#!/usr/bin/env python3
"""B1.4-P5 artifact no-leak scanner."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b")
IPV4_PATTERN = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
KEY_VALUE_PATTERN = re.compile(
    r"(?i)\b("
    r"session_id|idempotency_key|external_event_id|order_id|click_id|gclid|fbclid|transaction_id|user_agent|ip_address|ip"
    r")\b"
    r"\s*[:=]\s*"
    r"(\"[^\"]*\"|'[^']*'|[^\s,}\]]+)"
)
SAFE_PROXY_VALUES = {
    "***",
    "[REDACTED]",
    "[REDACTED_B1.4]",
    "null",
    "none",
    "{}",
    "[]",
    "false",
    "0",
    '""',
    "''",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan B1.4-P5 artifacts for no-leak violations")
    parser.add_argument("--artifacts-dir", default="artifacts/b14_p5")
    parser.add_argument("--canary", action="append", default=[])
    parser.add_argument("--simulate-regression", action="store_true")
    return parser.parse_args(argv)


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            files.append(path)
    return files


def _normalize_value(raw: str) -> str:
    value = raw.strip().strip(",;")
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        value = value[1:-1]
    return value.strip().lower()


def _scan_file(path: Path, *, canaries: list[str]) -> list[str]:
    content = path.read_text(encoding="utf-8", errors="replace")
    findings: list[str] = []
    lines = content.splitlines()
    for line_no, line in enumerate(lines, start=1):
        lower = line.lower()
        if EMAIL_PATTERN.search(line):
            findings.append(f"{path}:{line_no}:email-pattern")
        if IPV4_PATTERN.search(line):
            findings.append(f"{path}:{line_no}:ip-pattern")
        if SSN_PATTERN.search(line):
            findings.append(f"{path}:{line_no}:ssn-pattern")
        for match in KEY_VALUE_PATTERN.finditer(line):
            value = _normalize_value(match.group(2))
            if value in SAFE_PROXY_VALUES:
                continue
            findings.append(f"{path}:{line_no}:proxy-key:{match.group(1)}")
        for canary in canaries:
            if canary and canary.lower() in lower:
                findings.append(f"{path}:{line_no}:seeded-canary")
    return findings


def main(argv: list[str]) -> int:
    args = _parse_args(argv)
    if args.simulate_regression:
        print("b14_p5_artifact_scanner")
        print("result=FAIL")
        print("synthetic_regression=seeded_canary_detected")
        return 1

    artifacts_dir = Path(args.artifacts_dir)
    if not artifacts_dir.exists():
        print(f"b14_p5_artifact_scanner\nresult=FAIL\nmissing_artifacts_dir={artifacts_dir}")
        return 1

    findings: list[str] = []
    for path in _iter_text_files(artifacts_dir):
        findings.extend(_scan_file(path, canaries=args.canary))

    if findings:
        print("b14_p5_artifact_scanner")
        print("result=FAIL")
        for finding in findings:
            print(f"finding={finding}")
        return 1

    print("b14_p5_artifact_scanner")
    print("result=PASS")
    print(f"artifacts_dir={artifacts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

