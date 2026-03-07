from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


_SYSTEM_AUTHORITY_MODULE = "app.tasks.authority"
_SYSTEM_AUTHORITY_SYMBOL = "SystemAuthorityEnvelope"
_ALLOWED_SYSTEM_AUTHORITY_ORIGINS = {
    "backend/app/api/webhooks.py",
    "backend/app/services/attribution.py",
    "backend/app/services/llm_dispatch.py",
    "backend/app/tasks/maintenance.py",
    "backend/app/tasks/matviews.py",
}


@dataclass(frozen=True)
class _BoundaryViolation:
    path: str
    line: int
    reason: str


def _detect_system_authority_violations(*, source: str, path: str) -> list[_BoundaryViolation]:
    tree = ast.parse(source, filename=path)
    imported_symbol_aliases: set[str] = set()
    imported_module_aliases: set[str] = set()
    violations: list[_BoundaryViolation] = []

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == _SYSTEM_AUTHORITY_MODULE:
            for alias in node.names:
                if alias.name == _SYSTEM_AUTHORITY_SYMBOL:
                    imported_symbol_aliases.add(alias.asname or alias.name)
                    violations.append(
                        _BoundaryViolation(
                            path=path,
                            line=node.lineno,
                            reason="disallowed import of SystemAuthorityEnvelope",
                        )
                    )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _SYSTEM_AUTHORITY_MODULE:
                    imported_module_aliases.add(alias.asname or alias.name.split(".")[-1])

    class _CallVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
            if isinstance(node.func, ast.Name) and node.func.id in imported_symbol_aliases:
                violations.append(
                    _BoundaryViolation(
                        path=path,
                        line=node.lineno,
                        reason="disallowed SystemAuthorityEnvelope constructor call",
                    )
                )
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in imported_module_aliases
                and node.func.attr == _SYSTEM_AUTHORITY_SYMBOL
            ):
                violations.append(
                    _BoundaryViolation(
                        path=path,
                        line=node.lineno,
                        reason="disallowed SystemAuthorityEnvelope constructor call",
                    )
                )
            self.generic_visit(node)

    _CallVisitor().visit(tree)
    return violations


def _collect_repo_violations(repo_root: Path) -> list[_BoundaryViolation]:
    app_root = repo_root / "backend" / "app"
    violations: list[_BoundaryViolation] = []
    for path in app_root.rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        if relative in _ALLOWED_SYSTEM_AUTHORITY_ORIGINS:
            continue
        source = path.read_text(encoding="utf-8")
        violations.extend(_detect_system_authority_violations(source=source, path=relative))
    return violations


def test_system_authority_origination_is_allowlisted_in_app_code() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violations = _collect_repo_violations(repo_root)
    rendered = [f"{v.path}:{v.line} {v.reason}" for v in violations]
    assert not rendered, f"System authority origination boundary violated: {rendered}"


def test_system_authority_boundary_detector_negative_control() -> None:
    source = (
        "from app.tasks.authority import SystemAuthorityEnvelope\n"
        "def build(tenant_id):\n"
        "    return SystemAuthorityEnvelope(tenant_id=tenant_id)\n"
    )
    violations = _detect_system_authority_violations(
        source=source,
        path="backend/app/api/disallowed_boundary_probe.py",
    )
    reasons = [violation.reason for violation in violations]
    assert "disallowed import of SystemAuthorityEnvelope" in reasons
    assert "disallowed SystemAuthorityEnvelope constructor call" in reasons
