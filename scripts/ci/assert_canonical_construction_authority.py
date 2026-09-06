#!/usr/bin/env python3
"""B2.5-P14 Corrective V, Exit Gate 13: one definition of a production database.

Directive V §10.1 offers exactly two ways to end the canonical-construction
argument. Either the canonical bootstrap is production-authoritative, in which
case it must satisfy the *full* authority-equivalence contract, or it is
formally non-authoritative, in which case::

    production cannot select it
    CI does not present it as equivalent
    runbooks do not call it authoritative
    validators encode the narrower contract

and, explicitly, "do not merely weaken the validator to erase the difference".

The repository's answer is the second, and it follows from the artifact rather
than from preference: ``db/schema/canonical_schema.sql`` is produced by
``pg_dump --schema-only --no-owner --no-privileges``, so it has no vocabulary
for grants or ownership, carries no governed seed rows, and stamps no Alembic
revision. This gate makes that determination falsifiable instead of declared. It
does four things, in order, on a real PostgreSQL:

1.  **The reference is sound.** The canonical artifact loads *exactly as
    pg_dump emits it* -- no reordering, no flags of our own -- and the resulting
    structure matches the Alembic head on functions, triggers, constraints, RLS
    and columns. A structural reference that does not describe the schema is
    worthless, so this is the gate's positive control.

2.  **The reference is not a construction.** The authority divergences are
    *required to be present and are enumerated*. If a canonical database ever
    silently acquires a governed role graph, this gate goes red -- because that
    would mean the two routes had quietly become interchangeable again, which is
    the ambiguity the phase is closing.

3.  **Production refuses it.** ``assert_production_construction_authority``
    rejects the empty ``alembic_version`` a canonical bootstrap leaves behind,
    and accepts the migrated head. The marker is unforgeable by construction:
    pg_dump carries no rows, so no canonical bootstrap can stamp a revision.

4.  **Nothing can select it by accident.** Every production construction
    surface -- compose files, Dockerfiles, entrypoints, Procfile, deployment
    workflows -- is scanned for a reference to the canonical artifact, and any
    hit outside the declared drift-detection allowlist fails the gate.

Run with ``--negative-control`` to prove the gate is load-bearing rather than
decorative: it asserts the checks fail on a deliberately broken input.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import psycopg2

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.core.construction_authority import (  # noqa: E402
    ConstructionAuthorityError,
    assert_production_construction_authority,
    known_revisions,
)

CANONICAL_RELATIVE = "db/schema/canonical_schema.sql"

# Files that are allowed to name the canonical artifact, and why. Every one of
# these reads it as a *reference*: to detect drift, to compare structure, or to
# document the posture. None of them constructs a database a process will serve.
REFERENCE_ALLOWLIST: dict[str, str] = {
    ".github/workflows/schema-validation.yml": "drift detection and its negative control",
    ".github/workflows/schema-drift-check.yml": "drift detection",
    ".github/workflows/ci.yml": "drift detection",
    ".github/workflows/b2_5-p13-e2e-trust-closure.yml": (
        "drift detection and the structural-reference comparison"
    ),
    ".github/workflows/r1-contract-runtime.yml": (
        "ephemeral contract-runtime fixture; not a deployed database"
    ),
    ".github/workflows/r2-data-truth-hardening.yml": (
        "ephemeral data-truth fixture; not a deployed database"
    ),
    "scripts/schema/assert_canonical_schema.py": "the drift detector itself",
    "scripts/ci/assert_canonical_construction_authority.py": "this gate",
    "backend/app/core/construction_authority.py": "the runtime refusal",
    "backend/tests/trust/test_b25_p14_r5_construction_authority.py": "this gate's suite",
}

# Surfaces that would actually construct a database a process then serves. A
# reference to the canonical artifact in any of these is the failure this gate
# exists to catch.
PRODUCTION_CONSTRUCTION_GLOBS = (
    "docker-compose*.yml",
    "Procfile",
    "backend/Dockerfile*",
    "backend/*.sh",
    "backend/scripts/**/*.sh",
    "backend/scripts/**/*.py",
    "infra/**/*",
    "scripts/database/**/*",
    "scripts/deploy/**/*",
    ".github/workflows/*deploy*.yml",
    ".github/workflows/*production*.yml",
)

# The authority divergences that make the canonical route non-constructive.
# Each is `(label, sql, canonical_expectation, alembic_expectation)`.
AUTHORITY_PROBES: tuple[tuple[str, str, Any, Any], ...] = (
    (
        "alembic_revision_rows",
        "SELECT count(*) FROM public.alembic_version",
        0,
        1,
    ),
    (
        "narrative_frame_rows",
        "SELECT count(*) FROM public.b27_narrative_templates",
        0,
        20,
    ),
    (
        "narrative_registry_rows",
        "SELECT count(*) FROM public.b27_narrative_template_registry",
        0,
        1,
    ),
    (
        "app_user_may_insert_b28_requests",
        "SELECT has_table_privilege('app_user',"
        " 'public.b28_simulation_requests', 'INSERT')",
        True,
        False,
    ),
    (
        "b28_requester_may_insert_requests",
        "SELECT has_table_privilege('app_b28_requester',"
        " 'public.b28_simulation_requests', 'INSERT')",
        False,
        True,
    ),
    (
        "b28_solver_may_insert_results",
        "SELECT has_table_privilege('app_b28_solver',"
        " 'public.b28_simulation_results', 'INSERT')",
        False,
        True,
    ),
    (
        "issuer_may_append_issuance_history",
        "SELECT has_table_privilege('app_trust_issuer',"
        " 'public.trust_envelope_issuance_log', 'INSERT')",
        False,
        True,
    ),
)

# The structural dimensions that must agree, because a reference that does not
# describe the schema is not a reference.
STRUCTURAL_PROBES: tuple[tuple[str, str], ...] = (
    (
        "functions",
        "SELECT count(*) FROM pg_proc p JOIN pg_namespace n"
        " ON n.oid = p.pronamespace WHERE n.nspname IN ('public','auth','security')",
    ),
    ("triggers", "SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal"),
    (
        "check_constraints",
        "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n"
        " ON n.oid = c.connamespace WHERE n.nspname = 'public'",
    ),
    ("rls_policies", "SELECT count(*) FROM pg_policy"),
    (
        "forced_rls_relations",
        "SELECT count(*) FROM pg_class WHERE relforcerowsecurity",
    ),
    (
        "columns",
        "SELECT count(*) FROM information_schema.columns"
        " WHERE table_schema IN ('public','auth','security')",
    ),
)


def _print(message: str) -> None:
    print(f"[p14-construction] {message}")


def _scalar(dsn: str, statement: str) -> Any:
    with psycopg2.connect(dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchone()[0]


def check_structural_reference_is_sound(
    alembic_dsn: str, canonical_dsn: str
) -> tuple[list[str], dict[str, Any]]:
    """1. The reference describes the schema the migrations produce."""
    violations: list[str] = []
    evidence: dict[str, Any] = {}
    for label, statement in STRUCTURAL_PROBES:
        migrated = _scalar(alembic_dsn, statement)
        canonical = _scalar(canonical_dsn, statement)
        evidence[label] = {"alembic": migrated, "canonical": canonical}
        if migrated != canonical:
            violations.append(
                f"structural reference diverges on {label}:"
                f" alembic={migrated} canonical={canonical}"
            )
    return violations, evidence


def check_reference_is_not_a_construction(
    alembic_dsn: str, canonical_dsn: str
) -> tuple[list[str], dict[str, Any]]:
    """2. The authority divergences are present, enumerated, and required."""
    violations: list[str] = []
    evidence: dict[str, Any] = {}
    for label, statement, expect_canonical, expect_alembic in AUTHORITY_PROBES:
        migrated = _scalar(alembic_dsn, statement)
        canonical = _scalar(canonical_dsn, statement)
        evidence[label] = {"alembic": migrated, "canonical": canonical}
        if migrated != expect_alembic:
            violations.append(
                f"the production construction route no longer satisfies {label}:"
                f" expected {expect_alembic}, observed {migrated}"
            )
        if canonical != expect_canonical:
            violations.append(
                f"the structural reference's declared non-authority changed at"
                f" {label}: expected {expect_canonical}, observed {canonical}."
                " Either it has quietly become constructive, or this gate's"
                " enumeration is stale; both need a decision, not a green tick"
            )
    return violations, evidence


def check_production_refuses_the_reference(
    alembic_dsn: str, canonical_dsn: str
) -> tuple[list[str], dict[str, Any]]:
    """3. A process refuses to serve the canonically-built database."""
    violations: list[str] = []
    evidence: dict[str, Any] = {}

    with psycopg2.connect(canonical_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM public.alembic_version")
            canonical_revisions = [row[0] for row in cursor.fetchall()]
    evidence["canonical_revisions"] = canonical_revisions
    try:
        assert_production_construction_authority(canonical_revisions)
        violations.append(
            "the runtime accepted a canonically-constructed database;"
            " 'production cannot select it' is not physically true"
        )
        evidence["canonical_refusal"] = None
    except ConstructionAuthorityError as exc:
        evidence["canonical_refusal"] = str(exc)

    with psycopg2.connect(alembic_dsn) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version_num FROM public.alembic_version")
            migrated_revisions = [row[0] for row in cursor.fetchall()]
    evidence["alembic_revisions"] = migrated_revisions
    try:
        evidence["accepted_revision"] = assert_production_construction_authority(
            migrated_revisions
        )
    except ConstructionAuthorityError as exc:
        violations.append(
            f"the runtime refused a lawfully migrated database: {exc}"
        )
    evidence["known_revision_count"] = len(known_revisions())
    return violations, evidence


def check_no_production_surface_selects_it() -> tuple[list[str], dict[str, Any]]:
    """4. Nothing that constructs a served database names the artifact."""
    violations: list[str] = []
    hits: list[str] = []
    for pattern in PRODUCTION_CONSTRUCTION_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            if relative in REFERENCE_ALLOWLIST:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if CANONICAL_RELATIVE in text or "canonical_schema.sql" in text:
                hits.append(relative)
                violations.append(
                    f"{relative} names the structural reference; a production"
                    " construction surface may not select it"
                )
    return violations, {"production_surface_hits": hits}


def run_negative_control() -> int:
    """Prove the checks are load-bearing without touching a real database."""
    failures: list[str] = []

    # 3's falsifier: an empty revision set must be refused, and an invented one
    # must be refused for a different, named reason.
    try:
        assert_production_construction_authority([])
        failures.append("an unconstructed database was accepted")
    except ConstructionAuthorityError as exc:
        if "no_alembic_revision" not in str(exc):
            failures.append(f"wrong refusal for an unconstructed database: {exc}")
    try:
        assert_production_construction_authority(["9999999999999"])
        failures.append("an unknown revision was accepted")
    except ConstructionAuthorityError as exc:
        if "unknown_revision" not in str(exc):
            failures.append(f"wrong refusal for an unknown revision: {exc}")
    try:
        assert_production_construction_authority(["202609061200", "202609051200"])
        failures.append("a divergent history was accepted")
    except ConstructionAuthorityError as exc:
        if "multiple_alembic_revisions" not in str(exc):
            failures.append(f"wrong refusal for a divergent history: {exc}")

    # 4's falsifier: a production surface that names the artifact must be seen.
    probe = REPO_ROOT / "docker-compose.p14-construction-negative-control.yml"
    probe.write_text(
        "# negative control\nservices:\n  db:\n    command: psql -f"
        " db/schema/canonical_schema.sql\n",
        encoding="utf-8",
    )
    try:
        violations, _ = check_no_production_surface_selects_it()
        if not any("negative-control" in item for item in violations):
            failures.append(
                "a compose file that constructs from the reference was not seen"
            )
    finally:
        probe.unlink(missing_ok=True)

    residual, _ = check_no_production_surface_selects_it()
    if residual:
        failures.append(f"the negative control did not restore cleanly: {residual}")

    if failures:
        for failure in failures:
            _print(f"NEGATIVE CONTROL FAILED: {failure}")
        return 1
    _print("negative control fired on every check")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alembic-dsn", default="")
    parser.add_argument("--canonical-dsn", default="")
    parser.add_argument("--evidence-out", default="")
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()

    if args.negative_control:
        return run_negative_control()

    if not args.alembic_dsn or not args.canonical_dsn:
        _print("ERROR: --alembic-dsn and --canonical-dsn are required")
        return 2

    checks = [
        (
            "structural_reference_is_sound",
            lambda: check_structural_reference_is_sound(
                args.alembic_dsn, args.canonical_dsn
            ),
        ),
        (
            "reference_is_not_a_construction",
            lambda: check_reference_is_not_a_construction(
                args.alembic_dsn, args.canonical_dsn
            ),
        ),
        (
            "production_refuses_the_reference",
            lambda: check_production_refuses_the_reference(
                args.alembic_dsn, args.canonical_dsn
            ),
        ),
        ("no_production_surface_selects_it", check_no_production_surface_selects_it),
    ]

    evidence: dict[str, Any] = {
        "construction_ontology": "canonical_schema.sql is a structural reference"
        " and is never a production construction route",
    }
    failed = False
    for name, run in checks:
        violations, detail = run()
        evidence[name] = {"status": "FAIL" if violations else "PASS", **detail}
        if violations:
            failed = True
            _print(f"{name}=FAIL")
            for violation in violations:
                _print(f"  {violation}")
        else:
            _print(f"{name}=PASS")

    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
        _print(f"wrote evidence: {out}")

    if failed:
        _print("canonical construction authority FAILED")
        return 1
    _print("canonical construction authority PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
