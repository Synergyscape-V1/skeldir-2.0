#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

DB_SECRET_KEYS = {
    "DATABASE_URL",
    "MIGRATION_DATABASE_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
}
PROVIDER_SECRET_KEYS = {
    "LLM_PROVIDER_API_KEY",
    "NEON_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "STRIPE_API_KEY",
    "PAYPAL_CLIENT_SECRET",
    "SHOPIFY_WEBHOOK_SECRET",
    "WOOCOMMERCE_WEBHOOK_SECRET",
}
TARGET_KEYS = DB_SECRET_KEYS | PROVIDER_SECRET_KEYS
ALLOWED_PATHS = {
    "backend/app/core/secrets.py",
    "backend/app/core/config.py",
    "backend/app/core/control_plane.py",
    "backend/app/core/managed_settings_contract.py",
    "alembic/env.py",
}


def _repo_rel(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def _const_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _scan_python_file(path: Path) -> tuple[list[str], list[str]]:
    rel = _repo_rel(path)
    if rel in ALLOWED_PATHS:
        return [], []
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    db_hits: list[str] = []
    provider_hits: list[str] = []

    def _add(key: str, msg: str) -> None:
        if key in DB_SECRET_KEYS:
            db_hits.append(msg)
        if key in PROVIDER_SECRET_KEYS:
            provider_hits.append(msg)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "settings":
                key = node.attr
                if key in TARGET_KEYS:
                    _add(key, f"{rel}:{node.lineno}: forbidden settings secret access settings.{key}")
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name in {"os.getenv", "os.environ.get"} and node.args:
                key = _const_string(node.args[0])
                if key in TARGET_KEYS:
                    _add(key, f"{rel}:{node.lineno}: forbidden env secret access {name}('{key}')")
        if isinstance(node, ast.Subscript):
            if (
                isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
                and node.value.attr == "environ"
            ):
                key = _const_string(node.slice)
                if key in TARGET_KEYS:
                    _add(key, f"{rel}:{node.lineno}: forbidden env secret access os.environ['{key}']")
    return db_hits, provider_hits


def _scan_workflows(workflow_paths: list[Path]) -> list[str]:
    violations: list[str] = []
    workflows = workflow_paths
    risky_github_secret = re.compile(r"\$\{\{\s*secrets\.(NEON_API_KEY|NEON_PROJECT_ID|DATABASE_URL|MIGRATION_DATABASE_URL)\s*}}")
    dsn_pattern = re.compile(r"postgresql(?:\+asyncpg)?://[^\s\"']+")
    allowed_hosts = ("localhost", "127.0.0.1", "postgres")

    for path in workflows:
        rel = _repo_rel(path)
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            if risky_github_secret.search(line):
                violations.append(f"{rel}:{idx}: prohibited GitHub secret source for high-risk credential")
            for match in dsn_pattern.finditer(line):
                dsn = match.group(0)
                if "user:pass@host" in dsn:
                    continue
                host = ""
                if "@" in dsn:
                    host = dsn.split("@", 1)[1].split("/", 1)[0].split("?", 1)[0].split(":", 1)[0].lower()
                if host and host not in allowed_hosts:
                    violations.append(f"{rel}:{idx}: prohibited non-local inline DSN")
    return violations


def _write_report(path: Path, header: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [header, f"violations={len(lines)}", *lines]
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="B11-P4 static governance scans")
    parser.add_argument(
        "--out-dir",
        default="docs/forensics/evidence/b11_p4",
        help="Output evidence directory",
    )
    parser.add_argument("--python-paths", nargs="*", default=None)
    parser.add_argument("--workflow-paths", nargs="*", default=None)
    args = parser.parse_args()

    out_dir = (REPO_ROOT / args.out_dir).resolve()
    if args.python_paths:
        py_files = [Path(item).resolve() for item in args.python_paths]
    else:
        py_files = sorted((REPO_ROOT / "backend" / "app").rglob("*.py"))
        py_files.append(REPO_ROOT / "alembic" / "env.py")

    db_violations: list[str] = []
    provider_violations: list[str] = []
    for py_file in py_files:
        if not py_file.exists():
            continue
        db_hits, provider_hits = _scan_python_file(py_file)
        db_violations.extend(db_hits)
        provider_violations.extend(provider_hits)

    if args.workflow_paths:
        workflow_paths = [Path(item).resolve() for item in args.workflow_paths]
    else:
        workflow_paths = sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml"))
    workflow_violations = _scan_workflows(workflow_paths)

    _write_report(out_dir / "db_dsn_callsite_scan.txt", "b11_p4_db_dsn_callsite_scan", db_violations)
    _write_report(
        out_dir / "provider_key_callsite_scan.txt",
        "b11_p4_provider_key_callsite_scan",
        provider_violations,
    )
    _write_report(
        out_dir / "workflow_plaintext_secret_scan.txt",
        "b11_p4_workflow_plaintext_secret_scan",
        workflow_violations,
    )

    print((out_dir / "db_dsn_callsite_scan.txt").as_posix())
    print((out_dir / "provider_key_callsite_scan.txt").as_posix())
    print((out_dir / "workflow_plaintext_secret_scan.txt").as_posix())

    return 1 if (db_violations or provider_violations or workflow_violations) else 0


if __name__ == "__main__":
    raise SystemExit(main())
