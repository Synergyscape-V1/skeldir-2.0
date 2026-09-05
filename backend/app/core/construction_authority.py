"""Which database constructions may back a production process.

B2.5-P14 Corrective V, closing H-DU-V-04 / Exit Gate 13.

The repository has two artifacts that describe the schema and exactly one that
*constructs* it:

    alembic/versions/**            the construction authority
    db/schema/canonical_schema.sql a structural reference

One independent audit read the second as a supported production construction
route and failed the phase because a database built from it does not satisfy the
repository's own authority validator. The audit's measurement was correct. The
ontology it measured against was not stated anywhere the audit could check, and
a contract that lives only in a comment is not a contract.

**The determination, and why it follows from the artifact rather than from
preference.** ``canonical_schema.sql`` is produced by
``pg_dump --schema-only --no-owner --no-privileges --no-comments``. Three
consequences follow from the generator, not from policy:

* ``--no-privileges`` means the file has *no vocabulary* for grants or
  ownership. It cannot express the authority graph, so it cannot construct one.
* ``--schema-only`` means it carries no rows, so every content-addressed seed
  (the B2.7 narrative frame corpus and its registry) is absent and B2.7 fails
  closed with ``registry_unknown``.
* ``alembic_version`` is created empty, so a database built this way is at *no
  revision*. ``alembic upgrade head`` against it does not resume; it replays
  from zero and collides with objects that already exist.

Measured on a fresh PostgreSQL 15 at head ``202609061200``, a
canonically-bootstrapped database is not a weaker production database -- it is
not a production database at all:

    alembic_version rows                    0   (Alembic head: 1)
    b27_narrative_templates rows            0   (Alembic head: 20)
    b27_narrative_template_registry rows    0   (Alembic head: 1)
    app_user INSERT on b28 requests      true   (Alembic head: false)
    app_b28_requester INSERT on requests false  (Alembic head: true)
    app_b28_solver INSERT on results    false   (Alembic head: true)
    app_trust_issuer INSERT on issuance false   (Alembic head: true)

The last four are the decisive ones. The canonical route re-grants the generic
API principal the very INSERT this corrective removed, and grants neither
dedicated causal authority anything -- it reconstitutes the defect and disables
the fix. Structurally the two universes agree exactly (128 functions, 172
triggers), which is what makes the file a sound *reference* and an unsound
*construction*.

So the ontology is settled as: **structural reference, never production**. This
module makes that physical rather than conventional. ``alembic_version`` is the
unforgeable marker -- a canonical bootstrap cannot stamp it, because pg_dump
carries no rows -- and a production process refuses to serve a database that
does not carry a revision this repository knows.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS_ROOT = REPOSITORY_ROOT / "alembic" / "versions"
CANONICAL_SCHEMA_PATH = REPOSITORY_ROOT / "db" / "schema" / "canonical_schema.sql"

#: The one construction route that may back a production process.
PRODUCTION_CONSTRUCTION_ROUTE = "alembic"

#: Routes that exist and are deliberately not production-authoritative. The
#: value is why, in the terms an operator would need.
NON_AUTHORITATIVE_CONSTRUCTION_ROUTES: dict[str, str] = {
    "canonical_schema_sql": (
        "db/schema/canonical_schema.sql is a pg_dump --no-owner --no-privileges"
        " structural reference: it cannot express the role graph, carries no"
        " governed seed rows, and stamps no alembic revision"
    ),
}

_REVISION_RE = re.compile(r"^revision\s*=\s*[\"']([0-9A-Za-z_]+)[\"']", re.M)


class ConstructionAuthorityError(RuntimeError):
    """The database was not constructed by the production construction route."""


def known_revisions(migrations_root: Path | None = None) -> frozenset[str]:
    """Every revision identifier the repository's migration history declares."""
    root = migrations_root or MIGRATIONS_ROOT
    found: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        match = _REVISION_RE.search(path.read_text(encoding="utf-8"))
        if match:
            found.add(match.group(1))
    return frozenset(found)


def assert_production_construction_authority(
    observed_revisions: Iterable[Any],
    *,
    migrations_root: Path | None = None,
) -> str:
    """Refuse a database this repository's migrations did not construct.

    ``observed_revisions`` is whatever ``SELECT version_num FROM
    alembic_version`` returned. Three states are refused and each names itself:

    ``no revision``
        the shape a canonical bootstrap produces, and the shape a hand-built or
        partially-restored database produces. Both are structurally plausible
        and neither carries the governed authority graph.

    ``multiple revisions``
        a divergent history; the repository is strictly linear, so this is a
        merge accident rather than a state to serve traffic from.

    ``unknown revision``
        a database ahead of, behind, or beside this deployment's own history.
    """

    revisions = [str(value) for value in observed_revisions if value is not None]
    if not revisions:
        raise ConstructionAuthorityError(
            "database_construction_unauthoritative:no_alembic_revision;"
            " a production database is constructed by "
            f"{PRODUCTION_CONSTRUCTION_ROUTE}. "
            + NON_AUTHORITATIVE_CONSTRUCTION_ROUTES["canonical_schema_sql"]
        )
    if len(revisions) > 1:
        raise ConstructionAuthorityError(
            "database_construction_unauthoritative:multiple_alembic_revisions:"
            + ",".join(sorted(revisions))
        )
    revision = revisions[0]
    known = known_revisions(migrations_root)
    if revision not in known:
        raise ConstructionAuthorityError(
            f"database_construction_unauthoritative:unknown_revision:{revision}"
        )
    return revision


#: The definer function the 202609061200 revision installs. The runtime
#: principal deliberately holds no privilege on ``alembic_version`` -- the
#: baseline revision revokes it and CI re-asserts the revoke -- so the revision
#: is read through a function that exposes the identifiers and nothing else.
CONSTRUCTION_REVISION_FUNCTION = "public.skeldir_database_construction_revisions"


async def read_construction_revisions(connection: Any) -> list[str]:
    """Read the construction revisions a runtime principal is allowed to see.

    The definer function is preferred. A database below ``202609061200`` does
    not have it yet, so the direct read remains as a fallback -- that is not a
    bypass: it reads the same relation by a different route, and a principal
    that can read neither yields no revisions and is refused by the caller.

    Which route to take is decided by *asking the catalog*, not by trying one and
    catching the failure. A failed statement aborts the enclosing transaction in
    PostgreSQL, so an exception-driven fallback would poison the readiness
    transaction it is running inside and report the wrong cause.
    """
    from sqlalchemy import text  # noqa: PLC0415

    probe = await connection.execute(
        text(f"SELECT to_regprocedure('{CONSTRUCTION_REVISION_FUNCTION}()')")
    )
    statement = (
        f"SELECT * FROM {CONSTRUCTION_REVISION_FUNCTION}()"
        if probe.scalar() is not None
        else "SELECT version_num FROM public.alembic_version"
    )
    result = await connection.execute(text(statement))
    return [row[0] for row in result.fetchall()]


async def assert_database_construction_authority(session: Any) -> str:
    """Startup-time refusal, over an async SQLAlchemy session or connection."""
    try:
        rows = await read_construction_revisions(session)
    except Exception as exc:  # pragma: no cover - defensive
        raise ConstructionAuthorityError(
            f"database_construction_unauthoritative:revision_unreadable:{exc}"
        ) from exc
    return assert_production_construction_authority(rows)


__all__ = [
    "CANONICAL_SCHEMA_PATH",
    "CONSTRUCTION_REVISION_FUNCTION",
    "ConstructionAuthorityError",
    "NON_AUTHORITATIVE_CONSTRUCTION_ROUTES",
    "PRODUCTION_CONSTRUCTION_ROUTE",
    "assert_database_construction_authority",
    "assert_production_construction_authority",
    "known_revisions",
    "read_construction_revisions",
]
