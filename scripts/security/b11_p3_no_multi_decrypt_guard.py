from __future__ import annotations

"""Fail CI when SQL multi-key trial decrypt anti-patterns are introduced."""

import argparse
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = (
    REPO_ROOT / "backend" / "app",
    REPO_ROOT / "backend" / "tests",
    REPO_ROOT / "alembic",
    REPO_ROOT / "db",
)
EXCLUDED_PATH_FRAGMENTS = (
    "backend/tests/fixtures/forbidden_multi_decrypt_fixture.sql",
)
FILE_EXTENSIONS = {".py", ".sql", ".md", ".txt", ".yaml", ".yml"}

MULTI_DECRYPT_PATTERN = re.compile(
    r"pgp_sym_decrypt\s*\([^)]*\)\s*,\s*pgp_sym_decrypt\s*\(",
    re.IGNORECASE | re.DOTALL,
)
COALESCE_MULTI_DECRYPT_PATTERN = re.compile(
    r"coalesce\s*\(\s*pgp_sym_decrypt\s*\([^)]*\)\s*,\s*pgp_sym_decrypt\s*\(",
    re.IGNORECASE | re.DOTALL,
)


def _iter_files() -> list[Path]:
    files: list[Path] = []
    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            continue
        for path in scan_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() in FILE_EXTENSIONS:
                normalized = path.as_posix()
                if any(fragment in normalized for fragment in EXCLUDED_PATH_FRAGMENTS):
                    continue
                files.append(path)
    return files


def _scan_file(path: Path) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    findings: list[str] = []
    for pattern in (MULTI_DECRYPT_PATTERN, COALESCE_MULTI_DECRYPT_PATTERN):
        for match in pattern.finditer(content):
            lineno = content.count("\n", 0, match.start()) + 1
            findings.append(
                f"{path.relative_to(REPO_ROOT)}:{lineno}: forbidden multi-decrypt SQL pattern"
            )
    return findings


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paths", nargs="*", help="optional files/dirs to scan")
    parser.add_argument("--report", help="optional report path")
    args = parser.parse_args(argv)

    if args.paths:
        paths: list[Path] = []
        for raw in args.paths:
            candidate = Path(raw)
            if candidate.is_dir():
                paths.extend(
                    [p for p in candidate.rglob("*") if p.is_file() and p.suffix.lower() in FILE_EXTENSIONS]
                )
            elif candidate.is_file():
                normalized = candidate.as_posix()
                if any(fragment in normalized for fragment in EXCLUDED_PATH_FRAGMENTS):
                    continue
                paths.append(candidate)
    else:
        paths = _iter_files()

    violations: list[str] = []
    for path in paths:
        violations.extend(_scan_file(path))

    lines: list[str] = ["b11_p3_no_multi_decrypt_guard", f"scanned_files={len(paths)}"]
    if violations:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("no forbidden multi-decrypt SQL patterns detected")
    payload = "\n".join(lines) + "\n"

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(payload, encoding="utf-8")

    sys.stdout.write(payload)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
