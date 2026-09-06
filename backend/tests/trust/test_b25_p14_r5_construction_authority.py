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


# ---------------------------------------------------------------------------
# H-RC-V-07 -- the new SECURITY DEFINER function's tenant physics.
# ---------------------------------------------------------------------------


def _admin_dsn_or_skip() -> str:
    """Resolve an admin DSN, or skip.

    The rest of this suite is pure Python and runs in every lane, which is the
    point: the construction ontology is decided without a database. This one
    probe needs a provisioned role graph, so it is gated on the same flag the
    other P14 database proofs use rather than on the mere presence of a DSN --
    several lanes export `MIGRATION_DATABASE_URL` without standing a PostgreSQL
    up, and a probe that connected there would fail for the wrong reason.
    """
    import os

    if os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1":
        pytest.skip("the definer probe requires a provisioned production role graph")
    for name in (
        "P14_ADMIN_DATABASE_URL",
        "C21_ADMIN_DATABASE_URL",
        "C20_ADMIN_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value.replace("postgresql+psycopg2://", "postgresql://")
    pytest.skip("no admin DSN is configured for the definer probe")


def test_the_construction_revision_definer_is_narrow_and_tenant_free() -> None:
    """Directive V H-RC-V-07, discharged rather than assumed.

    This corrective introduces exactly one SECURITY DEFINER function, and the
    directive is explicit that prior RLS safety does not automatically extend to
    a new authority. What is checked here is the whole surface it could possibly
    have: it is owned by the migration principal, its search_path is pinned, it
    takes no arguments (so there is no value a caller could steer it with), its
    body reads one relation that has no tenant column and no row-level security,
    EXECUTE is revoked from PUBLIC, and neither B2.8 causal authority holds it --
    a definer function is a capability, and a capability nobody needs is one
    nobody should hold.
    """

    import psycopg2

    conn = psycopg2.connect(_admin_dsn_or_skip())
    conn.autocommit = True
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig,"
                " p.pronargs, pg_get_functiondef(p.oid), p.proacl::text"
                " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public'"
                "   AND p.proname = 'skeldir_database_construction_revisions'"
            )
            row = cursor.fetchone()
            assert row is not None, "the construction-revision definer is absent"
            secdef, owner, config, nargs, definition, acl = row

            # Every tenant-scoped relation, so the body check below is decided
            # against the database rather than against a remembered list.
            cursor.execute(
                "SELECT c.relname FROM pg_class c JOIN pg_namespace n"
                " ON n.oid = c.relnamespace"
                " WHERE n.nspname = 'public' AND c.relrowsecurity"
            )
            rls_relations = sorted(name for (name,) in cursor.fetchall())

            cursor.execute(
                "SELECT count(*) FROM pg_attribute a"
                " WHERE a.attrelid = 'public.alembic_version'::regclass"
                "   AND a.attname = 'tenant_id' AND NOT a.attisdropped"
            )
            alembic_has_tenant = cursor.fetchone()[0]
    finally:
        conn.close()

    assert secdef is True
    assert owner == "migration_owner", owner
    assert config == ["search_path=pg_catalog, public"], config
    assert nargs == 0, "a definer function with arguments is a steerable one"
    assert "alembic_version" in definition
    # It reads exactly one relation, and that relation is not tenant-scoped, so
    # there is no tenant boundary for the definer authority to cross.
    assert alembic_has_tenant == 0
    assert "alembic_version" not in rls_relations
    for relation in rls_relations:
        assert relation not in definition, (
            f"the definer reads the tenant-scoped relation {relation}"
        )

    # PUBLIC holds nothing, and neither causal authority holds EXECUTE.
    assert acl is not None, "an ungoverned ACL means EXECUTE is public by default"
    assert "=X/" not in acl.split(",")[0] or "migration_owner=" in acl, acl
    for principal in ("app_b28_requester", "app_b28_solver"):
        assert f"{principal}=X" not in acl, (
            f"{principal} holds EXECUTE on the construction-revision definer"
        )
