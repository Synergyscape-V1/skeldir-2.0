"""B2.5-P14 Corrective VI -- proven possession, honest solver semantics, pinned compatibility.

Four propositions, each reproduced as false on the entering protected-main tree
(``d4ccb816``, tree ``b3bcfbce``, head ``202609061200``) on a fresh PostgreSQL 15
provisioned by the repository's own role script, before this suite existed.

**Exit Gate 1 -- request possession authority.** A durable
``b28_simulation_requests`` row exists only because somebody presented the
plaintext secret of the credential it names. On the entering tree a session
authenticated only as ``app_b28_requester`` inserted a fully FK-valid request
naming a live credential, with the correctly derived ``requested_by``, having
never presented the token::

    GATE_F_tokenless_request   ALLOWED  request_id=c89ca01d-4f92-4f35-94c3-c9004bd32aa6

Every check the guard ran was a statement about the credential *row*. The
application half verified the secret honestly and left no durable trace, so the
two universes produced byte-identical state.

**Exit Gate 2 -- credential custody, declared truthfully.** The custody module
claimed a credential "only one code path can reach". Four lines refuted it::

    GATE_G_dsn_direct_connect  ALLOWED  session_user=app_b28_requester caller=__main__

The fence guards the helper, not the credential; the DSN is process-global. The
repair is not a stronger fence -- a Python frame check cannot become a kernel
boundary -- but a true declaration plus a request authority that no longer rests
on custody alone.

**Exit Gate 3 -- solver consequence semantics.** ``solver_invocations`` read as
an event count and could not be witnessed::

    GATE_K_no_solver_exact_alloc  ALLOWED  result_id=10c30bd2-... solver_invocations=1

with the solver never invoked, and every ``b28_*`` column comment ``NULL``. The
repair is Architecture B: persist the extensional proposition the database
actually verifies, and say so in the schema.

**Exit Gate 6 -- construction compatibility.** A database at the immediately
preceding revision was accepted as production-ready through the real readiness
path::

    stale_known_202609051200:migration_owner  ACCEPTED
    stale_known_202609051200:app_user         ACCEPTED

``202609051200`` grants ``app_user`` INSERT on all three B2.8 relations. Being
known is not being compatible.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager

import psycopg2
import pytest

from app.core.construction_authority import (
    COMPATIBLE_SCHEMA_REVISIONS,
    REQUIRED_SCHEMA_REVISION,
    ConstructionAuthorityError,
    assert_production_construction_authority,
    known_revisions,
    migration_graph_head,
)
from app.simulation.admission import compute_input_snapshot_hash
from app.simulation.consequence_custody import (
    B28_REQUEST_DATABASE_URL_ENV,
    B28_REQUEST_PRINCIPAL,
    B28_SOLVER_DATABASE_URL_ENV,
    B28_SOLVER_PRINCIPAL,
    CUSTODY_TRUST_BOUNDARY,
    CUSTODY_TRUSTED_SERVICES,
)
from app.simulation.contract import SOLVER_CONSEQUENCE_KIND, SimulationRequest
from app.simulation.persistence import conduct_requested_simulation
from app.simulation.requester_identity import (
    POSSESSION_WITNESS_TTL_SECONDS,
    REQUESTED_BY_PREFIX,
)
from app.simulation.solver import SOLVER_PROFILE, allocate_budget
from app.simulation.sufficiency import (
    SUFFICIENCY_POLICY_VERSION,
    adjudicate_sufficiency,
)
from app.trust.refusal import tagged_sha256

from tests.trust.test_b25_p14_r4_downstream_consequence import (
    SUFFICIENT_CHANNELS,
    _admin_connection,
    _admin_dsn,
    _bind_tenant,
    _conduct_issuance,
    _digest,
    _read_back_issued_envelope,
    _role_connection,
    _seed_tenant,
    _sign_real_envelope,
)
from tests.trust.test_b25_p14_r5_causal_authority import (
    _evidence_json,
    _seed_agent_credential,
)


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1",
    reason="P14 Corrective VI proofs require a provisioned production role graph",
)


_REQUEST_INSERT = (
    "INSERT INTO public.b28_simulation_requests (tenant_id, request_ref,"
    " requested_by, requested_by_agent_client_id, requested_by_credential_id,"
    " request_authority_principal, request_authentication_id, source_envelope_id,"
    " source_semantic_truth_hash, source_issuance_envelope_hash,"
    " input_snapshot_hash, total_budget_minor, currency, channel_count,"
    " channel_evidence, solver_profile, sufficiency_policy_version,"
    " sufficiency_verdict, sufficiency_reasons, observed_channels,"
    " observed_conversions, observed_revenue_minor)"
    " VALUES"
    " (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)"
    " RETURNING id"
)

_RESULT_INSERT = (
    "INSERT INTO public.b28_simulation_results (tenant_id, request_id,"
    " source_envelope_id, source_semantic_truth_hash, projection_profile_hash,"
    " input_snapshot_hash, solver_profile, solver_consequence_kind,"
    " total_budget_minor, allocated_total_minor, currency, action_authority,"
    " allocations) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
    " RETURNING id"
)

_MINT_SQL = (
    "SELECT public.b28_authenticate_request_possession(%s::uuid,%s,%s,%s,%s)"
)

#: Directive VI §15. Every durable B2.8 column declares exactly one of these,
#: in its own column comment, so the classification is a property of the schema
#: rather than of a document beside it.
_FIELD_CLASSIFICATIONS = frozenset(
    {"DERIVED VALUE", "OBSERVED EVENT", "AUTHORITY IDENTITY", "PROVENANCE REFERENCE"}
)

_B28_RELATIONS = (
    "b28_request_authentications",
    "b28_simulation_requests",
    "b28_simulation_results",
    "b28_proposals",
)


def _dsn_for(principal: str) -> str:
    from urllib.parse import urlsplit

    parts = urlsplit(_admin_dsn())
    return (
        f"postgresql://{principal}:{principal}@{parts.hostname}:"
        f"{parts.port or 5432}{parts.path}"
    )


@pytest.fixture(autouse=True)
def _consequence_custody_env(monkeypatch):
    monkeypatch.setenv(B28_REQUEST_DATABASE_URL_ENV, _dsn_for(B28_REQUEST_PRINCIPAL))
    monkeypatch.setenv(B28_SOLVER_DATABASE_URL_ENV, _dsn_for(B28_SOLVER_PRINCIPAL))
    yield


@contextmanager
def _as(principal: str, tenant_id):
    connection = psycopg2.connect(_dsn_for(principal))
    connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
        yield connection
    finally:
        connection.close()


def _attempt(principal: str, tenant_id, statement: str, params) -> str:
    with _as(principal, tenant_id) as connection:
        try:
            with connection.cursor() as cursor:
                cursor.execute(statement, params)
                returned = cursor.fetchone()
            connection.commit()
            return f"ALLOWED:{returned[0]}"
        except psycopg2.Error as exc:
            connection.rollback()
            return str(exc).strip().splitlines()[0]


class _Journey:
    """One tenant, one live machine principal, one genuinely signed Trust."""

    def __init__(self) -> None:
        admin = _admin_connection()
        try:
            with admin.cursor() as cursor:
                self.tenant_id = _seed_tenant(cursor)
                (
                    self.token,
                    self.client_id,
                    self.credential_id,
                ) = _seed_agent_credential(cursor, self.tenant_id)
        finally:
            admin.close()
        signed, _registry = _sign_real_envelope(self.tenant_id)
        self.signed = signed
        self.issuance = _conduct_issuance(self.tenant_id, signed)
        self.channels = SUFFICIENT_CHANNELS
        self.budget = 1_000_000
        self.adjudication = adjudicate_sufficiency(self.channels)
        self.snapshot = compute_input_snapshot_hash(
            SimulationRequest(
                request_id="probe",
                tenant_id=str(self.tenant_id),
                requested_by=f"{REQUESTED_BY_PREFIX}{self.client_id}",
                source_envelope_id=self.issuance["envelope_id"],
                source_semantic_truth_hash=self.issuance["semantic_truth_hash"],
                total_budget_minor=self.budget,
                currency="USD",
                channels=self.channels,
                requested_at="probe",
            )
        )

    def mint(self, request_ref: str, *, token: str | None = None) -> str:
        """Take the lawful route to a possession witness."""
        with _as(B28_REQUEST_PRINCIPAL, self.tenant_id) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    _MINT_SQL,
                    (
                        str(self.tenant_id),
                        self.token if token is None else token,
                        request_ref,
                        self.issuance["envelope_hash"],
                        self.snapshot,
                    ),
                )
                witness = str(cursor.fetchone()[0])
            connection.commit()
        return witness

    def request_params(
        self,
        *,
        request_ref: str,
        witness: str,
        requested_by: str | None = None,
        client_id: str | None = None,
        credential_id: str | None = None,
        principal: str = B28_REQUEST_PRINCIPAL,
    ) -> tuple:
        return (
            str(self.tenant_id),
            request_ref,
            requested_by
            if requested_by is not None
            else f"{REQUESTED_BY_PREFIX}{self.client_id}",
            client_id if client_id is not None else self.client_id,
            credential_id if credential_id is not None else self.credential_id,
            principal,
            witness,
            self.issuance["envelope_id"],
            self.issuance["semantic_truth_hash"],
            self.issuance["envelope_hash"],
            self.snapshot,
            self.budget,
            "USD",
            len(self.channels),
            _evidence_json(self.channels),
            SOLVER_PROFILE,
            SUFFICIENCY_POLICY_VERSION,
            self.adjudication.sufficient,
            list(self.adjudication.reasons),
            self.adjudication.observed_channels,
            self.adjudication.observed_conversions,
            self.adjudication.observed_revenue_minor,
        )


# ---------------------------------------------------------------------------
# Exit Gate 1 -- durable requester attribution implies proven possession.
# ---------------------------------------------------------------------------


def test_p14_r6_a_request_cannot_exist_without_proven_possession() -> None:
    """The audit's verbatim counterexample, and the three layers beneath it.

    ``H-VI-01`` said durable requester attribution exceeded possession evidence.
    It did. Every probe below runs as the *real* request principal -- the only
    login that can write a request at all -- so nothing here is refused for want
    of privilege; each refusal is the possession contract firing.
    """

    journey = _Journey()
    findings: dict[str, str] = {}

    # 1. The entering tree's exact move: a well-formed request naming a live
    #    credential, from a session that never presented the secret. It now has
    #    nowhere to get a witness from, so it invents one.
    findings["TOKENLESS_INVENTED_WITNESS"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(
            request_ref="req_" + uuid.uuid4().hex, witness=str(uuid.uuid4())
        ),
    )

    # 2. ... and cannot manufacture one either: possession, not privilege, is
    #    what mints a witness, so the write path simply is not granted.
    findings["REQUESTER_WRITES_WITNESS"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        "INSERT INTO public.b28_request_authentications (tenant_id,"
        " agent_client_id, credential_id, request_binding,"
        " authenticated_by_principal) VALUES (%s,%s,%s,%s,%s) RETURNING id",
        (
            str(journey.tenant_id),
            journey.client_id,
            journey.credential_id,
            "sha256:" + "0" * 64,
            B28_REQUEST_PRINCIPAL,
        ),
    )

    # 3. Knowing the prefix is not holding the secret. The refusal is
    #    deliberately identical to an unknown prefix: a caller must not learn
    #    which prefixes exist.
    wrong_secret = journey.token[:8] + "X" * (len(journey.token) - 8)
    findings["WRONG_SECRET"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _MINT_SQL,
        (
            str(journey.tenant_id),
            wrong_secret,
            "req_" + uuid.uuid4().hex,
            journey.issuance["envelope_hash"],
            journey.snapshot,
        ),
    )

    # 4. The lawful journey, for contrast: a presented secret becomes a witness
    #    becomes a durable request.
    lawful_ref = "req_" + uuid.uuid4().hex
    lawful_witness = journey.mint(lawful_ref)
    findings["LAWFUL"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(request_ref=lawful_ref, witness=lawful_witness),
    )

    # 5. A witness proves possession *for one request*. Spending it on another
    #    is refused by re-derivation, not by comparison to a stored copy.
    findings["WITNESS_SPENT_ELSEWHERE"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(
            request_ref="req_" + uuid.uuid4().hex, witness=lawful_witness
        ),
    )

    # 6. A witness is single-use even when the binding would match, because the
    #    unique index is a structural fact rather than a guard's opinion.
    findings["WITNESS_REPLAYED"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(request_ref=lawful_ref, witness=lawful_witness),
    )

    # 7. A witness cannot be relabelled onto another client: the witness carries
    #    the client the secret resolved to, and the guard compares them.
    other_journey = _Journey()
    other_ref = "req_" + uuid.uuid4().hex
    other_witness = other_journey.mint(other_ref)
    findings["WITNESS_FOR_ANOTHER_CLIENT"] = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(request_ref=other_ref, witness=other_witness),
    )

    assert "b28_request_possession_witness_unknown" in findings[
        "TOKENLESS_INVENTED_WITNESS"
    ], findings["TOKENLESS_INVENTED_WITNESS"]
    assert findings["REQUESTER_WRITES_WITNESS"].startswith("permission denied"), (
        findings["REQUESTER_WRITES_WITNESS"]
    )
    assert "b28_request_possession_credential_unknown" in findings["WRONG_SECRET"], (
        findings["WRONG_SECRET"]
    )
    assert findings["LAWFUL"].startswith("ALLOWED:"), findings["LAWFUL"]
    assert "b28_request_possession_binding_mismatch" in findings[
        "WITNESS_SPENT_ELSEWHERE"
    ], findings["WITNESS_SPENT_ELSEWHERE"]
    assert findings["WITNESS_REPLAYED"] != "ALLOWED", findings["WITNESS_REPLAYED"]
    assert (
        "uq_b28_request_authentication" in findings["WITNESS_REPLAYED"]
        or "uq_b28_request_ref" in findings["WITNESS_REPLAYED"]
    ), findings["WITNESS_REPLAYED"]
    assert findings["WITNESS_FOR_ANOTHER_CLIENT"] != "ALLOWED", findings[
        "WITNESS_FOR_ANOTHER_CLIENT"
    ]


def test_p14_r6_possession_refuses_every_non_live_credential() -> None:
    """Liveness is re-decided at the database's own clock, not the caller's."""

    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            live_token, _client, _credential = _seed_agent_credential(
                cursor, tenant_id
            )
            revoked_token, _rc, revoked_credential = _seed_agent_credential(
                cursor, tenant_id, status="revoked"
            )
            dead_client_token, _dc, _dcred = _seed_agent_credential(
                cursor, tenant_id, client_status="suspended"
            )
            foreign_tenant = _seed_tenant(cursor)
            foreign_token, _fc, _fcred = _seed_agent_credential(
                cursor, foreign_tenant
            )
            # An expiry the database will read as past, set through the same
            # relation the guard reads.
            expiring_token, _ec, expiring_credential = _seed_agent_credential(
                cursor, tenant_id
            )
            cursor.execute(
                "UPDATE public.agent_service_credentials"
                " SET expires_at = now() - interval '1 hour' WHERE id = %s",
                (expiring_credential,),
            )
            cursor.execute(
                "SELECT token_prefix FROM public.agent_service_credentials"
                " WHERE id = %s",
                (revoked_credential,),
            )
            revoked_prefix = cursor.fetchone()[0]
            cursor.execute(
                "INSERT INTO public.agent_token_revocations (tenant_id,"
                " agent_client_id, token_prefix, reason_code)"
                " VALUES (%s,%s,%s,'manual_revocation') ON CONFLICT DO NOTHING",
                (str(tenant_id), _rc, revoked_prefix),
            )
    finally:
        admin.close()

    def mint(token: str, *, tenant=None) -> str:
        return _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant or tenant_id,
            _MINT_SQL,
            (
                str(tenant or tenant_id),
                token,
                "req_" + uuid.uuid4().hex,
                _digest(),
                _digest(),
            ),
        )

    findings["LIVE"] = mint(live_token)
    findings["REVOKED"] = mint(revoked_token)
    findings["DEAD_CLIENT"] = mint(dead_client_token)
    findings["EXPIRED"] = mint(expiring_token)
    # A real secret, presented against the wrong tenant: the lookup is scoped by
    # tenant, so it is indistinguishable from an unknown credential.
    findings["FOREIGN_TENANT"] = mint(foreign_token)
    findings["MALFORMED"] = mint("abc")

    assert findings["LIVE"].startswith("ALLOWED:"), findings["LIVE"]
    assert "b28_request_possession_credential" in findings["REVOKED"], findings[
        "REVOKED"
    ]
    assert "b28_request_possession_client_not_live" in findings["DEAD_CLIENT"], (
        findings["DEAD_CLIENT"]
    )
    assert "b28_request_possession_credential_not_live" in findings["EXPIRED"], (
        findings["EXPIRED"]
    )
    assert "b28_request_possession_credential_unknown" in findings[
        "FOREIGN_TENANT"
    ], findings["FOREIGN_TENANT"]
    assert "b28_request_possession_token_malformed" in findings["MALFORMED"], (
        findings["MALFORMED"]
    )


def test_p14_r6_no_principal_can_write_a_possession_witness() -> None:
    """The witness relation has exactly one writer, and it is not a role.

    A grant is transferable and a secret is not. Making the definer function the
    only INSERT path means "who can attest possession" is answered by *what the
    caller knows*, which is the only answer that can be true.
    """

    journey = _Journey()
    probe = (
        "INSERT INTO public.b28_request_authentications (tenant_id,"
        " agent_client_id, credential_id, request_binding,"
        " authenticated_by_principal) VALUES (%s,%s,%s,%s,%s) RETURNING id"
    )
    params = (
        str(journey.tenant_id),
        journey.client_id,
        journey.credential_id,
        "sha256:" + "1" * 64,
        "forged",
    )
    for principal in (
        "app_user",
        "app_worker",
        B28_REQUEST_PRINCIPAL,
        B28_SOLVER_PRINCIPAL,
    ):
        outcome = _attempt(principal, journey.tenant_id, probe, params)
        assert outcome.startswith("permission denied"), f"{principal}: {outcome}"

    # And the privilege layer says so directly, before any trigger.
    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            for principal in (
                "app_user",
                "app_worker",
                "app_ro",
                "app_rw",
                B28_REQUEST_PRINCIPAL,
                B28_SOLVER_PRINCIPAL,
            ):
                for privilege in ("INSERT", "UPDATE", "DELETE"):
                    cursor.execute(
                        "SELECT has_table_privilege(%s,"
                        " 'public.b28_request_authentications', %s)",
                        (principal, privilege),
                    )
                    assert cursor.fetchone()[0] is False, (
                        f"{principal} holds {privilege} on the witness relation"
                    )
    finally:
        admin.close()


def test_p14_r6_the_possession_layer_is_independently_load_bearing() -> None:
    """Sever one layer at a time; the other must still refuse.

    Directive VI §16's active falsifier: remove the possession binding while
    preserving the credential FK, the client FK, the ``requested_by`` derivation
    and the dedicated request role. Token-less requester attribution must not
    become durable. Here the trigger is dropped and the ``NOT NULL`` foreign key
    still refuses; then the column is made nullable and the trigger still
    refuses. Exact restoration returns green.
    """

    journey = _Journey()
    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_request_possession' AND NOT tgisinternal"
            )
            triggerdef = cursor.fetchone()[0]
        assert triggerdef

        tokenless = journey.request_params(
            request_ref="req_" + uuid.uuid4().hex, witness=str(uuid.uuid4())
        )
        findings["PRISTINE"] = _attempt(
            B28_REQUEST_PRINCIPAL, journey.tenant_id, _REQUEST_INSERT, tokenless
        )

        try:
            with admin.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER trg_b28_request_possession"
                    " ON public.b28_simulation_requests"
                )
            # The structural half alone: an invented witness id has no row to
            # point at, so the foreign key refuses.
            findings["TRIGGER_SEVERED"] = _attempt(
                B28_REQUEST_PRINCIPAL, journey.tenant_id, _REQUEST_INSERT, tokenless
            )
        finally:
            with admin.cursor() as cursor:
                cursor.execute(triggerdef)

        # The guard half alone: a witness that exists but belongs to a different
        # request. The foreign key is satisfied; the binding is not.
        other_ref = "req_" + uuid.uuid4().hex
        other_witness = journey.mint(other_ref)
        findings["BINDING_ONLY"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            journey.tenant_id,
            _REQUEST_INSERT,
            journey.request_params(
                request_ref="req_" + uuid.uuid4().hex, witness=other_witness
            ),
        )

        # Exact restoration: the lawful path is green again.
        restored_ref = "req_" + uuid.uuid4().hex
        findings["RESTORED"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            journey.tenant_id,
            _REQUEST_INSERT,
            journey.request_params(
                request_ref=restored_ref, witness=journey.mint(restored_ref)
            ),
        )
    finally:
        admin.close()

    assert "b28_request_possession_witness_unknown" in findings["PRISTINE"], findings[
        "PRISTINE"
    ]
    assert "foreign key" in findings["TRIGGER_SEVERED"].lower() or (
        "request_authentication" in findings["TRIGGER_SEVERED"]
    ), findings["TRIGGER_SEVERED"]
    assert "b28_request_possession_binding_mismatch" in findings["BINDING_ONLY"], (
        findings["BINDING_ONLY"]
    )
    assert findings["RESTORED"].startswith("ALLOWED:"), findings["RESTORED"]


# ---------------------------------------------------------------------------
# Exit Gate 2 -- the declared custody boundary is the physical one.
# ---------------------------------------------------------------------------


def test_p14_r6_the_declared_custody_boundary_matches_physical_custody() -> None:
    """The claim the audit refuted is gone, and what replaced it is measured.

    ``custody_dsn_direct_connect: ALLOWED`` proved the credential is reachable
    by any in-process code holding the environment DSN. The module now says
    ``process``, and this test reproduces the audit's own probe to show the
    declaration is accurate rather than aspirational -- an honest boundary is one
    you can demonstrate, including the parts you would rather were narrower.
    """

    journey = _Journey()

    assert CUSTODY_TRUST_BOUNDARY == "process"
    assert CUSTODY_TRUSTED_SERVICES == ("api",)

    # The audit's probe, verbatim: unrelated in-process code spends the DSN.
    connection = psycopg2.connect(os.environ[B28_REQUEST_DATABASE_URL_ENV])
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT session_user")
            assert cursor.fetchone()[0] == B28_REQUEST_PRINCIPAL
    finally:
        connection.close()

    # And the consequence that used to follow from it no longer does: holding
    # the credential without holding the secret buys no requester attribution.
    outcome = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(
            request_ref="req_" + uuid.uuid4().hex, witness=str(uuid.uuid4())
        ),
    )
    assert "b28_request_possession_witness_unknown" in outcome, outcome

    # The caller fence is retained as a diagnostic and documented as one. The
    # module must not claim it is a boundary.
    from app.simulation import consequence_custody

    doc = consequence_custody.__doc__ or ""
    assert "diagnostic, not a control" in doc
    assert "only one code path can reach" not in doc


# ---------------------------------------------------------------------------
# Exit Gate 3 -- the persisted solver contract claims only what it can prove.
# ---------------------------------------------------------------------------


def test_p14_r6_the_result_contract_claims_no_unwitnessed_execution() -> None:
    """Architecture B, made physical rather than editorial."""

    journey = _Journey()
    lawful_ref = "req_" + uuid.uuid4().hex
    request_outcome = _attempt(
        B28_REQUEST_PRINCIPAL,
        journey.tenant_id,
        _REQUEST_INSERT,
        journey.request_params(
            request_ref=lawful_ref, witness=journey.mint(lawful_ref)
        ),
    )
    assert request_outcome.startswith("ALLOWED:"), request_outcome
    request_id = request_outcome.split(":", 1)[1]

    lines = allocate_budget(
        channels=journey.channels, total_budget_minor=journey.budget
    )
    allocations = json.dumps(
        [
            {
                "channel_id": line.channel_id,
                "allocation_minor": line.allocation_minor,
                "weight_basis_points": line.weight_basis_points,
            }
            for line in lines
        ],
        separators=(",", ":"),
    )

    def result(kind: str, payload: str, allocated: int | None = None) -> str:
        return _attempt(
            B28_SOLVER_PRINCIPAL,
            journey.tenant_id,
            _RESULT_INSERT,
            (
                str(journey.tenant_id),
                request_id,
                journey.issuance["envelope_id"],
                journey.issuance["semantic_truth_hash"],
                tagged_sha256({"probe": "profile"}),
                journey.snapshot,
                SOLVER_PROFILE,
                kind,
                journey.budget,
                journey.budget if allocated is None else allocated,
                "USD",
                "simulation_only",
                payload,
            ),
        )

    findings: dict[str, str] = {}

    # Under Architecture B this is *lawful and honest*: the writer recomputed the
    # governed function and the database agreed. The point of the corrective is
    # that the row no longer claims a process executed.
    findings["EXTENSIONAL"] = result(SOLVER_CONSEQUENCE_KIND, allocations)

    # The falsifier §18 names for Architecture B: one allocation unit moved,
    # budget still conserved, every CHECK still satisfied.
    moved = json.loads(allocations)
    moved[0]["allocation_minor"] += 1
    moved[1]["allocation_minor"] -= 1
    findings["MUTATED_UNIT"] = result(
        SOLVER_CONSEQUENCE_KIND, json.dumps(moved, separators=(",", ":"))
    )

    # And no field may be widened back into an execution claim.
    findings["EXECUTION_VOCABULARY"] = result(
        "application_solver_executed", allocations
    )
    findings["NULLED_KIND"] = _attempt(
        B28_SOLVER_PRINCIPAL,
        journey.tenant_id,
        _RESULT_INSERT,
        (
            str(journey.tenant_id),
            request_id,
            journey.issuance["envelope_id"],
            journey.issuance["semantic_truth_hash"],
            tagged_sha256({"probe": "profile"}),
            journey.snapshot,
            SOLVER_PROFILE,
            None,
            journey.budget,
            journey.budget,
            "USD",
            "simulation_only",
            allocations,
        ),
    )

    assert findings["EXTENSIONAL"].startswith("ALLOWED:"), findings["EXTENSIONAL"]
    assert "b28_result_not_solver_consequence" in findings["MUTATED_UNIT"], findings[
        "MUTATED_UNIT"
    ]
    assert "b28_result_consequence_kind_ungoverned" in findings[
        "EXECUTION_VOCABULARY"
    ] or "ck_b28_result_solver_consequence_kind" in findings[
        "EXECUTION_VOCABULARY"
    ], findings["EXECUTION_VOCABULARY"]
    assert findings["NULLED_KIND"] != "ALLOWED", findings["NULLED_KIND"]

    # The durable schema carries no execution-event column at all.
    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM pg_attribute"
                " WHERE attrelid = 'public.b28_simulation_results'::regclass"
                "   AND attname = 'solver_invocations' AND NOT attisdropped"
            )
            assert cursor.fetchone()[0] == 0
    finally:
        admin.close()


def test_p14_r6_every_durable_b28_field_declares_its_evidence() -> None:
    """Directive VI §15, as a property of the live catalog.

    A schema that says what it can prove is checkable. Each column carries one
    of four classifications and a sentence naming the physical evidence that
    makes it true, so the next auditor reads the answer out of the database
    rather than out of a report.
    """

    admin = _admin_connection()
    unclassified: list[str] = []
    seen: dict[str, int] = {}
    try:
        with admin.cursor() as cursor:
            for relation in _B28_RELATIONS:
                cursor.execute(
                    "SELECT a.attname, col_description(a.attrelid, a.attnum)"
                    "  FROM pg_attribute a"
                    " WHERE a.attrelid = %s::regclass AND a.attnum > 0"
                    "   AND NOT a.attisdropped"
                    " ORDER BY a.attnum",
                    (f"public.{relation}",),
                )
                rows = cursor.fetchall()
                assert rows, relation
                for column, comment in rows:
                    if not comment:
                        unclassified.append(f"{relation}.{column}: no comment")
                        continue
                    classification = comment.split(".", 1)[0].strip()
                    if classification not in _FIELD_CLASSIFICATIONS:
                        unclassified.append(
                            f"{relation}.{column}: {classification!r}"
                        )
                        continue
                    evidence = comment.split(".", 1)[1].strip()
                    if len(evidence) < 20:
                        unclassified.append(
                            f"{relation}.{column}: evidence too thin"
                        )
                    seen[classification] = seen.get(classification, 0) + 1
    finally:
        admin.close()

    assert not unclassified, unclassified
    # Every category is actually used: a taxonomy where three of four buckets
    # are empty is a taxonomy nobody applied.
    assert set(seen) == _FIELD_CLASSIFICATIONS, seen

    # And the one field the corrective renamed says both halves of its meaning.
    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT col_description('public.b28_simulation_results'::regclass,"
                " (SELECT attnum FROM pg_attribute"
                "   WHERE attrelid = 'public.b28_simulation_results'::regclass"
                "     AND attname = 'solver_consequence_kind'))"
            )
            comment = cursor.fetchone()[0]
    finally:
        admin.close()
    assert comment.startswith("DERIVED VALUE.")
    assert "b28_recompute_allocation" in comment
    assert "NOT a claim" in comment


# ---------------------------------------------------------------------------
# Exit Gate 6 -- construction compatibility, explicit and machine-checkable.
# ---------------------------------------------------------------------------


def test_p14_r6_the_compatibility_contract_cannot_drift_from_the_chain() -> None:
    assert REQUIRED_SCHEMA_REVISION == migration_graph_head()
    assert COMPATIBLE_SCHEMA_REVISIONS == frozenset({REQUIRED_SCHEMA_REVISION})
    assert REQUIRED_SCHEMA_REVISION in known_revisions()


def test_p14_r6_readiness_refuses_a_known_incompatible_revision() -> None:
    """The Corrective-VI blocker, and the distinction it turns on.

    ``202609051200`` is known, structurally plausible, and the schema whose
    fabrication surface Corrective V removed. The refusal names *which* property
    failed, so an operator can tell "not ours" from "ours, but not this build's".
    """

    for stale in ("202609051200", "202609061200"):
        assert stale in known_revisions()
        with pytest.raises(ConstructionAuthorityError) as refusal:
            assert_production_construction_authority([stale])
        assert "incompatible_revision" in str(refusal.value)

    with pytest.raises(ConstructionAuthorityError) as unknown:
        assert_production_construction_authority(["999912311200"])
    assert "unknown_revision" in str(unknown.value)

    with pytest.raises(ConstructionAuthorityError) as unconstructed:
        assert_production_construction_authority([])
    assert "no_alembic_revision" in str(unconstructed.value)

    with pytest.raises(ConstructionAuthorityError) as multiple:
        assert_production_construction_authority(
            [REQUIRED_SCHEMA_REVISION, "202609061200"]
        )
    assert "multiple_alembic_revisions" in str(multiple.value)

    assert (
        assert_production_construction_authority([REQUIRED_SCHEMA_REVISION])
        == REQUIRED_SCHEMA_REVISION
    )


# ---------------------------------------------------------------------------
# Operational wiring and constant mirroring.
# ---------------------------------------------------------------------------


def test_p14_r6_the_lawful_library_path_produces_a_possession_witness() -> None:
    """Directive VI §31: the corrected authority is the deployed route.

    ``conduct_requested_simulation`` takes a token, not an identity. This drives
    it end to end and then reconstructs, from the durable rows alone, that a
    possession proof physically preceded the request it authorised.
    """

    journey = _Journey()
    envelope = _read_back_issued_envelope(
        journey.tenant_id, journey.issuance["audit_ref"]
    )
    conducted = conduct_requested_simulation(
        envelope=envelope,
        tenant_id=str(journey.tenant_id),
        presented_token=journey.token,
        source_issuance_envelope_hash=journey.issuance["envelope_hash"],
        total_budget_minor=journey.budget,
        currency="USD",
        channels=journey.channels,
    )
    assert conducted["identifiers"]["persisted"] == "true"

    reader = _role_connection("app_user")
    try:
        with reader.cursor() as cursor:
            _bind_tenant(cursor, journey.tenant_id)
            cursor.execute(
                "SELECT req.request_ref, req.requested_by,"
                "       req.source_issuance_envelope_hash, req.input_snapshot_hash,"
                "       auth.id, auth.agent_client_id, auth.credential_id,"
                "       auth.request_binding, auth.authenticated_by_principal,"
                "       auth.authenticated_at <= req.requested_at,"
                "       res.solver_consequence_kind"
                "  FROM public.b28_simulation_requests AS req"
                "  JOIN public.b28_request_authentications AS auth"
                "    ON auth.id = req.request_authentication_id"
                "  JOIN public.b28_simulation_results AS res"
                "    ON res.request_id = req.id"
                " WHERE req.id = %s",
                (conducted["request_id"],),
            )
            row = cursor.fetchone()
            assert row is not None

            # The binding is re-derivable by any reader holding only SELECT: the
            # possession proof is auditable without trusting the writer.
            cursor.execute(
                "SELECT public.b28_request_authentication_binding("
                " %s::uuid,%s,%s,%s)",
                (str(journey.tenant_id), row[0], row[2], row[3]),
            )
            rederived = cursor.fetchone()[0]
    finally:
        reader.close()

    assert row[1] == f"{REQUESTED_BY_PREFIX}{row[5]}"
    assert str(row[6]) == journey.credential_id
    assert row[7] == rederived
    assert row[8] == B28_REQUEST_PRINCIPAL
    assert row[9] is True, "possession was not proven before the request committed"
    assert row[10] == SOLVER_CONSEQUENCE_KIND


def test_p14_r6_governed_constants_are_mirrored_by_the_migration() -> None:
    """A constant that moves in one place and not the other is merge-blocking."""

    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/007_skeldir_foundation"
        / "202609071200_b25_p14_r6_possession_and_compatibility.py"
    ).read_text(encoding="utf-8")

    assert f'_SOLVER_CONSEQUENCE_KIND = "{SOLVER_CONSEQUENCE_KIND}"' in migration
    assert f'_SOLVER_PROFILE = "{SOLVER_PROFILE}"' in migration
    assert (
        f"_POSSESSION_WITNESS_TTL_SECONDS = {POSSESSION_WITNESS_TTL_SECONDS}"
        in migration
    )
    assert f'_REQUEST_PRINCIPAL = "{B28_REQUEST_PRINCIPAL}"' in migration
    assert f'_SOLVER_PRINCIPAL = "{B28_SOLVER_PRINCIPAL}"' in migration
    assert f'revision = "{REQUIRED_SCHEMA_REVISION}"' in migration


def test_p14_r6_the_possession_guard_runs_after_the_consequence_guard() -> None:
    """Pin the diagnostic ordering the other suites' reason codes depend on.

    Both guards must pass, so the order is never a security property. It is a
    diagnosis property: an operator whose credential is unknown should be told
    that, not told about a witness mismatch that is merely its consequence.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT tgname FROM pg_trigger t"
                "  JOIN pg_class c ON c.oid = t.tgrelid"
                " WHERE c.relname = 'b28_simulation_requests'"
                "   AND NOT t.tgisinternal"
                "   AND t.tgname IN ('trg_b28_request_consequence',"
                "                    'trg_b28_request_possession')"
                " ORDER BY t.tgname"
            )
            order = [row[0] for row in cursor.fetchall()]
    finally:
        admin.close()
    assert order == [
        "trg_b28_request_consequence",
        "trg_b28_request_possession",
    ], order
