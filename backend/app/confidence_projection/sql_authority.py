"""Executable-SQL dependency authority for the B2.4 Trust projection."""

from __future__ import annotations

import re
from collections.abc import Iterable


class ConfidenceProjectionAuthorityError(RuntimeError):
    """The executable projection SQL does not match its declared read graph."""


_RELATION = re.compile(
    r"\b(?:from|join)\s+(?:only\s+)?"
    r"(?:(?P<schema>[a-z_][a-z0-9_]*)\s*\.\s*)?"
    r"(?P<table>[a-z_][a-z0-9_]*)\b",
    re.IGNORECASE,
)
_CTE = re.compile(r"\b([a-z_][a-z0-9_]*)\s+as\s*\(", re.IGNORECASE)


def _executable_sql(sql: str) -> str:
    """Remove comments and string bodies while retaining SQL identifiers."""

    output: list[str] = []
    index = 0
    block_depth = 0
    length = len(sql)
    while index < length:
        if block_depth:
            if sql.startswith("/*", index):
                block_depth += 1
                output.extend("  ")
                index += 2
            elif sql.startswith("*/", index):
                block_depth -= 1
                output.extend("  ")
                index += 2
            else:
                output.append("\n" if sql[index] == "\n" else " ")
                index += 1
            continue
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            if end == -1:
                output.extend(" " * (length - index))
                break
            output.extend(" " * (end - index))
            index = end
            continue
        if sql.startswith("/*", index):
            block_depth = 1
            output.extend("  ")
            index += 2
            continue
        char = sql[index]
        if char == "'":
            output.append(" ")
            index += 1
            while index < length:
                output.append("\n" if sql[index] == "\n" else " ")
                if sql[index] == "'":
                    if index + 1 < length and sql[index + 1] == "'":
                        output.append(" ")
                        index += 2
                        continue
                    index += 1
                    break
                index += 1
            continue
        if char == '"':
            index += 1
            identifier: list[str] = []
            while index < length:
                if sql[index] == '"':
                    if index + 1 < length and sql[index + 1] == '"':
                        identifier.append('"')
                        index += 2
                        continue
                    index += 1
                    break
                identifier.append(sql[index])
                index += 1
            output.extend(identifier)
            continue
        if char == "$":
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", sql[index:])
            if match is not None:
                delimiter = match.group(0)
                end = sql.find(delimiter, index + len(delimiter))
                if end != -1:
                    stop = end + len(delimiter)
                    output.extend(
                        "\n" if value == "\n" else " " for value in sql[index:stop]
                    )
                    index = stop
                    continue
        output.append(char)
        index += 1
    return "".join(output)


def executable_public_relations(sql: str) -> frozenset[str]:
    """Return executable base relations referenced by FROM/JOIN clauses.

    Unqualified names are included because PostgreSQL resolves them through the
    connection search path; CTE references are excluded because they are not
    physical authorities.
    """

    executable = _executable_sql(sql)
    ctes = {match.group(1).lower() for match in _CTE.finditer(executable)}
    relations: set[str] = set()
    for match in _RELATION.finditer(executable):
        if re.search(
            r"\bdistinct\s+$",
            executable[max(0, match.start() - 32) : match.start()],
            re.IGNORECASE,
        ):
            continue
        schema = match.group("schema")
        table = match.group("table").lower()
        if schema is None and table in ctes:
            continue
        if schema is None or schema.lower() == "public":
            relations.add(table)
        else:
            relations.add(f"{schema.lower()}.{table}")
    return frozenset(relations)


def assert_executable_read_authority(
    sql: str, *, expected_tables: Iterable[str]
) -> frozenset[str]:
    """Fail closed unless actual executable dependencies equal the declaration."""

    actual = executable_public_relations(sql)
    expected = frozenset(expected_tables)
    if actual != expected:
        raise ConfidenceProjectionAuthorityError(
            f"confidence_projection_read_graph_drift:{sorted(actual)}!={sorted(expected)}"
        )
    return actual
