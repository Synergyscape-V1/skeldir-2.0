#!/usr/bin/env python3
"""Assert every durable B2.8 field declares what it is and what makes it true.

B2.5-P14 Corrective VI, discharging Directive VI §15 and supporting Exit Gate 3.

§15 requires each durable field to be classified as exactly one of::

    DERIVED VALUE
    OBSERVED EVENT
    AUTHORITY IDENTITY
    PROVENANCE REFERENCE

and, for each, an answer to "what physical evidence makes this field true?".

The entering tree answered neither. Measured live, every ``b28_*`` column
comment was ``NULL``, and the one field whose name made a claim --
``solver_invocations integer NOT NULL`` -- claimed an execution event the
database has no witness for. An audit inserted an independently recomputed
allocation with ``solver_invocations = 1``, having never invoked the solver, and
the row was accepted.

The repair is not a document. It is a column comment on every field, checked
here against the live catalog, so:

* a new column that says nothing about itself is merge-blocking;
* a column whose classification is not one of the four is merge-blocking;
* ``solver_consequence_kind`` in particular must keep saying both halves of its
  meaning -- what it asserts, and what it explicitly does not.

The migration is the source of truth for the text
(``FIELD_SEMANTICS`` in ``202609071200``); this script proves the database
actually carries it, which is the difference between a plan and a schema.

Usage::

    python scripts/ci/assert_b25_p14_field_semantics.py \\
        --database-url postgresql://... [--evidence-out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2


REPO_ROOT = Path(__file__).resolve().parents[2]

CLASSIFICATIONS = frozenset(
    {
        "DERIVED VALUE",
        "OBSERVED EVENT",
        "AUTHORITY IDENTITY",
        "PROVENANCE REFERENCE",
    }
)

RELATIONS = (
    "b28_request_authentications",
    "b28_simulation_requests",
    "b28_simulation_results",
    "b28_proposals",
)

#: A field whose evidence sentence is shorter than this is not an answer to
#: "what makes it true"; it is a label.
MIN_EVIDENCE_CHARS = 20

#: Columns the schema must NOT carry, with the reason. An event claim the
#: database cannot witness is worse than no claim: it is a false one.
FORBIDDEN_COLUMNS = {
    ("b28_simulation_results", "solver_invocations"): (
        "an execution-event count with no witness. Corrective VI replaced it"
        " with solver_consequence_kind, which states the extensional property"
        " b28_recompute_allocation actually verifies"
    ),
}

#: Phrases the solver field's comment must carry, so the honest half cannot be
#: quietly trimmed back into an execution claim.
SOLVER_COMMENT_REQUIREMENTS = (
    "DERIVED VALUE.",
    "b28_recompute_allocation",
    "NOT a claim",
)


def _database_url(explicit: str) -> str:
    """Resolve the target from the argument alone.

    Deliberately no environment fallback. The B1.1-P4 DSN-callsite scan forbids
    an enforcer reaching for `DATABASE_URL` or `MIGRATION_DATABASE_URL` out of
    the ambient environment, and it is right to: a gate that silently picks up
    whatever credentials happen to be exported can report on a database nobody
    intended it to read. The caller names the universe.
    """

    if not explicit:
        raise SystemExit(
            "[b25-p14-fields] --database-url is required; this gate does not read"
            " ambient database credentials"
        )
    return explicit.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default="", required=True)
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    failures: list[str] = []
    classified: dict[str, dict[str, str]] = {}
    counts: dict[str, int] = {name: 0 for name in sorted(CLASSIFICATIONS)}

    connection = psycopg2.connect(_database_url(args.database_url))
    try:
        with connection.cursor() as cursor:
            for relation in RELATIONS:
                cursor.execute(
                    "SELECT to_regclass(%s)", (f"public.{relation}",)
                )
                if cursor.fetchone()[0] is None:
                    failures.append(f"relation public.{relation} does not exist")
                    continue
                cursor.execute(
                    "SELECT a.attname, col_description(a.attrelid, a.attnum)"
                    "  FROM pg_attribute a"
                    " WHERE a.attrelid = %s::regclass"
                    "   AND a.attnum > 0 AND NOT a.attisdropped"
                    " ORDER BY a.attnum",
                    (f"public.{relation}",),
                )
                rows = cursor.fetchall()
                if not rows:
                    failures.append(f"relation public.{relation} has no columns")
                    continue
                classified[relation] = {}
                for column, comment in rows:
                    forbidden = FORBIDDEN_COLUMNS.get((relation, column))
                    if forbidden:
                        failures.append(
                            f"{relation}.{column} exists again: {forbidden}"
                        )
                        continue
                    if not comment:
                        failures.append(
                            f"{relation}.{column} carries no field-semantics"
                            " comment; Directive VI section 15 requires every"
                            " durable field to declare what it is"
                        )
                        continue
                    head, _, evidence = comment.partition(".")
                    classification = head.strip()
                    if classification not in CLASSIFICATIONS:
                        failures.append(
                            f"{relation}.{column} declares {classification!r},"
                            f" which is not one of {sorted(CLASSIFICATIONS)}"
                        )
                        continue
                    if len(evidence.strip()) < MIN_EVIDENCE_CHARS:
                        failures.append(
                            f"{relation}.{column} names a classification but no"
                            " evidence for it"
                        )
                        continue
                    classified[relation][column] = classification
                    counts[classification] += 1

            cursor.execute(
                "SELECT col_description('public.b28_simulation_results'::regclass,"
                " (SELECT attnum FROM pg_attribute"
                "   WHERE attrelid = 'public.b28_simulation_results'::regclass"
                "     AND attname = 'solver_consequence_kind'"
                "     AND NOT attisdropped))"
            )
            row = cursor.fetchone()
            solver_comment = row[0] if row else None
            if not solver_comment:
                failures.append(
                    "b28_simulation_results.solver_consequence_kind has no"
                    " comment; the field whose predecessor overstated its"
                    " evidence must state exactly what it means"
                )
            else:
                for phrase in SOLVER_COMMENT_REQUIREMENTS:
                    if phrase not in solver_comment:
                        failures.append(
                            "solver_consequence_kind comment no longer carries"
                            f" {phrase!r}"
                        )
    finally:
        connection.close()

    empty = [name for name, total in counts.items() if total == 0]
    if empty:
        failures.append(
            "these classifications are declared but unused: "
            + ", ".join(sorted(empty))
            + " -- a taxonomy nobody applied is not a classification"
        )

    evidence_pack = {
        "relations": RELATIONS,
        "classification_counts": counts,
        "classified": classified,
        "failures": failures,
    }
    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(evidence_pack, indent=2, sort_keys=True), encoding="utf-8"
        )

    for name in sorted(counts):
        print(f"[b25-p14-fields] {name:22s} {counts[name]}")
    total = sum(counts.values())
    print(f"[b25-p14-fields] classified_columns={total}")

    if failures:
        for failure in failures:
            print(f"[b25-p14-fields] FAIL: {failure}", file=sys.stderr)
        return 1
    print("[b25-p14] field semantics PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
