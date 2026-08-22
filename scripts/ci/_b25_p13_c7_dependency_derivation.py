#!/usr/bin/env python3
"""Derive the confidence read model's ACTUAL decision dependencies from its SQL.

C6 validated one direction only: every registered field appears somewhere in the
read-model source text. That is satisfied by a registry that is a subset of what
the query really reads, which is exactly how ``created_at`` -- an ordering input
that decides ``has_newer_fit`` and therefore signed snapshot freshness -- stayed
governed-by-nobody while CI stayed green.

This module derives the other direction. It resolves the projection's CTE alias
map and reports the real column set each relation contributes, so the C7 gate can
assert set equality rather than substring membership. A new ``fit.foo``
reference that nobody registers has nowhere to hide.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path


# Alias -> physical relation, as bound in _EXACT_FIT_PROJECTION_SQL's FROM/JOIN
# clauses. A new alias the gate does not know about is an error rather than a
# silently ignored reference.
FIT_ALIASES = ("fit", "newer_fit")
FIT_CTE_ALIAS = "requested_fit"
NON_FIT_ALIASES = {
    "dirty": "public.b24_dirty_events",
    "artifact": "public.bayesian_artifacts",
}

# Bind parameters and CTE-local names that are not columns of any relation.
_REFERENCE = re.compile(r"\b([a-z_][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b")
_CTE_PROJECTION = re.compile(
    r"\bfit\.([a-z_][a-z0-9_]*)(?:\s+AS\s+([a-z_][a-z0-9_]*))?", re.IGNORECASE
)


class DependencyDerivationError(RuntimeError):
    """The read model references something the derivation cannot resolve."""


def extract_sql(read_model_source: str, name: str = "_EXACT_FIT_PROJECTION_SQL") -> str:
    """Pull one ``text(\"\"\"...\"\"\")`` SQL literal out of the read model."""

    tree = ast.parse(read_model_source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Call) and value.args:
            literal = value.args[0]
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                return literal.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
    raise DependencyDerivationError(f"projection_sql_missing:{name}")


def _cte_body(sql: str) -> str:
    """The requested_fit CTE, which defines the alias map for the whole query."""

    marker = "WITH requested_fit AS ("
    start = sql.find(marker)
    if start < 0:
        raise DependencyDerivationError("requested_fit_cte_missing")
    depth = 0
    for index in range(start + len(marker) - 1, len(sql)):
        if sql[index] == "(":
            depth += 1
        elif sql[index] == ")":
            depth -= 1
            if depth == 0:
                return sql[start + len(marker) : index]
    raise DependencyDerivationError("requested_fit_cte_unterminated")


def cte_alias_map(sql: str) -> dict[str, str]:
    """Map each requested_fit output name back to its physical fit column."""

    mapping: dict[str, str] = {}
    for column, alias in _CTE_PROJECTION.findall(_cte_body(sql)):
        mapping[(alias or column).lower()] = column.lower()
    if not mapping:
        raise DependencyDerivationError("requested_fit_projects_no_fit_columns")
    return mapping


def derive_dependencies(read_model_source: str) -> dict[str, frozenset[str]]:
    """Return {relation: columns the read model actually decides with}."""

    sql = extract_sql(read_model_source)
    aliases = cte_alias_map(sql)
    fit_columns: set[str] = set()
    non_fit: dict[str, set[str]] = {name: set() for name in NON_FIT_ALIASES.values()}
    unresolved: set[str] = set()

    for alias, member in _REFERENCE.findall(sql):
        alias = alias.lower()
        member = member.lower()
        if alias in FIT_ALIASES:
            fit_columns.add(member)
        elif alias == FIT_CTE_ALIAS:
            resolved = aliases.get(member)
            if resolved is None:
                # A requested_fit output that the CTE never projected: either a
                # typo or a new dependency added without updating the CTE.
                unresolved.add(f"{alias}.{member}")
            else:
                fit_columns.add(resolved)
        elif alias in NON_FIT_ALIASES:
            non_fit[NON_FIT_ALIASES[alias]].add(member)
        elif alias in ("public", "artifact_summary", "freshness_authority",
                       "candidate_keys", "both_buckets"):
            continue
        else:
            unresolved.add(f"{alias}.{member}")

    if unresolved:
        raise DependencyDerivationError(
            "unresolved_read_model_reference:" + ",".join(sorted(unresolved))
        )

    derived = {"public.bayesian_model_fits": frozenset(fit_columns)}
    for relation, columns in non_fit.items():
        derived[relation] = frozenset(columns)
    return derived


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    source = (root / "backend/app/confidence_projection/read_model.py").read_text(
        encoding="utf-8"
    )
    for relation, columns in sorted(derive_dependencies(source).items()):
        print(f"{relation} ({len(columns)}):")
        for column in sorted(columns):
            print(f"  - {column}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
