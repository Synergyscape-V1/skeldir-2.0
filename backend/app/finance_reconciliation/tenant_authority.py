"""B2.6-P1 transaction-bound tenant authority (Corrective V).

Defect class closed here
------------------------

Database visibility authority and financial scope authority were two
independent inputs: the database session carried one tenant (the PostgreSQL
``app.current_tenant_id`` setting) while the financial query carried another
(the ``tenant_id`` parameter). Their divergence was silent: row-level
security hid the requested tenant, ``COALESCE`` turned invisibility into
zero, and a canonical-looking ``0/0`` value was returned for a tenant the
caller was never authorized to see.

Class-closure theorem
---------------------

Canonical financial scope and transaction-bound database tenant authority
are one machine-enforced identity before any aggregate can be accepted:
every canonical derivation observes the sovereign PostgreSQL setting
``current_setting('app.current_tenant_id', true)`` on the same connection
that will run the aggregation and refuses -- before aggregation -- unless
it is present and equal to the requested scope tenant. Authorization
failure therefore fails closed; it can never collapse into governed zero.

Sovereign sources composed (never reimplemented)
------------------------------------------------

* PostgreSQL ``current_setting`` / ``current_user`` / ``current_database``
  observed directly on the live session (the tenant-authority oracle is the
  database itself, not a caller variable).
* The production session factories in ``app.db.session`` (imported locally
  so this module stays import-light and never creates engines itself).
* The governed least-privilege principals are the existing production
  logins; no new role is created for naming aesthetics.

What this module does NOT do
----------------------------

* No new table, migration, trigger, or role (read-only authority path;
  durable state needs none of these).
* No ``SECURITY DEFINER`` function (an app-layer observer of sovereign
  PostgreSQL state, combined with framework-owned session acquisition in
  ``canonical_sink``, closes the class without enlarging authority).
* Deployment database selection (``DATABASE_URL``) stays in the trusted
  deployment plane: this module never accepts URLs, engines, or factories
  from request code. The framework owns capability acquisition; ordinary
  code cannot inject a session into the canonical path because the
  canonical path takes no session parameter at all.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, AsyncIterator, Mapping
from uuid import UUID

from sqlalchemy import text

if TYPE_CHECKING:  # Import-time light: never create engines on import.
    from sqlalchemy.ext.asyncio import AsyncSession


TENANT_GUC_NAME = "app.current_tenant_id"

# Governed least-privilege production principals for canonical derivation.
# migration_owner (DDL ownership) and every other login are refused on the
# canonical path even though they can resolve the same SQL: authority is
# the principal, not the query text.
GOVERNED_CANONICAL_PRINCIPALS = frozenset({"app_user", "app_worker"})

TENANT_AUTHORITY_MODE = "transaction_bound_db_tenant_equals_scope_tenant"
DATABASE_CAPABILITY_MODE = "framework_owned_governed_session_factory_only"


class TenantAuthorityError(ValueError):
    """Database tenant authority is missing, mismatched, or ungoverned."""


class MissingTenantAuthorityError(TenantAuthorityError):
    """No transaction-bound tenant authority is present."""


class TenantAuthorityMismatchError(TenantAuthorityError):
    """Transaction-bound tenant authority differs from the requested scope."""


class CanonicalPrincipalError(TenantAuthorityError):
    """The database principal is not a governed canonical principal."""


class UnknownTenantError(TenantAuthorityError):
    """The authenticated tenant has no durable tenant row.

    Absence of a tenant row is authorization failure, never governed zero:
    a canonical ``0/0`` value is lawful only for an existing tenant whose
    sovereign B2.3 legs are both zero.
    """


async def read_db_authority(session: AsyncSession) -> Mapping[str, Any]:
    """Observe sovereign database authority directly on the live session.

    Returns the principal, database, and transaction-bound tenant setting as
    PostgreSQL itself reports them. A missing setting yields ``None`` (never
    an empty canonical claim).
    """
    row = (
        (
            await session.execute(
                text(
                    "SELECT current_user AS principal,"
                    " current_database() AS database_name,"
                    " current_setting('app.current_tenant_id', true)"
                    " AS tenant_guc"
                )
            )
        )
        .mappings()
        .one()
    )
    return {
        "principal": str(row["principal"]),
        "database_name": str(row["database_name"]),
        "tenant_guc": (None if row["tenant_guc"] is None else str(row["tenant_guc"])),
    }


async def assert_tenant_authority(
    session: AsyncSession, tenant_id: UUID | str
) -> Mapping[str, Any]:
    """Require one enforced tenant identity before financial aggregation.

    Refuses, in order: ungoverned principal, missing transaction authority,
    and scope/authority divergence. Returns the observed authority on
    success. Raises before any aggregate SQL may run, so refusal can never
    be reinterpreted as a zero-valued financial result downstream.
    """
    requested = str(tenant_id).strip()
    if not requested:
        raise MissingTenantAuthorityError(
            "canonical_scope_tenant_missing_before_aggregation"
        )
    authority = await read_db_authority(session)
    principal = str(authority["principal"])
    if principal not in GOVERNED_CANONICAL_PRINCIPALS:
        raise CanonicalPrincipalError(f"canonical_principal_not_governed:{principal}")
    tenant_guc = authority["tenant_guc"]
    if tenant_guc is None or not str(tenant_guc).strip():
        raise MissingTenantAuthorityError(
            "transaction_tenant_authority_missing_before_aggregation"
        )
    if str(tenant_guc).strip() != requested:
        raise TenantAuthorityMismatchError(
            "transaction_tenant_differs_from_canonical_scope:"
            f"db={tenant_guc}:scope={requested}"
        )
    return authority


@asynccontextmanager
async def open_governed_b23_session(
    tenant_id: UUID,
) -> AsyncIterator[AsyncSession]:
    """Open the framework-owned governed database capability for one tenant.

    The canonical consumer never accepts a caller-supplied session: it
    acquires its own capability through the approved production session
    factory bound to the server-derived scope tenant, verifies the
    transaction-local binding immediately, yields it for exactly one
    sovereign derivation, and re-verifies the binding on close so a
    mid-transaction authority switch fails closed instead of silently
    re-scoping the next statement.
    """
    if tenant_id is None or not str(tenant_id).strip():
        raise MissingTenantAuthorityError(
            "governed_session_requires_server_derived_tenant"
        )
    from app.db.session import (  # noqa: PLC0415  (factory owns engines)
        get_b23_session,
    )

    async with get_b23_session(tenant_id) as session:
        await assert_tenant_authority(session, tenant_id)
        yield session
        await assert_tenant_authority(session, tenant_id)


async def require_tenant_row_exists(
    session: AsyncSession, tenant_id: UUID | str
) -> None:
    """Require a durable tenant row for the authenticated scope tenant.

    A verified JWT can name a tenant UUID that was never provisioned (or
    that has been removed). Without this check the sovereign B2.3 read
    observes zero rows and the boundary would emit a canonical-looking
    ``0/0`` value for a tenant that does not exist. Absence therefore
    refuses here -- it can never become governed zero downstream. Only a
    lawful zero-leg tenant (existing row, both legs zero) may observe
    ``zero_denominator=True``.
    """
    requested = str(tenant_id).strip()
    if not requested:
        raise MissingTenantAuthorityError(
            "canonical_scope_tenant_missing_before_existence_check"
        )
    row = (
        (await session.execute(text("SELECT 1 AS present FROM public.tenants WHERE id = :tenant_id"), {"tenant_id": requested}))
        .mappings()
        .first()
    )
    if row is None:
        raise UnknownTenantError(
            "authenticated_tenant_has_no_durable_tenant_row"
        )
