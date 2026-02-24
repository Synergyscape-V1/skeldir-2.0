#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key_block": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    "github_pat": re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
}


def _git_tracked_files() -> list[Path]:
    proc = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    files: list[Path] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        files.append((REPO_ROOT / line.strip()).resolve())
    return files


def _scan_text(text: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for name, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                {
                    "pattern": name,
                    "excerpt": text[max(0, match.start() - 8): min(len(text), match.end() + 8)],
                }
            )
    return findings


def _scan_repo() -> tuple[int, list[dict[str, object]]]:
    scanned = 0
    matches: list[dict[str, object]] = []
    for path in _git_tracked_files():
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scanned += 1
        hits = _scan_text(content)
        for hit in hits:
            matches.append(
                {
                    "path": str(path.relative_to(REPO_ROOT).as_posix()),
                    "pattern": str(hit["pattern"]),
                    "excerpt": str(hit["excerpt"]),
                }
            )
    return scanned, matches


def main() -> int:
    parser = argparse.ArgumentParser(description="B11-P6 repo tracked-file secret scan")
    parser.add_argument(
        "--output",
        default="docs/forensics/evidence/b11_p6/no_secrets_repo_scan.json",
        help="Output JSON path.",
    )
    args = parser.parse_args()

    negative_control_text = (
        "canary_key=AKIA1234567890ABCDEF\n"
        "-----BEGIN PRIVATE KEY-----\nFAKE\n-----END PRIVATE KEY-----\n"
    )
    negative_control_hits = _scan_text(negative_control_text)
    non_vacuous = len(negative_control_hits) >= 2

    scanned_files, matches = _scan_repo()
    status = "PASS" if (non_vacuous and not matches) else "FAIL"

    payload = {
        "scanner": "b11_p6_repo_secret_scan",
        "status": status,
        "scanned_tracked_files": scanned_files,
        "patterns": sorted(PATTERNS.keys()),
        "non_vacuous_negative_control_detected": non_vacuous,
        "matches": matches,
    }

    out_path = (REPO_ROOT / args.output).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(out_path.as_posix())
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
