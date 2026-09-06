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
migration draws in the database: the intended place to open a connection under
``app_b28_requester`` or ``app_b28_solver``, and the only session source the
persistence boundary uses. It follows ``app/trust/signer_session.py``, including
the caller fence.

Neither DSN falls back to the ordinary runtime URL. A missing DSN raises, and
against a provisioned schema the ordinary URL would be refused anyway -- both by
the privilege layer, which no longer grants ``app_user`` INSERT, and by the
consequence guards, which compare ``session_user`` to the dedicated principal
names. The deployment therefore fails closed and loudly in every direction
rather than persisting a consequence under generic authority.

----------------------------------------------------------------------------
Corrective VI -- the declared boundary is the physical one
----------------------------------------------------------------------------

This module previously claimed the credential was reachable by one code path
only. An independent audit refuted it by demonstration in about four lines::

    custody_dsn_direct_connect: ALLOWED
        session_user=app_b28_requester caller=__main__

``_assert_permitted_caller`` fences *this helper*. It does not fence the
credential. The DSN lives in the process environment, ``psycopg2.connect`` is
importable from anywhere, and no file, mount, namespace or kernel boundary
separates the persistence module from the rest of the interpreter. Any in-process
path -- including a compromised transitive dependency -- that reads
``os.environ`` obtains exactly the same authority.

The honest boundary is therefore stated rather than wished for, and it is what
``CUSTODY_TRUST_BOUNDARY`` says:

    **process.** Every code path inside the API process, plus whatever can read
    that process's environment, can open a connection as either dedicated B2.8
    principal.

Two things follow, and both are load-bearing.

**The fence is a diagnostic, not a control.** It converts an accidental second
writer into a named startup-shaped failure during review and test. It is not
relied upon for any security property, and no claim in this repository should
rest on it. ``scripts/ci/assert_b25_p14_custody_manifest.py`` asserts the
declaration and the deployment agree.

**The credential stopped being the whole authority.** Corrective VI moved the
requester's durable attribution behind a possession proof: holding the request
DSN now lets a caller *write a request whose possession it can prove*, and
nothing more. In-process custody was doing work it could not support, and the
repair was to stop asking it to. What remains inside the process boundary is the
ability to write a well-formed row for a credential whose secret the writer
already holds -- which is what an authenticated requester is.

Physical containment is still real at the layer that can enforce it: only the
``api`` service receives ``B28_REQUEST_DATABASE_URL`` and
``B28_SOLVER_DATABASE_URL``. The workers, the beat scheduler, the publisher and
the trust signer do not, which is a container-level fact the custody-manifest
check verifies against ``docker-compose.c19.yml`` rather than inferring from
Python imports (Directive VI H-ART-VI-01).
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

#: The trust boundary the two DSNs are *physically* confined to. Corrective VI
#: replaced a module-shaped claim with the measured truth: the secret is in the
#: process environment, so the process is the boundary. Anything narrower would
#: be a description of intent rather than of custody, and Directive VI section 17
#: requires the declared boundary to match reality.
CUSTODY_TRUST_BOUNDARY = "process"

#: The container that receives the two DSNs in the production topology. Verified
#: against `docker-compose.c19.yml` by
#: `scripts/ci/assert_b25_p14_custody_manifest.py`, so widening it silently is
#: merge-blocking.
CUSTODY_TRUSTED_SERVICES: tuple[str, ...] = ("api",)

#: Claims this module used to make and no longer makes, kept as data rather than
#: as prose so a checker can assert they stay withdrawn. Each was refuted by
#: physical demonstration, and the demonstration is named beside it.
CUSTODY_RETRACTED_CLAIMS: dict[str, str] = {
    "a credential that only one code path can reach is a credential the rest of"
    " the process cannot spend": (
        "custody_dsn_direct_connect: ALLOWED session_user=app_b28_requester"
        " caller=__main__ -- unrelated in-process code opened psycopg directly"
        " with the environment DSN, bypassing the caller fence entirely"
    ),
}

#: The persistence boundary is the only intended caller. This is a review-time
#: and test-time *diagnostic*, not a security control: the audit demonstrated
#: that any in-process path holding the environment DSN bypasses it entirely by
#: calling `psycopg2.connect` directly. Keep it because an accidental second
#: writer should fail loudly with a name; do not rest any claim on it.
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
    "CUSTODY_RETRACTED_CLAIMS",
    "CUSTODY_TRUSTED_SERVICES",
    "CUSTODY_TRUST_BOUNDARY",
    "SimulationCustodyError",
    "b28_request_database_url",
    "b28_solver_database_url",
    "custody_is_separated",
    "request_custody",
    "solver_custody",
]
