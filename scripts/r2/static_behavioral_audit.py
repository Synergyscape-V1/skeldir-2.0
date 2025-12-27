#!/usr/bin/env python3
"""
R2 Static Behavioral Innocence (Defense-in-Depth)

This is an independent hard gate that scans the codebase for latent destructive
write paths targeting immutable tables.

Requirements:
  - Emit scope manifest + scope hash
  - Scan raw SQL strings and SQLAlchemy/driver patterns
  - Any allowlist must be explicit in scripts/r2/static_audit_allowlist.json
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional


IMMUTABLE_TABLES = ("attribution_events", "revenue_ledger")
DESTRUCTIVE_VERBS = ("UPDATE", "DELETE", "TRUNCATE", "ALTER")

DEFAULT_SCAN_ROOTS = (
    "backend/app",
    "scripts",
    "tools",
    "server",
)

DEFAULT_EXCLUDE_DIRS = (
    ".git",
    ".venv",
    "backend/.venv",
    "backend/.pytest_cache",
    "backend/.hypothesis",
    "node_modules",
    "dist",
    "artifacts",
    "tmp",
    "playwright-report",
    "test-results",
)

DEFAULT_EXCLUDE_PATH_PARTS = (
    "/tests/",
    "\\tests\\",
)


RAW_SQL_DESTRUCTIVE_RE = re.compile(
    rf"(?is)\b({'|'.join(DESTRUCTIVE_VERBS)})\b[\s\S]{{0,200}}\b({'|'.join(IMMUTABLE_TABLES)})\b"
)

# Heuristic for f-strings building destructive SQL against a table_name variable:
#   table_name = 'attribution_events'
#   text(f"UPDATE {table_name} SET ...")
TABLE_NAME_ASSIGN_RE = re.compile(
    rf"(?im)^\s*table_name\s*=\s*['\"]({'|'.join(IMMUTABLE_TABLES)})['\"]\s*$"
)
FSTRING_DESTRUCTIVE_RE = re.compile(r"(?is)\b(UPDATE|DELETE|TRUNCATE|ALTER)\b\s*{table_name}\b")


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    excerpt: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _scope_hash(paths: List[Path]) -> str:
    per_file = []
    for path in paths:
        digest = _sha256_bytes(path.read_bytes())
        per_file.append(f"{digest}  {path.as_posix()}")
    joined = "\n".join(sorted(per_file)).encode("utf-8")
    return _sha256_bytes(joined)


def _iter_python_files(repo_root: Path, roots: Iterable[str]) -> List[Path]:
    files: List[Path] = []
    for root in roots:
        base = (repo_root / root).resolve()
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(repo_root).as_posix()
            if any(part in rel for part in DEFAULT_EXCLUDE_PATH_PARTS):
                continue
            if any(rel.startswith(ex_dir.rstrip("/") + "/") or rel == ex_dir for ex_dir in DEFAULT_EXCLUDE_DIRS):
                continue
            if any(f"/{ex_dir.strip('/')}/" in f"/{rel}/" for ex_dir in DEFAULT_EXCLUDE_DIRS):
                continue
            files.append(path)
    return sorted(set(files))


def _load_allowlist(repo_root: Path, allowlist_path: str) -> dict:
    path = repo_root / allowlist_path
    data = json.loads(path.read_text(encoding="utf-8"))
    if "allow" not in data or not isinstance(data["allow"], list):
        raise ValueError("Allowlist must contain an 'allow' array")
    return data


def _is_allowlisted(*, allowlist: dict, path: str, kind: str, excerpt: str) -> bool:
    for entry in allowlist.get("allow", []):
        if entry.get("path") != path:
            continue
        if entry.get("kind") and entry["kind"] != kind:
            continue
        pattern = entry.get("excerpt_regex")
        if pattern:
            if re.search(pattern, excerpt):
                return True
        else:
            return True
    return False


def _first_line_containing(text: str, needle: str) -> int:
    for idx, line in enumerate(text.splitlines(), start=1):
        if needle in line:
            return idx
    return 1


def _scan_text(path: Path, content: str) -> List[Finding]:
    findings: List[Finding] = []

    if TABLE_NAME_ASSIGN_RE.search(content) and FSTRING_DESTRUCTIVE_RE.search(content):
        findings.append(
            Finding(
                path=path.as_posix(),
                line=_first_line_containing(content, "table_name"),
                kind="fstring_sql_destructive_table_name_variable",
                excerpt="table_name assigned to immutable table and used in destructive f-string SQL",
            )
        )

    return findings


def _extract_string_literals(node: ast.AST) -> List[str]:
    literals: List[str] = []
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        literals.append(node.value)
    if isinstance(node, ast.JoinedStr):
        # Only keep literal pieces; placeholders are ignored.
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                literals.append(part.value)
    return literals


def _scan_ast(path: Path, content: str) -> List[Finding]:
    findings: List[Finding] = []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return findings

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        func_name: Optional[str] = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        # Detect sqlalchemy.text("DELETE FROM attribution_events ...") style.
        if func_name == "text" and node.args:
            literals = _extract_string_literals(node.args[0])
            for literal in literals:
                if RAW_SQL_DESTRUCTIVE_RE.search(literal):
                    findings.append(
                        Finding(
                            path=path.as_posix(),
                            line=getattr(node, "lineno", 1),
                            kind="sqlalchemy_text_destructive_on_immutable",
                            excerpt=literal.strip().replace("\n", "\\n")[:300],
                        )
                    )

        # Detect direct driver/connection executes with literal SQL:
        #   conn.execute("DELETE FROM attribution_events ...")
        if func_name == "execute" and node.args:
            literals = _extract_string_literals(node.args[0])
            for literal in literals:
                if RAW_SQL_DESTRUCTIVE_RE.search(literal):
                    findings.append(
                        Finding(
                            path=path.as_posix(),
                            line=getattr(node, "lineno", 1),
                            kind="execute_literal_sql_destructive_on_immutable",
                            excerpt=literal.strip().replace("\n", "\\n")[:300],
                        )
                    )

        # Detect SQLAlchemy Core delete/update() targeting immutable ORM class names.
        if func_name in {"delete", "update"}:
            # Conservative: if AttributionEvent symbol appears in args, treat as violation.
            arg_names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
            if "AttributionEvent" in arg_names:
                findings.append(
                    Finding(
                        path=path.as_posix(),
                        line=getattr(node, "lineno", 1),
                        kind="sqlalchemy_core_mutation_on_attributionevent",
                        excerpt=f"{func_name}(AttributionEvent...)",
                    )
                )

        # Detect ORM bulk ops: query(...).delete/update on immutable table names in nearby literals.
        if func_name in {"delete", "update"} and isinstance(node.func, ast.Attribute):
            # Look for string literals in the call that mention immutable tables.
            call_literals: List[str] = []
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                call_literals.extend(_extract_string_literals(arg))
            if any(t in lit.lower() for t in IMMUTABLE_TABLES for lit in call_literals):
                findings.append(
                    Finding(
                        path=path.as_posix(),
                        line=getattr(node, "lineno", 1),
                        kind="orm_bulk_mutation_mentions_immutable_table",
                        excerpt=f"{func_name}(...) mentions immutable table",
                    )
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--allowlist", default="scripts/r2/static_audit_allowlist.json")
    parser.add_argument("--artifact-json", required=False)
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    allowlist = _load_allowlist(repo_root, args.allowlist)

    files = _iter_python_files(repo_root, DEFAULT_SCAN_ROOTS)
    scope_hash = _scope_hash(files)

    findings: List[Finding] = []
    for path in files:
        rel = path.relative_to(repo_root).as_posix()
        content = path.read_text(encoding="utf-8", errors="replace")
        for finding in _scan_text(Path(rel), content) + _scan_ast(Path(rel), content):
            if not _is_allowlisted(
                allowlist=allowlist, path=finding.path, kind=finding.kind, excerpt=finding.excerpt
            ):
                findings.append(finding)

    verdict = {
        "immutable_tables": IMMUTABLE_TABLES,
        "destructive_verbs": DESTRUCTIVE_VERBS,
        "scope": {
            "roots": list(DEFAULT_SCAN_ROOTS),
            "excluded_dirs": list(DEFAULT_EXCLUDE_DIRS),
            "excluded_path_parts": list(DEFAULT_EXCLUDE_PATH_PARTS),
            "files": [p.relative_to(repo_root).as_posix() for p in files],
            "file_count": len(files),
            "scope_hash_sha256": scope_hash,
        },
        "allowlist": allowlist,
        "finding_count": len(findings),
        "findings": [asdict(f) for f in findings[:200]],
    }

    print("R2_STATIC_BEHAVIORAL_INNOCENCE_VERDICT")
    print(f"SCOPE_FILES_COUNT={len(files)}")
    print(f"SCOPE_HASH_SHA256={scope_hash}")
    print(f"ALLOWLIST_ENTRIES={len(allowlist.get('allow', []))}")
    print(f"STATIC_FORBIDDEN_MATCH_COUNT={len(findings)}")
    if findings:
        print("FAILURES=" + "; ".join(f"{f.path}:{f.line}:{f.kind}" for f in findings[:25]))
    print("END_VERDICT")

    if args.artifact_json:
        Path(args.artifact_json).write_text(json.dumps(verdict, indent=2, sort_keys=True), encoding="utf-8")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
