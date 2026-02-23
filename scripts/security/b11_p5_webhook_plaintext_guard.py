from __future__ import annotations

"""Fail CI if plaintext tenant webhook secret columns are reintroduced."""

import argparse
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]

SCAN_PATHS = (
    REPO_ROOT / "backend" / "app",
    REPO_ROOT / "alembic" / "versions",
)

ALLOWED_HISTORICAL_PATH_FRAGMENTS = (
    "alembic/versions/005_webhook_secrets/202511171000_add_webhook_secrets.py",
    "alembic/versions/007_skeldir_foundation/202512271910_r3_add_webhook_secrets_columns.py",
    "alembic/versions/007_skeldir_foundation/202601211900_b057_p3_webhook_tenant_secret_resolver.py",
    "alembic/versions/007_skeldir_foundation/202602221630_b11_p5_webhook_secret_redesign.py",
    "alembic/versions/007_skeldir_foundation/202602221700_b11_p5_webhook_secret_contract_drop_plaintext.py",
)

FILE_EXTENSIONS = {".py", ".sql", ".yml", ".yaml", ".md"}

PLAIN_WEBHOOK_FIELD_PATTERN = re.compile(
    r"\b(shopify|stripe|paypal|woocommerce)_webhook_secret\b(?!_(ciphertext|key_id))",
    re.IGNORECASE,
)
SQL_CONTEXT_HINTS = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "ALTER",
    "FROM",
    "WHERE",
    "RETURNS TABLE",
    "TENANTS",
    " T.",
)


def _iter_paths() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_PATHS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in FILE_EXTENSIONS:
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if any(fragment in rel for fragment in ALLOWED_HISTORICAL_PATH_FRAGMENTS):
                continue
            files.append(path)
    return files


def _find_violations(path: Path) -> list[str]:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        rel = path.as_posix()
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    violations: list[str] = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if not PLAIN_WEBHOOK_FIELD_PATTERN.search(line):
            continue
        if rel.startswith("backend/app/"):
            line_upper = line.upper()
            if not any(hint in line_upper for hint in SQL_CONTEXT_HINTS):
                continue
        violations.append(f"{rel}:{lineno}: forbidden plaintext webhook field reference")
    return violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="Optional output report file path")
    parser.add_argument("--paths", nargs="*", help="Optional explicit files/directories")
    args = parser.parse_args(argv)

    if args.paths:
        to_scan: list[Path] = []
        for raw in args.paths:
            candidate = Path(raw)
            if candidate.is_file():
                to_scan.append(candidate)
            elif candidate.is_dir():
                to_scan.extend(
                    [
                        p
                        for p in candidate.rglob("*")
                        if p.is_file() and p.suffix.lower() in FILE_EXTENSIONS
                    ]
                )
    else:
        to_scan = _iter_paths()

    violations: list[str] = []
    for path in to_scan:
        violations.extend(_find_violations(path))

    lines = ["b11_p5_webhook_plaintext_guard", f"scanned_files={len(to_scan)}"]
    if violations:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("no plaintext webhook secret references detected")
    payload = "\n".join(lines) + "\n"

    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(payload, encoding="utf-8")

    sys.stdout.write(payload)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
