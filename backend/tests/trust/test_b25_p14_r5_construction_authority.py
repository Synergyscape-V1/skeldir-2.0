"""B2.5-P14 Corrective V Exit Gate 13 -- one definition of a production database.

An independent audit failed the phase on Gate M because a database built through
``db/schema/canonical_schema.sql`` does not satisfy the repository's own
authority validator. The measurement was right. What was missing was a stated,
checkable ontology: the repository treated the artifact as a structural
reference (its comparator says so, its CI passes ``--structural-only``) while
nothing prevented a reader -- or a deployment -- from treating it as a supported
construction route.

Directive V §10.1 gives two ways to end that: make it authoritative and fully
equivalent, or make it formally non-authoritative and enforce that physically.
The repository's answer is the second, and it follows from the artifact rather
than from preference -- ``pg_dump --schema-only --no-owner --no-privileges`` has
no vocabulary for grants, no rows to seed, and stamps no revision.

This suite decides the application half. ``scripts/ci/assert_canonical_
construction_authority.py`` decides the database half against two real
universes, and its own negative control is exercised here so the gate cannot
pass by being decorative.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.core.construction_authority import (
    CANONICAL_SCHEMA_PATH,
    NON_AUTHORITATIVE_CONSTRUCTION_ROUTES,
    PRODUCTION_CONSTRUCTION_ROUTE,
    ConstructionAuthorityError,
    assert_production_construction_authority,
    known_revisions,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_the_migration_history_is_the_only_production_construction_route() -> None:
    assert PRODUCTION_CONSTRUCTION_ROUTE == "alembic"
    assert "canonical_schema_sql" in NON_AUTHORITATIVE_CONSTRUCTION_ROUTES
    reason = NON_AUTHORITATIVE_CONSTRUCTION_ROUTES["canonical_schema_sql"]
    # The reason has to name the physics, not the preference: an operator
    # reading the refusal must be able to check the claim themselves.
    assert "--no-privileges" in reason
    assert "no governed seed rows" in reason
    assert "stamps no alembic revision" in reason


def test_an_unconstructed_database_is_refused_by_name() -> None:
    """The shape a canonical bootstrap leaves behind: no revision at all."""
    with pytest.raises(ConstructionAuthorityError) as exc:
        assert_production_construction_authority([])
    assert "no_alembic_revision" in str(exc.value)
    # The refusal explains what a production database *is*, because the operator
    # who sees it is one command away from fixing it.
    assert "alembic" in str(exc.value)


def test_a_divergent_or_foreign_history_is_refused_by_name() -> None:
    with pytest.raises(ConstructionAuthorityError) as multiple:
        assert_production_construction_authority(["202609061200", "202609051200"])
    assert "multiple_alembic_revisions" in str(multiple.value)

    with pytest.raises(ConstructionAuthorityError) as unknown:
        assert_production_construction_authority(["999912311200"])
    assert "unknown_revision" in str(unknown.value)


def test_the_current_head_is_accepted() -> None:
    revisions = known_revisions()
    assert "202609061200" in revisions, "the Corrective V revision is not declared"
    assert "202609051200" in revisions
    assert assert_production_construction_authority(["202609061200"]) == "202609061200"


def test_the_structural_reference_still_exists_and_is_a_pg_dump_artifact() -> None:
    """A reference that stopped being a pg_dump would have stopped being one.

    The whole determination rests on how the file is generated: change the
    generator and the reasoning about privileges, seeds and revisions no longer
    holds. The preamble is therefore checked, not assumed -- including
    ``check_function_bodies``, whose presence is why the artifact loads in
    dependency-free order without any flag of the loader's own.
    """
    assert CANONICAL_SCHEMA_PATH.exists()
    head = CANONICAL_SCHEMA_PATH.read_text(encoding="utf-8", errors="replace")[:4000]
    assert "PostgreSQL database dump" in head
    assert "SET check_function_bodies = false;" in head
    assert "Dumped by pg_dump" in head


def test_no_production_construction_surface_selects_the_reference() -> None:
    """Gate 13's institutional half, executed rather than asserted."""
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/ci/assert_canonical_construction_authority.py"),
            "--negative-control",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "negative control fired on every check" in result.stdout
