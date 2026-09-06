"""Who asked for a simulation, established rather than asserted.

B2.5-P14 Corrective V, closing H-V-01 / H-V-02.

On the entering protected-main tree ``requested_by`` was a ``text NOT NULL``
column and nothing else. The independent audits inserted
``requested_by='attacker:not-a-real-caller'`` through pure SQL and the row was
accepted; the reproduction on the exact entering tree additionally accepted the
empty string. A durable request therefore proved a tenant and a source Trust and
never proved that anybody requested anything.

The correction is not a longer validation of the string. It is that the string
stops being an input:

    a request names a live ``agent_service_credentials`` row
    the caller must present the plaintext token that hashes to it
    ``requested_by`` is *derived* from the resulting principal

``authenticate_simulation_requester`` is the library-boundary counterpart of the
P9 HTTP gateway. Design Partner Mode exposes B2.8 as a library, not as a route,
so the audits' finding -- "no caller authentication exists at the library
boundary" -- is answered here rather than deferred to a future ingress. The
credential physics are P9's, unchanged and reused rather than reimplemented:
SHA-256 at rest, O(1) prefix lookup, ``hmac.compare_digest`` verification,
explicit revocation and expiry checks.

``VerifiedRequester`` carries no free-text field, and no function in this module
accepts a ``requested_by`` argument. The database then re-derives the same value
from the same two foreign keys and refuses any disagreement, so the identity is
checked twice by two authorities that cannot both be the caller.

----------------------------------------------------------------------------
Corrective VI -- the conclusion becomes durable
----------------------------------------------------------------------------

Corrective V's verification was honest and left no trace. The independent audit
reproduced the consequence on a fresh cluster: a session holding only the
``app_b28_requester`` DSN inserted a fully FK-valid request naming a live
credential, with the correctly derived ``requested_by``, **without ever
presenting the plaintext token** (``GATE_F_tokenless_request ALLOWED``). Every
check the database ran was a statement about the credential *row*; none was a
statement about the caller.

``prove_request_possession`` closes that gap by moving the possession proof to
the authority that owns the durable claim. It calls
``b28_authenticate_request_possession``, a ``SECURITY DEFINER`` function that
recomputes ``sha256(presented_token)`` against the stored ``token_hash``,
re-checks liveness at the database's own clock, derives the request binding
itself, and writes a single-use ``b28_request_authentications`` row. The request
insert then names that row through a ``NOT NULL`` foreign key with a ``UNIQUE``
index, so:

    durable requested_by = X
    =>
    somebody presented X's secret, for this exact request, once

The application check below is *kept* rather than replaced. It is no longer the
trust root -- the database is -- but it is what turns a wrong credential into a
named refusal at the boundary instead of a generic SQL error three frames later,
and it is the second of the two authorities that must agree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.trust.machine_identity import TOKEN_PREFIX_LENGTH, verify_machine_token


#: Every persisted requester identity has this exact shape, and the
#: ``ck_b28_request_requested_by_derived`` CHECK constraint says so in the
#: database. An identity that does not name an ``agent_clients`` row is not
#: representable.
REQUESTED_BY_PREFIX = "agent_client:"

_UUID_TEXT = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# Reason codes. Each refusal names one so a red control can be checked for the
# predicted cause rather than merely for redness.
REASON_TOKEN_MALFORMED = "simulation_requester_token_malformed"
REASON_CREDENTIAL_UNKNOWN = "simulation_requester_credential_unknown"
REASON_CREDENTIAL_NOT_LIVE = "simulation_requester_credential_not_live"
REASON_CLIENT_NOT_LIVE = "simulation_requester_client_not_live"
REASON_TENANT_MISMATCH = "simulation_requester_tenant_mismatch"
REASON_POSSESSION_UNPROVEN = "simulation_requester_possession_unproven"

#: The database function that is the sole writer of a possession witness. It is
#: ``SECURITY DEFINER``: the key that mints a witness is the caller's secret, not
#: the caller's grant, so no privilege escalation produces one.
POSSESSION_WITNESS_FUNCTION = "public.b28_authenticate_request_possession"

#: Mirrors ``_POSSESSION_WITNESS_TTL_SECONDS`` in the ``202609071200``
#: migration. A witness is bound to its exact request, so a stale one could only
#: re-authorise the identical row the unique index already refuses; the window is
#: defence in depth, not the mechanism.
POSSESSION_WITNESS_TTL_SECONDS = 900


class SimulationRequesterError(RuntimeError):
    """The presented caller could not be established as a live principal."""

    def __init__(self, reason_code: str, detail: str = "") -> None:
        self.reason_code = reason_code
        self.detail = detail
        super().__init__(detail or reason_code)


@dataclass(frozen=True)
class VerifiedRequester:
    """An authenticated principal. Every field is consequence-derived.

    There is deliberately no ``display_name``, ``label`` or ``requested_by``
    field: a field that exists can be set, and the whole point of this type is
    that the requester identity is not something a caller supplies.
    """

    tenant_id: str
    agent_client_id: str
    credential_id: str
    token_prefix: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "agent_client_id", "credential_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not _UUID_TEXT.match(value):
                raise SimulationRequesterError(
                    REASON_CREDENTIAL_UNKNOWN, f"verified_requester_field:{name}"
                )

    @property
    def requested_by(self) -> str:
        """The derived identity the durable row must carry."""
        return f"{REQUESTED_BY_PREFIX}{self.agent_client_id}"


_LOOKUP_SQL = """
    SELECT cred.id,
           cred.agent_client_id,
           cred.token_hash,
           cred.hash_algorithm,
           cred.status,
           cred.revoked_at,
           cred.expires_at,
           client.status AS client_status,
           client.tenant_id AS client_tenant_id
      FROM public.agent_service_credentials AS cred
      JOIN public.agent_clients AS client
        ON client.id = cred.agent_client_id
     WHERE cred.tenant_id = %s
       AND cred.token_prefix = %s
     LIMIT 1
"""

_REVOCATION_SQL = """
    SELECT 1
      FROM public.agent_token_revocations
     WHERE tenant_id = %s
       AND token_prefix = %s
     LIMIT 1
"""


def authenticate_simulation_requester(
    connection: Any,
    *,
    tenant_id: str,
    presented_token: str,
) -> VerifiedRequester:
    """Establish the caller, or refuse.

    The connection is supplied by the caller because the request-entry boundary
    already holds one under the dedicated request principal; authenticating on a
    second, differently-privileged connection would put the identity check and
    the write in two authority universes, which is the shape Directive V's
    H-DU-V-02 names.
    """

    if not isinstance(presented_token, str) or len(presented_token) < TOKEN_PREFIX_LENGTH:
        raise SimulationRequesterError(
            REASON_TOKEN_MALFORMED, "presented token is too short to be a credential"
        )
    if not isinstance(tenant_id, str) or not _UUID_TEXT.match(tenant_id):
        raise SimulationRequesterError(
            REASON_TENANT_MISMATCH, "tenant identity is not a uuid"
        )

    token_prefix = presented_token[:TOKEN_PREFIX_LENGTH]
    with connection.cursor() as cursor:
        cursor.execute(_LOOKUP_SQL, (tenant_id, token_prefix))
        row = cursor.fetchone()
        if row is None:
            # Indistinguishable from a wrong secret by design: a caller must not
            # learn which prefixes exist.
            raise SimulationRequesterError(
                REASON_CREDENTIAL_UNKNOWN, "no live credential matches"
            )
        (
            credential_id,
            agent_client_id,
            token_hash,
            hash_algorithm,
            status,
            revoked_at,
            expires_at,
            client_status,
            client_tenant_id,
        ) = row

        if not verify_machine_token(
            presented_token, str(token_hash), str(hash_algorithm or "sha256")
        ):
            raise SimulationRequesterError(
                REASON_CREDENTIAL_UNKNOWN, "no live credential matches"
            )

        cursor.execute(_REVOCATION_SQL, (tenant_id, token_prefix))
        if cursor.fetchone() is not None:
            raise SimulationRequesterError(
                REASON_CREDENTIAL_NOT_LIVE, "credential prefix is revoked"
            )

    if status != "active" or revoked_at is not None:
        raise SimulationRequesterError(
            REASON_CREDENTIAL_NOT_LIVE, f"credential status is {status!r}"
        )
    if expires_at is not None:
        # Compared against the database's clock rather than the process's: the
        # guard that re-checks this in `b28_enforce_request_consequence` uses
        # `now()`, and two clocks would be two universes.
        with connection.cursor() as cursor:
            cursor.execute("SELECT %s <= now()", (expires_at,))
            if bool(cursor.fetchone()[0]):
                raise SimulationRequesterError(
                    REASON_CREDENTIAL_NOT_LIVE, "credential has expired"
                )
    if client_status != "active":
        raise SimulationRequesterError(
            REASON_CLIENT_NOT_LIVE, f"agent client status is {client_status!r}"
        )
    if str(client_tenant_id) != tenant_id:
        raise SimulationRequesterError(
            REASON_TENANT_MISMATCH, "agent client belongs to another tenant"
        )

    return VerifiedRequester(
        tenant_id=tenant_id,
        agent_client_id=str(agent_client_id),
        credential_id=str(credential_id),
        token_prefix=token_prefix,
    )


_POSSESSION_SQL = f"""
    SELECT {POSSESSION_WITNESS_FUNCTION}(
        %(tenant_id)s::uuid, %(presented_token)s, %(request_ref)s,
        %(source_issuance_envelope_hash)s, %(input_snapshot_hash)s
    )
"""


def prove_request_possession(
    connection: Any,
    *,
    tenant_id: str,
    presented_token: str,
    request_ref: str,
    source_issuance_envelope_hash: str,
    input_snapshot_hash: str,
) -> str:
    """Make the possession proof durable, and return the witness identity.

    The arguments other than the token are exactly the material the witness is
    *bound* to. They are not decoration: the guard on
    ``b28_simulation_requests`` re-derives the binding from the row being
    inserted and requires equality, so a witness minted for one request cannot
    be spent on another, and the caller cannot decouple the proof from what it
    is a proof of.

    What the caller cannot pass is equally load-bearing. There is no
    ``agent_client_id`` parameter and no ``credential_id`` parameter: both are
    read out of the row the presented secret resolves to. A caller that could
    name them would be back to proving a row rather than a possession.
    """

    with connection.cursor() as cursor:
        cursor.execute(
            _POSSESSION_SQL,
            {
                "tenant_id": str(tenant_id),
                "presented_token": presented_token,
                "request_ref": request_ref,
                "source_issuance_envelope_hash": source_issuance_envelope_hash,
                "input_snapshot_hash": input_snapshot_hash,
            },
        )
        row = cursor.fetchone()
    if row is None or row[0] is None:
        raise SimulationRequesterError(
            REASON_POSSESSION_UNPROVEN, "no possession witness was returned"
        )
    return str(row[0])


__all__ = [
    "POSSESSION_WITNESS_FUNCTION",
    "POSSESSION_WITNESS_TTL_SECONDS",
    "REASON_CLIENT_NOT_LIVE",
    "REASON_CREDENTIAL_NOT_LIVE",
    "REASON_CREDENTIAL_UNKNOWN",
    "REASON_POSSESSION_UNPROVEN",
    "REASON_TENANT_MISMATCH",
    "REASON_TOKEN_MALFORMED",
    "REQUESTED_BY_PREFIX",
    "SimulationRequesterError",
    "VerifiedRequester",
    "authenticate_simulation_requester",
    "prove_request_possession",
]
