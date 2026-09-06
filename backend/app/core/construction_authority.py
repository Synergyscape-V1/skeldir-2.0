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
the fix. Structurally the two universes agree exactly (129 functions, 172
triggers), which is what makes the file a sound *reference* and an unsound
*construction*.

So the ontology is settled as: **structural reference, never production**. This
module makes that physical rather than conventional. ``alembic_version`` is the
unforgeable marker -- a canonical bootstrap cannot stamp it, because pg_dump
carries no rows.

**Corrective VI narrows the second half.** Carrying *a* revision this repository
knows was never the right admission test, and a fresh measurement proved it
admitted the wrong database: the immediate predecessor ``202609051200`` was
accepted as production-ready by the real readiness path, as both the owner and
the runtime principal, while granting ``app_user`` INSERT on every B2.8 relation.
Readiness now requires an *explicitly compatible* revision --
``COMPATIBLE_SCHEMA_REVISIONS``, today exactly ``REQUIRED_SCHEMA_REVISION`` --
and the required revision is asserted equal to the migration graph's own head, so
the contract cannot drift away from the schema it describes.
"""

from __future__ import annotations

import ast
import configparser
import os
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

def _module_revision_identifiers(source: str) -> tuple[str | None, tuple[str, ...]]:
    """Read ``revision`` and ``down_revision`` out of one migration module.

    Parsed rather than pattern-matched, because the repository's 171 migration
    modules declare these four ways -- bare, annotated (``revision: str = ...``),
    tuple-valued for merge revisions, and ``None`` for the root -- and a regex
    that handles one form silently ignores the others. The entering tree's
    ``^revision =`` pattern matched 39 of 171 files, so the "every revision this
    repository knows" set was in fact a small arbitrary subset. That did not make
    a database *more* acceptable, but a predicate whose domain is accidental
    cannot be reasoned about, and Corrective VI needs this one to be exact.
    """

    revision: str | None = None
    parents: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:  # pragma: no cover - a broken migration fails elsewhere
        return None, ()

    def _identifiers(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return [node.value]
        if isinstance(node, (ast.Tuple, ast.List)):
            found: list[str] = []
            for element in node.elts:
                found.extend(_identifiers(element))
            return found
        return []

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            targets = [t.id for t in statement.targets if isinstance(t, ast.Name)]
            value = statement.value
        elif isinstance(statement, ast.AnnAssign) and isinstance(
            statement.target, ast.Name
        ):
            targets = [statement.target.id]
            value = statement.value
        else:
            continue
        if value is None:
            continue
        if "revision" in targets:
            found = _identifiers(value)
            revision = found[0] if found else None
        if "down_revision" in targets:
            parents.extend(_identifiers(value))
    return revision, tuple(parents)


def _chain_directories(migrations_root: Path) -> tuple[Path, ...]:
    """The version directories Alembic itself loads, per ``alembic.ini``.

    ``version_locations`` is the authority for what constitutes the chain, and
    the repository has at least one directory outside it
    (``alembic/versions/005_webhook_secrets``) holding a revision Alembic never
    loads. Scanning the whole tree would therefore report an orphan file as a
    second head and make a linear chain look divergent -- a head computation that
    disagrees with the tool that applies the migrations is worse than none.
    """

    ini = REPOSITORY_ROOT / "alembic.ini"
    if not ini.exists():  # pragma: no cover - defensive
        return (migrations_root,)
    parser = configparser.ConfigParser()
    parser.read(ini, encoding="utf-8")
    declared = parser.get("alembic", "version_locations", fallback="").strip()
    if not declared:
        return (migrations_root,)
    separator = parser.get("alembic", "version_path_separator", fallback=";").strip()
    separator = {"os": os.pathsep, "space": " ", ":": ":", ";": ";"}.get(
        separator, separator or ";"
    )
    directories = [
        (REPOSITORY_ROOT / entry.strip()).resolve()
        for entry in declared.split(separator)
        if entry.strip()
    ]
    return tuple(path for path in directories if path.is_dir()) or (migrations_root,)


def _migration_modules(migrations_root: Path | None = None):
    root = migrations_root or MIGRATIONS_ROOT
    directories = _chain_directories(root) if migrations_root is None else (root,)
    for directory in directories:
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            # `utf-8-sig`, not `utf-8`: at least one migration module carries a
            # BOM, and `ast.parse` refuses a source string that starts with one.
            # Read as plain utf-8 it parsed as a SyntaxError, was silently
            # skipped, and its parent became a phantom second head.
            yield _module_revision_identifiers(path.read_text(encoding="utf-8-sig"))


# ---------------------------------------------------------------------------
# B2.5-P14 Corrective VI, closing H-VI-08 / H-VI-09 / Exit Gate 6.
# ---------------------------------------------------------------------------
# The entering tree accepted any revision string that appeared anywhere under
# `alembic/versions/**`. Measured on a fresh PostgreSQL 15 through the real
# `/health/ready` code path, the immediately preceding revision was accepted as
# production-ready by both `migration_owner` and `app_user`:
#
#     stale_known_202609051200:migration_owner   ACCEPTED revision=202609051200
#     stale_known_202609051200:app_user          ACCEPTED revision=202609051200
#
# A `202609051200` database grants `app_user` INSERT on all three B2.8
# relations, retains no `channel_evidence`, and has no `b28_recompute_allocation`
# -- it is the exact schema whose fabrication surface Corrective V removed. The
# predicate was measuring familiarity, not fitness, which is the
# anti-corroboration trap Directive VI names verbatim:
#
#     revision is somewhere in repository history  ->  ready        REFUSED
#     revision is explicitly compatible with this build  ->  ready  REQUIRED
#
# Skeldir's operational answer is the simple one Directive VI section 13 says to
# prefer when it is sufficient: **exact head**. Every deployment migrates before
# it serves, there is no rolling multi-version window in the design-partner
# topology, and a bounded window would have to be justified by an upgrade
# choreography that does not exist. `COMPATIBLE_SCHEMA_REVISIONS` is the seam a
# future window would widen through, and it is machine-checkable either way:
# `REQUIRED_SCHEMA_REVISION` must equal the head computed from the migration
# graph, and `backend/tests/trust/test_b25_p14_r6_possession_authority.py`
# asserts exactly that -- so the contract cannot drift away from the schema it
# claims to describe.

#: The single Alembic revision this build's code requires. Asserted equal to the
#: migration graph's head by a merge-blocking test; never hand-maintained
#: independently of the chain.
REQUIRED_SCHEMA_REVISION = "202609071200"

#: Every revision a process running this build may serve traffic against.
#: Exactly one today. Widening this set is a deliberate, reviewable act that
#: must come with evidence that the older schema carries every authority control
#: the running code depends on.
COMPATIBLE_SCHEMA_REVISIONS: frozenset[str] = frozenset({REQUIRED_SCHEMA_REVISION})


class ConstructionAuthorityError(RuntimeError):
    """The database was not constructed by the production construction route."""


def known_revisions(migrations_root: Path | None = None) -> frozenset[str]:
    """Every revision identifier the repository's migration history declares.

    Retained because "is this revision one of ours at all?" and "may this build
    serve it?" are different questions with different answers, and an operator
    reading a refusal needs to know which one fired. It is no longer the
    admission predicate.
    """
    return frozenset(
        revision
        for revision, _parents in _migration_modules(migrations_root)
        if revision
    )


def migration_graph_head(migrations_root: Path | None = None) -> str:
    """The single head of the repository's migration graph.

    Computed from the graph rather than declared, so ``REQUIRED_SCHEMA_REVISION``
    can be *checked* rather than trusted: a merge-blocking test asserts they are
    equal, and a head that moved without the contract moving turns that test red.
    More than one head means a divergent history, over which a compatibility
    contract has no meaning -- so this raises rather than picking one.
    """
    revisions: set[str] = set()
    parents: set[str] = set()
    for revision, module_parents in _migration_modules(migrations_root):
        if not revision:
            continue
        revisions.add(revision)
        parents.update(module_parents)
    heads = sorted(revisions - parents)
    if len(heads) != 1:
        raise ConstructionAuthorityError(
            "database_construction_unauthoritative:migration_chain_not_linear:"
            + ",".join(heads)
        )
    return heads[0]


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
        a database beside this deployment's own history entirely -- ahead of it,
        or from another repository.

    ``incompatible revision``
        a revision this repository does know, and this build may not run
        against. Corrective VI: recognising a revision is not the same as being
        able to serve it. ``202609051200`` is known, structurally plausible, and
        grants the generic API principal INSERT on every B2.8 relation; a
        Corrective-VI process on that schema would reconstitute the exact
        fabrication surface two audits exploited.
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
    if revision not in COMPATIBLE_SCHEMA_REVISIONS:
        raise ConstructionAuthorityError(
            "database_construction_unauthoritative:incompatible_revision:"
            f"{revision};this build requires "
            + ",".join(sorted(COMPATIBLE_SCHEMA_REVISIONS))
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
    "COMPATIBLE_SCHEMA_REVISIONS",
    "CONSTRUCTION_REVISION_FUNCTION",
    "ConstructionAuthorityError",
    "NON_AUTHORITATIVE_CONSTRUCTION_ROUTES",
    "PRODUCTION_CONSTRUCTION_ROUTE",
    "REQUIRED_SCHEMA_REVISION",
    "assert_database_construction_authority",
    "assert_production_construction_authority",
    "known_revisions",
    "migration_graph_head",
    "read_construction_revisions",
]
