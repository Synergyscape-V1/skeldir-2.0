"""Dedicated database custody for the two B2.8 causal authorities.

B2.5-P14 Corrective V.

A durable ``b28_simulation_requests`` row is the claim *a verified caller asked
for this simulation*. A durable ``b28_simulation_results`` row is the claim *the
governed deterministic solver ran over that admitted input*. On the entering
protected-main tree both claims were writable by the ordinary ``app_user``
login, so one authority domain could author the alleged cause and the alleged
consequence -- structurally the issuance self-certification defect that
Corrective XVI closed for ``trust_envelope_issuance_log``.

This module is the application half of the boundary the ``202609061200``
migration draws in the database: the only place that opens a connection under
``app_b28_requester`` or ``app_b28_solver``, and the only session source the
persistence boundary may use. It follows ``app/trust/signer_session.py``
exactly, including the caller fence, because the property being obtained is the
same one: a credential that only one code path can reach is a credential the
rest of the process cannot spend.

Neither DSN falls back to the ordinary runtime URL. A missing DSN raises, and
against a provisioned schema the ordinary URL would be refused anyway -- both by
the privilege layer, which no longer grants ``app_user`` INSERT, and by the
consequence guards, which compare ``session_user`` to the dedicated principal
names. The deployment therefore fails closed and loudly in every direction
rather than persisting a consequence under generic authority.
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Iterator

import psycopg2


B28_REQUEST_DATABASE_URL_ENV = "B28_REQUEST_DATABASE_URL"
B28_SOLVER_DATABASE_URL_ENV = "B28_SOLVER_DATABASE_URL"

#: The database principals the ``202609061200`` consequence guards compare
#: ``session_user`` against. ``SET ROLE`` cannot change ``session_user``, which
#: is why the guards key on it rather than on ``current_user``.
B28_REQUEST_PRINCIPAL = "app_b28_requester"
B28_SOLVER_PRINCIPAL = "app_b28_solver"

#: Only the persistence boundary may take custody. A module that wants to write
#: a request or a result has to be this one, which makes "who can persist a
#: consequence" a fact about the import graph rather than about discipline.
_PERMITTED_CALLER = "app.simulation.persistence"


class SimulationCustodyError(RuntimeError):
    """Raised when consequence custody is unavailable or improperly reached."""


def _assert_permitted_caller(depth: int) -> None:
    caller = sys._getframe(depth).f_globals.get("__name__", "")
    if caller != _PERMITTED_CALLER:
        raise SimulationCustodyError(
            f"b28_consequence_custody_untrusted_caller:{caller or 'unknown'}"
        )


def b28_request_database_url() -> str:
    """Resolve the DSN held only by the B2.8 request-entry boundary."""
    configured = os.getenv(B28_REQUEST_DATABASE_URL_ENV, "").strip()
    if not configured:
        raise SimulationCustodyError("b28_request_database_url_required")
    return configured


def b28_solver_database_url() -> str:
    """Resolve the DSN held only by the B2.8 solver consequence boundary."""
    configured = os.getenv(B28_SOLVER_DATABASE_URL_ENV, "").strip()
    if not configured:
        raise SimulationCustodyError("b28_solver_database_url_required")
    return configured


def _normalize(dsn: str) -> str:
    return dsn.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+asyncpg://", "postgresql://"
    )


@contextmanager
def _custody(dsn: str, *, expected_principal: str) -> Iterator[object]:
    connection = psycopg2.connect(_normalize(dsn))
    connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT session_user")
            actual = cursor.fetchone()[0]
        if actual != expected_principal:
            # H-ART-V-03 / H-WIRE-V-02: a migration can create the right role
            # and the deployment can still authenticate as the wrong one. The
            # process refuses to proceed rather than discovering it at the
            # trigger, so a misconfigured DSN is a startup-shaped failure with a
            # name instead of a confusing permission error later.
            raise SimulationCustodyError(
                f"b28_consequence_custody_wrong_principal:{actual}"
                f"!={expected_principal}"
            )
        yield connection
    finally:
        connection.close()


@contextmanager
def request_custody() -> Iterator[object]:
    """Open one short-lived connection as the request-entry principal."""
    _assert_permitted_caller(3)
    with _custody(
        b28_request_database_url(), expected_principal=B28_REQUEST_PRINCIPAL
    ) as connection:
        yield connection


@contextmanager
def solver_custody() -> Iterator[object]:
    """Open one short-lived connection as the solver consequence principal."""
    _assert_permitted_caller(3)
    with _custody(
        b28_solver_database_url(), expected_principal=B28_SOLVER_PRINCIPAL
    ) as connection:
        yield connection


def custody_is_separated() -> bool:
    """Report whether both causal authorities have their own DSN here."""
    return bool(
        os.getenv(B28_REQUEST_DATABASE_URL_ENV, "").strip()
        and os.getenv(B28_SOLVER_DATABASE_URL_ENV, "").strip()
    )


__all__ = [
    "B28_REQUEST_DATABASE_URL_ENV",
    "B28_REQUEST_PRINCIPAL",
    "B28_SOLVER_DATABASE_URL_ENV",
    "B28_SOLVER_PRINCIPAL",
    "SimulationCustodyError",
    "b28_request_database_url",
    "b28_solver_database_url",
    "custody_is_separated",
    "request_custody",
    "solver_custody",
]
