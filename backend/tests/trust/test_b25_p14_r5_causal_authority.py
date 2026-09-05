"""B2.5-P14 Corrective V -- genuine request intent and solver consequence.

Two propositions, each reproduced as false on the entering protected-main tree
(`0d8d2283`, tree `795b4ddc`, head `202609051200`) before this suite existed.

**Exit Gate 1 -- genuine explicit request authority.** A durable
``b28_simulation_requests`` row exists only because a caller that proved it holds
a live machine credential asked for a simulation. On the entering tree the real
``app_user`` login inserted ``requested_by='attacker:not-a-real-caller'`` through
pure SQL and the row was accepted (`ALLOWED rowcount=1`); so was the empty
string. ``requested_by`` was descriptive text, and no caller authentication
existed at the library boundary Design Partner Mode exposes.

**Exit Gate 2 -- solver consequence sovereignty.** A durable
``b28_simulation_results`` row exists only because the governed deterministic
solver produced exactly that allocation over exactly that admitted input. On the
entering tree a result over fantasy channels ``a``/``b`` -- present in no
evidence, for a request that was never adjudicated -- carrying the governed
profile string and ``solver_invocations=1``, was accepted with no solver
execution at all; ``solver_invocations=99`` was equally acceptable.

The correction is layered, and the layers are severed one at a time below so
each is shown to be independently load-bearing:

    privilege     ``app_user`` holds no INSERT on any B2.8 relation
    principal     the guards compare ``session_user`` to a dedicated login
    identity      ``requested_by`` is re-derived from live credential rows
    witness       the request retains its channel evidence; the snapshot hash
                  is recomputed from it
    sufficiency   the verdict is re-adjudicated and durably bound
    consequence   the allocation is *recomputed*, not compared

The last is the one that matters most. The solver is a deterministic integer
function, so the database can evaluate it; a fabricated allocation is refused
not because it looks wrong but because it is not the value of the function.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from typing import Any

import psycopg2
import pytest

from app.simulation.admission import compute_input_snapshot_hash
from app.simulation.consequence_custody import (
    B28_REQUEST_DATABASE_URL_ENV,
    B28_REQUEST_PRINCIPAL,
    B28_SOLVER_DATABASE_URL_ENV,
    B28_SOLVER_PRINCIPAL,
    SimulationCustodyError,
    custody_is_separated,
    request_custody,
)
from app.simulation.contract import ChannelEvidence, SimulationRequest
from app.simulation.persistence import conduct_requested_simulation
from app.simulation.requester_identity import (
    REASON_CREDENTIAL_NOT_LIVE,
    REASON_CREDENTIAL_UNKNOWN,
    REQUESTED_BY_PREFIX,
    SimulationRequesterError,
    VerifiedRequester,
    authenticate_simulation_requester,
)
from app.simulation.solver import SOLVER_PROFILE, allocate_budget
from app.simulation.sufficiency import (
    MIN_CHANNELS,
    MIN_CHANNELS_WITH_EVIDENCE,
    MIN_TOTAL_CONVERSIONS,
    MIN_TOTAL_REVENUE_MINOR,
    SUFFICIENCY_POLICY_VERSION,
    adjudicate_sufficiency,
)
from app.trust.machine_identity import generate_machine_token

from tests.trust.test_b25_p14_r4_downstream_consequence import (
    SUFFICIENT_CHANNELS,
    _admin_connection,
    _bind_tenant,
    _conduct_issuance,
    _digest,
    _read_back_issued_envelope,
    _role_connection,
    _seed_tenant,
    _sign_real_envelope,
)


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1",
    reason="P14 Corrective V proofs require a provisioned production role graph",
)


INSUFFICIENT_CHANNELS = (
    ChannelEvidence("google_ads", 400_000, 1),
    ChannelEvidence("meta_ads", 0, 0),
)


# ---------------------------------------------------------------------------
# Fixtures for the authenticated principal the corrected contract requires.
# ---------------------------------------------------------------------------


def _seed_agent_credential(
    cursor, tenant_id, *, client_status: str = "active", status: str = "active"
) -> tuple[str, str, str]:
    """Create one live machine principal and return its plaintext token."""
    secret = generate_machine_token()
    client_id = uuid.uuid4()
    credential_id = uuid.uuid4()
    cursor.execute(
        "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
        " client_display_hash, audience, status)"
        " VALUES (%s,%s,%s,%s,%s,%s)",
        (
            str(client_id),
            str(tenant_id),
            f"p14r5-{client_id.hex[:8]}",
            _digest(),
            "trust-api",
            client_status,
        ),
    )
    cursor.execute(
        "INSERT INTO public.agent_service_credentials (id, tenant_id,"
        " agent_client_id, token_prefix, token_hash, status)"
        " VALUES (%s,%s,%s,%s,%s,%s)",
        (
            str(credential_id),
            str(tenant_id),
            str(client_id),
            secret.token_prefix,
            secret.token_hash,
            status,
        ),
    )
    return secret.plaintext, str(client_id), str(credential_id)


def _dsn_for(principal: str) -> str:
    from urllib.parse import urlsplit

    from tests.trust.test_b25_p14_r4_downstream_consequence import _admin_dsn

    parts = urlsplit(_admin_dsn())
    return (
        f"postgresql://{principal}:{principal}@{parts.hostname}:"
        f"{parts.port or 5432}{parts.path}"
    )


@pytest.fixture(autouse=True)
def _consequence_custody_env(monkeypatch):
    """Give the process the two dedicated DSNs, as the deployment would."""
    monkeypatch.setenv(B28_REQUEST_DATABASE_URL_ENV, _dsn_for(B28_REQUEST_PRINCIPAL))
    monkeypatch.setenv(B28_SOLVER_DATABASE_URL_ENV, _dsn_for(B28_SOLVER_PRINCIPAL))
    yield


@contextmanager
def _requester_connection(tenant_id):
    """A connection as the request principal, opened by the test rather than
    through ``request_custody``.

    The custody helper refuses every caller but ``app.simulation.persistence``
    -- that fence is itself proved below -- so an identity probe has to open its
    own connection under the same login. The authority being exercised is
    identical; only the code path that obtained it differs.
    """
    connection = psycopg2.connect(_dsn_for(B28_REQUEST_PRINCIPAL))
    connection.autocommit = False
    try:
        with connection.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
        yield connection
        connection.rollback()
    finally:
        connection.close()


def _attempt(role: str, tenant_id, statement: str, params) -> str:
    conn = _role_connection(role)
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(statement, params)
        conn.commit()
        return "ALLOWED"
    except psycopg2.Error as exc:
        conn.rollback()
        return str(exc).strip().splitlines()[0]
    finally:
        conn.close()


_REQUEST_INSERT_FULL = (
    "INSERT INTO public.b28_simulation_requests (tenant_id, request_ref,"
    " requested_by, requested_by_agent_client_id, requested_by_credential_id,"
    " request_authority_principal, source_envelope_id,"
    " source_semantic_truth_hash, source_issuance_envelope_hash,"
    " input_snapshot_hash, total_budget_minor, currency, channel_count,"
    " channel_evidence, solver_profile, sufficiency_policy_version,"
    " sufficiency_verdict, sufficiency_reasons, observed_channels,"
    " observed_conversions, observed_revenue_minor)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s)"
)

_RESULT_INSERT = (
    "INSERT INTO public.b28_simulation_results (tenant_id, request_id,"
    " source_envelope_id, source_semantic_truth_hash, projection_profile_hash,"
    " input_snapshot_hash, solver_profile, solver_invocations,"
    " total_budget_minor, allocated_total_minor, currency, action_authority,"
    " allocations) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)


def _evidence_json(channels: tuple[ChannelEvidence, ...]) -> str:
    return json.dumps(
        [
            {
                "channel_id": c.channel_id,
                "verified_revenue_minor": c.verified_revenue_minor,
                "conversion_count": c.conversion_count,
            }
            for c in channels
        ]
    )


def _request_params(
    tenant_id,
    issuance,
    *,
    requested_by: str,
    client_id: str,
    credential_id: str,
    principal: str,
    channels: tuple[ChannelEvidence, ...] = SUFFICIENT_CHANNELS,
    budget: int = 1_000_000,
    snapshot: str | None = None,
    verdict: bool | None = None,
) -> tuple:
    adjudication = adjudicate_sufficiency(channels)
    probe = SimulationRequest(
        request_id="probe",
        tenant_id=str(tenant_id),
        requested_by=requested_by or "x",
        source_envelope_id=issuance["envelope_id"],
        source_semantic_truth_hash=issuance["semantic_truth_hash"],
        total_budget_minor=budget,
        currency="USD",
        channels=channels,
        requested_at="probe",
    )
    return (
        str(tenant_id),
        "req_" + uuid.uuid4().hex,
        requested_by,
        client_id,
        credential_id,
        principal,
        issuance["envelope_id"],
        issuance["semantic_truth_hash"],
        issuance["envelope_hash"],
        snapshot if snapshot is not None else compute_input_snapshot_hash(probe),
        budget,
        "USD",
        len(channels),
        _evidence_json(channels),
        SOLVER_PROFILE,
        SUFFICIENCY_POLICY_VERSION,
        adjudication.sufficient if verdict is None else verdict,
        list(adjudication.reasons),
        adjudication.observed_channels,
        adjudication.observed_conversions,
        adjudication.observed_revenue_minor,
    )


# ---------------------------------------------------------------------------
# Exit Gate 1 -- genuine explicit request authority.
# ---------------------------------------------------------------------------


def test_p14_r5_generic_runtime_principals_cannot_author_a_request() -> None:
    """The audits' verbatim counterexample, and the privilege beneath it."""

    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, client_id, credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
        signed, _registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)

        # The exact row both independent audits made durable.
        findings["REQ_DIRECT_SQL_NO_INTENT"] = _attempt(
            "app_user",
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by="attacker:not-a-real-caller",
                client_id=client_id,
                credential_id=credential_id,
                principal="app_user",
            ),
        )
        # ... and the same row with a derived identity, which still must fail:
        # the identity being well formed is not the same as the writer being
        # entitled to make the claim.
        findings["REQ_DIRECT_SQL_DERIVED_IDENTITY"] = _attempt(
            "app_user",
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=credential_id,
                principal="app_user",
            ),
        )
        findings["REQ_WORKER"] = _attempt(
            "app_worker",
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=credential_id,
                principal="app_worker",
            ),
        )
        # The solver authority may not manufacture its own cause.
        findings["REQ_BY_SOLVER_PRINCIPAL"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=credential_id,
                principal=B28_SOLVER_PRINCIPAL,
            ),
        )
        # Even the request principal may not author an undeclared identity.
        findings["REQ_PRINCIPAL_INVENTED_IDENTITY"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by="attacker:not-a-real-caller",
                client_id=client_id,
                credential_id=credential_id,
                principal=B28_REQUEST_PRINCIPAL,
            ),
        )
        findings["REQ_PRINCIPAL_UNKNOWN_CREDENTIAL"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=str(uuid.uuid4()),
                principal=B28_REQUEST_PRINCIPAL,
            ),
        )
        findings["REQ_PRINCIPAL_MISREPORTED_AUTHORITY"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=credential_id,
                principal="app_user",
            ),
        )
    finally:
        admin.close()

    assert findings["REQ_DIRECT_SQL_NO_INTENT"].startswith("permission denied")
    assert findings["REQ_DIRECT_SQL_DERIVED_IDENTITY"].startswith("permission denied")
    assert findings["REQ_WORKER"].startswith("permission denied")
    assert findings["REQ_BY_SOLVER_PRINCIPAL"].startswith("permission denied")
    assert (
        "b28_request_requested_by_not_derived"
        in findings["REQ_PRINCIPAL_INVENTED_IDENTITY"]
    )
    assert (
        "b28_request_requester_credential_unknown"
        in findings["REQ_PRINCIPAL_UNKNOWN_CREDENTIAL"]
    )
    assert (
        "b28_request_authority_principal_not_derived"
        in findings["REQ_PRINCIPAL_MISREPORTED_AUTHORITY"]
    )


def test_p14_r5_requester_identity_is_established_not_asserted() -> None:
    """The library boundary authenticates; a self-declared caller cannot pass."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, client_id, credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
            other_tenant = _seed_tenant(cursor)
            revoked_token, _, _ = _seed_agent_credential(
                cursor, tenant_id, status="revoked"
            )
            dead_client_token, _, _ = _seed_agent_credential(
                cursor, tenant_id, client_status="revoked"
            )
    finally:
        admin.close()

    with _requester_connection(tenant_id) as connection:
        verified = authenticate_simulation_requester(
            connection, tenant_id=str(tenant_id), presented_token=token
        )
        assert isinstance(verified, VerifiedRequester)
        assert verified.agent_client_id == client_id
        assert verified.credential_id == credential_id
        assert verified.requested_by == f"{REQUESTED_BY_PREFIX}{client_id}"

        with pytest.raises(SimulationRequesterError) as invented:
            authenticate_simulation_requester(
                connection,
                tenant_id=str(tenant_id),
                presented_token="not-a-real-token-at-all",
            )
        assert invented.value.reason_code == REASON_CREDENTIAL_UNKNOWN

        # A right prefix with a wrong secret is refused the same way, so the
        # refusal leaks nothing about which prefixes exist.
        with pytest.raises(SimulationRequesterError) as wrong_secret:
            authenticate_simulation_requester(
                connection,
                tenant_id=str(tenant_id),
                presented_token=token[:8] + "x" * (len(token) - 8),
            )
        assert wrong_secret.value.reason_code == REASON_CREDENTIAL_UNKNOWN

        with pytest.raises(SimulationRequesterError) as revoked:
            authenticate_simulation_requester(
                connection, tenant_id=str(tenant_id), presented_token=revoked_token
            )
        assert revoked.value.reason_code == REASON_CREDENTIAL_NOT_LIVE

        with pytest.raises(SimulationRequesterError) as dead_client:
            authenticate_simulation_requester(
                connection,
                tenant_id=str(tenant_id),
                presented_token=dead_client_token,
            )
        assert dead_client.value.reason_code in {
            REASON_CREDENTIAL_NOT_LIVE,
            "simulation_requester_client_not_live",
        }

    # A real credential presented under the wrong tenant is invisible: RLS
    # filters the lookup under the caller's own tenant binding.
    with _requester_connection(other_tenant) as connection:
        with pytest.raises(SimulationRequesterError) as cross_tenant:
            authenticate_simulation_requester(
                connection, tenant_id=str(other_tenant), presented_token=token
            )
        assert cross_tenant.value.reason_code == REASON_CREDENTIAL_UNKNOWN


# ---------------------------------------------------------------------------
# Exit Gates 2 and 4 -- solver consequence sovereignty and input reconstruction.
# ---------------------------------------------------------------------------


def test_p14_r5_a_result_must_be_the_solver_consequence() -> None:
    """Every shape the audits made durable, refused; the lawful one, accepted."""

    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, client_id, credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
        signed, _registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)
        envelope = _read_back_issued_envelope(tenant_id, issuance["audit_ref"])

        conducted = conduct_requested_simulation(
            envelope=envelope,
            tenant_id=str(tenant_id),
            presented_token=token,
            source_issuance_envelope_hash=issuance["envelope_hash"],
            total_budget_minor=1_000_000,
            currency="USD",
            channels=SUFFICIENT_CHANNELS,
        )
        request_id = conducted["request_id"]
        outcome = conducted["outcome"]
        lawful_allocations = json.dumps(
            [
                {
                    "channel_id": line.channel_id,
                    "allocation_minor": line.allocation_minor,
                    "weight_basis_points": line.weight_basis_points,
                }
                for line in outcome.allocations
            ]
        )

        # A second request over the same evidence, to attack with.
        second = conduct_requested_simulation(
            envelope=envelope,
            tenant_id=str(tenant_id),
            presented_token=token,
            source_issuance_envelope_hash=issuance["envelope_hash"],
            total_budget_minor=1_000_000,
            currency="USD",
            channels=SUFFICIENT_CHANNELS,
        )
        del second

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cursor.execute(
                _REQUEST_INSERT_FULL + " RETURNING id",
                _request_params(
                    tenant_id,
                    issuance,
                    requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                    client_id=client_id,
                    credential_id=credential_id,
                    principal="postgres",
                ),
            )
            spare_request = cursor.fetchone()[0]

        base = (
            str(tenant_id),
            str(spare_request),
            issuance["envelope_id"],
            issuance["semantic_truth_hash"],
            _digest(),
            outcome.input_snapshot_hash,
            SOLVER_PROFILE,
            1,
            1_000_000,
            1_000_000,
            "USD",
            "simulation_only",
        )

        findings["RESULT_BY_APP_USER"] = _attempt(
            "app_user", tenant_id, _RESULT_INSERT, base + (lawful_allocations,)
        )
        findings["RESULT_BY_REQUEST_PRINCIPAL"] = _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base + (lawful_allocations,),
        )
        # The audits' verbatim forgery: fantasy channels, exactly conserving.
        findings["RESULT_FANTASY_CHANNELS"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base
            + (
                json.dumps(
                    [
                        {
                            "channel_id": "a",
                            "allocation_minor": 600_000,
                            "weight_basis_points": 6000,
                        },
                        {
                            "channel_id": "b",
                            "allocation_minor": 400_000,
                            "weight_basis_points": 4000,
                        },
                    ]
                ),
            ),
        )
        # A caller-chosen conserving split over the *right* channels.
        findings["RESULT_CALLER_CHOSEN_SPLIT"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base
            + (
                json.dumps(
                    [
                        {
                            "channel_id": "email",
                            "allocation_minor": 1_000_000,
                            "weight_basis_points": 10_000,
                        },
                        {
                            "channel_id": "google_ads",
                            "allocation_minor": 0,
                            "weight_basis_points": 0,
                        },
                        {
                            "channel_id": "meta_ads",
                            "allocation_minor": 0,
                            "weight_basis_points": 0,
                        },
                    ]
                ),
            ),
        )
        # One minor unit moved between two channels: still conserving, still
        # every CHECK satisfied, still not the solver's output.
        moved = json.loads(lawful_allocations)
        moved[0]["allocation_minor"] += 1
        moved[1]["allocation_minor"] -= 1
        findings["RESULT_ONE_MINOR_UNIT_MOVED"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base + (json.dumps(moved),),
        )
        # Correct money, wrong declared weights.
        reweighted = json.loads(lawful_allocations)
        reweighted[0]["weight_basis_points"] += 1
        reweighted[1]["weight_basis_points"] -= 1
        findings["RESULT_WEIGHTS_ALTERED"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base + (json.dumps(reweighted),),
        )
        findings["RESULT_SOLVER_INVOCATIONS_99"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base[:7] + (99,) + base[8:] + (lawful_allocations,),
        )
        # The lawful consequence, persisted by the lawful authority.
        findings["RESULT_LAWFUL"] = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            base + (lawful_allocations,),
        )
    finally:
        admin.close()

    assert findings["RESULT_BY_APP_USER"].startswith("permission denied")
    assert findings["RESULT_BY_REQUEST_PRINCIPAL"].startswith("permission denied")
    for key in (
        "RESULT_FANTASY_CHANNELS",
        "RESULT_CALLER_CHOSEN_SPLIT",
        "RESULT_ONE_MINOR_UNIT_MOVED",
        "RESULT_WEIGHTS_ALTERED",
    ):
        assert (
            "b28_result_not_solver_consequence" in findings[key]
            or "b28_result_channel_count_disagrees" in findings[key]
        ), f"{key}: {findings[key]}"
    assert (
        "b28_result_solver_invocations_not_one"
        in findings["RESULT_SOLVER_INVOCATIONS_99"]
    )
    assert findings["RESULT_LAWFUL"] == "ALLOWED"
    assert request_id


def test_p14_r5_the_input_witness_is_reconstructible_and_bound() -> None:
    """Gate 4: an auditor with only the row can recompute the allocation."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, _client_id, _credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
        signed, _registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)
        envelope = _read_back_issued_envelope(tenant_id, issuance["audit_ref"])

        conducted = conduct_requested_simulation(
            envelope=envelope,
            tenant_id=str(tenant_id),
            presented_token=token,
            source_issuance_envelope_hash=issuance["envelope_hash"],
            total_budget_minor=777_777,
            currency="USD",
            channels=SUFFICIENT_CHANNELS,
        )

        # Read the durable state back as a read-only principal and recompute.
        reader = _role_connection("app_user")
        try:
            with reader.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                cursor.execute(
                    "SELECT channel_evidence, total_budget_minor, currency,"
                    " source_envelope_id, source_semantic_truth_hash,"
                    " input_snapshot_hash, requested_by, sufficiency_verdict,"
                    " sufficiency_reasons, observed_channels,"
                    " observed_conversions, observed_revenue_minor,"
                    " request_authority_principal"
                    " FROM public.b28_simulation_requests WHERE id = %s",
                    (conducted["request_id"],),
                )
                row = cursor.fetchone()
                cursor.execute(
                    "SELECT allocations, solver_invocations, input_snapshot_hash"
                    " FROM public.b28_simulation_results WHERE request_id = %s",
                    (conducted["request_id"],),
                )
                result_row = cursor.fetchone()
            reader.commit()
        finally:
            reader.close()
    finally:
        admin.close()

    (
        channel_evidence,
        budget,
        currency,
        envelope_id,
        truth_hash,
        snapshot_hash,
        requested_by,
        verdict,
        reasons,
        observed_channels,
        observed_conversions,
        observed_revenue,
        authority_principal,
    ) = row

    reconstructed = tuple(
        ChannelEvidence(
            channel_id=item["channel_id"],
            verified_revenue_minor=item["verified_revenue_minor"],
            conversion_count=item["conversion_count"],
        )
        for item in channel_evidence
    )
    assert set(c.channel_id for c in reconstructed) == set(
        c.channel_id for c in SUFFICIENT_CHANNELS
    )

    probe = SimulationRequest(
        request_id="probe",
        tenant_id=str(tenant_id),
        requested_by=requested_by,
        source_envelope_id=envelope_id,
        source_semantic_truth_hash=truth_hash,
        total_budget_minor=budget,
        currency=currency,
        channels=reconstructed,
        requested_at="probe",
    )
    assert compute_input_snapshot_hash(probe) == snapshot_hash
    assert result_row[2] == snapshot_hash
    assert result_row[1] == 1
    assert authority_principal == B28_REQUEST_PRINCIPAL
    assert requested_by.startswith(REQUESTED_BY_PREFIX)

    recomputed = [
        {
            "channel_id": line.channel_id,
            "allocation_minor": line.allocation_minor,
            "weight_basis_points": line.weight_basis_points,
        }
        for line in allocate_budget(
            channels=reconstructed, total_budget_minor=budget
        )
    ]
    assert result_row[0] == recomputed
    assert sum(line["allocation_minor"] for line in recomputed) == budget

    adjudication = adjudicate_sufficiency(reconstructed)
    assert verdict is adjudication.sufficient
    assert tuple(reasons) == adjudication.reasons
    assert observed_channels == adjudication.observed_channels
    assert observed_conversions == adjudication.observed_conversions
    assert observed_revenue == adjudication.observed_revenue_minor


# ---------------------------------------------------------------------------
# Exit Gate 3 -- sufficiency-consequence binding.
# ---------------------------------------------------------------------------


def test_p14_r5_an_insufficient_request_has_no_representable_consequence() -> None:
    """The request may exist and be honest about failing; the result may not."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, client_id, credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
        signed, _registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)
        envelope = _read_back_issued_envelope(tenant_id, issuance["audit_ref"])

        conducted = conduct_requested_simulation(
            envelope=envelope,
            tenant_id=str(tenant_id),
            presented_token=token,
            source_issuance_envelope_hash=issuance["envelope_hash"],
            total_budget_minor=1_000,
            currency="USD",
            channels=INSUFFICIENT_CHANNELS,
        )
        # The application refuses and persists nothing.
        assert conducted["outcome"].reason_code == "simulation_insufficient_evidence"
        assert conducted["proposal"] is None
        assert conducted["identifiers"]["persisted"] == "false"

        # A request that lies about its own verdict is refused outright.
        lying = _attempt(
            B28_REQUEST_PRINCIPAL,
            tenant_id,
            _REQUEST_INSERT_FULL,
            _request_params(
                tenant_id,
                issuance,
                requested_by=f"{REQUESTED_BY_PREFIX}{client_id}",
                client_id=client_id,
                credential_id=credential_id,
                principal=B28_REQUEST_PRINCIPAL,
                channels=INSUFFICIENT_CHANNELS,
                budget=1_000,
                verdict=True,
            ),
        )
        assert "b28_request_sufficiency_not_derived" in lying

        # And the honest insufficient request cannot carry a result, even one
        # whose allocation is exactly what the solver would compute.
        reader = _role_connection("app_user")
        try:
            with reader.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                cursor.execute(
                    "SELECT id, input_snapshot_hash FROM"
                    " public.b28_simulation_requests"
                    " WHERE tenant_id = %s AND sufficiency_verdict = false",
                    (str(tenant_id),),
                )
                insufficient = cursor.fetchone()
            reader.commit()
        finally:
            reader.close()
        assert insufficient is not None, (
            "the insufficient request is not persisted, so the binding cannot"
            " be tested; conduct persists the request before admission"
        )

        lawful_shape = [
            {
                "channel_id": line.channel_id,
                "allocation_minor": line.allocation_minor,
                "weight_basis_points": line.weight_basis_points,
            }
            for line in allocate_budget(
                channels=INSUFFICIENT_CHANNELS, total_budget_minor=1_000
            )
        ]
        refused = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            _RESULT_INSERT,
            (
                str(tenant_id),
                str(insufficient[0]),
                issuance["envelope_id"],
                issuance["semantic_truth_hash"],
                _digest(),
                insufficient[1],
                SOLVER_PROFILE,
                1,
                1_000,
                1_000,
                "USD",
                "simulation_only",
                json.dumps(lawful_shape),
            ),
        )
        assert "b28_result_request_insufficient" in refused
    finally:
        admin.close()


# ---------------------------------------------------------------------------
# Exit Gate 5 -- proposal root-of-trust conservation.
# ---------------------------------------------------------------------------


def test_p14_r5_proposals_derive_only_from_a_real_result() -> None:
    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            token, _client_id, _credential_id = _seed_agent_credential(
                cursor, tenant_id
            )
        signed, _registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)
        envelope = _read_back_issued_envelope(tenant_id, issuance["audit_ref"])
        conducted = conduct_requested_simulation(
            envelope=envelope,
            tenant_id=str(tenant_id),
            presented_token=token,
            source_issuance_envelope_hash=issuance["envelope_hash"],
            total_budget_minor=500_000,
            currency="USD",
            channels=SUFFICIENT_CHANNELS,
        )
        result_id = conducted["identifiers"]["result_id"]
        allocations = json.dumps(
            [
                {
                    "channel_id": line.channel_id,
                    "allocation_minor": line.allocation_minor,
                    "weight_basis_points": line.weight_basis_points,
                }
                for line in conducted["outcome"].allocations
            ]
        )
        proposal_insert = (
            "INSERT INTO public.b28_proposals (tenant_id, result_id,"
            " proposal_ref, source_envelope_id, action_authority, allocations)"
            " VALUES (%s,%s,%s,%s,%s,%s::jsonb)"
        )
        by_app_user = _attempt(
            "app_user",
            tenant_id,
            proposal_insert,
            (
                str(tenant_id),
                result_id,
                "prop_" + uuid.uuid4().hex,
                issuance["envelope_id"],
                "simulation_only",
                allocations,
            ),
        )
        altered = json.loads(allocations)
        altered[0]["allocation_minor"] += 1
        altered[1]["allocation_minor"] -= 1
        by_solver_altered = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            proposal_insert,
            (
                str(tenant_id),
                result_id,
                "prop_" + uuid.uuid4().hex,
                issuance["envelope_id"],
                "simulation_only",
                json.dumps(altered),
            ),
        )
        escalated = _attempt(
            B28_SOLVER_PRINCIPAL,
            tenant_id,
            proposal_insert,
            (
                str(tenant_id),
                result_id,
                "prop_" + uuid.uuid4().hex,
                issuance["envelope_id"],
                "proposal_required",
                allocations,
            ),
        )
    finally:
        admin.close()

    assert by_app_user.startswith("permission denied")
    assert "b28_proposal_disagrees_with_result" in by_solver_altered
    assert "b28_proposal_disagrees_with_result" in escalated
    assert conducted["proposal"].requires_human_approval is True
    assert conducted["proposal"].authority_class == "non_authoritative_proposal"


# ---------------------------------------------------------------------------
# Operational wiring and drift.
# ---------------------------------------------------------------------------


def test_p14_r5_consequence_custody_is_reachable_only_from_persistence() -> None:
    """H-WIRE-V-02: a dedicated credential the whole process can spend is not
    a dedicated credential."""

    assert custody_is_separated()
    with pytest.raises(SimulationCustodyError) as exc:
        with request_custody():
            pass
    assert "untrusted_caller" in str(exc.value)


def test_p14_r5_database_derivations_equal_the_application_authorities() -> None:
    """The PL/pgSQL twins are the same functions, over an adversarial corpus."""

    import random

    rng = random.Random(20260906)
    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            for _ in range(120):
                n = rng.randint(1, 5)
                channels = tuple(
                    ChannelEvidence(
                        channel_id=f"c{index}-{rng.choice('xyz._:-')}",
                        verified_revenue_minor=rng.choice(
                            [0, 1, 7, 999, 400_001, 9_007_199_254_740_741]
                        ),
                        conversion_count=rng.choice([0, 1, 5, 12, 99]),
                    )
                    for index in range(n)
                )
                budget = rng.choice([1, 3, 1000, 999_983, 9_007_199_254_740_740])
                evidence = _evidence_json(channels)
                envelope_id = "env_" + uuid.uuid4().hex
                truth = _digest()

                probe = SimulationRequest(
                    request_id="probe",
                    tenant_id="t",
                    requested_by="agent_client:x",
                    source_envelope_id=envelope_id,
                    source_semantic_truth_hash=truth,
                    total_budget_minor=budget,
                    currency="USD",
                    channels=channels,
                    requested_at="probe",
                )
                cursor.execute(
                    "SELECT public.b28_input_snapshot_hash(%s,%s,%s,%s,%s::jsonb)",
                    (envelope_id, truth, budget, "USD", evidence),
                )
                assert cursor.fetchone()[0] == compute_input_snapshot_hash(probe)

                cursor.execute(
                    "SELECT sufficient, reasons, observed_channels,"
                    " observed_conversions, observed_revenue_minor"
                    " FROM public.b28_adjudicate_sufficiency(%s::jsonb)",
                    (evidence,),
                )
                db_suff = cursor.fetchone()
                py_suff = adjudicate_sufficiency(channels)
                assert db_suff[0] is py_suff.sufficient
                assert tuple(db_suff[1]) == py_suff.reasons
                assert db_suff[2] == py_suff.observed_channels
                assert db_suff[3] == py_suff.observed_conversions
                assert db_suff[4] == py_suff.observed_revenue_minor

                if sum(c.verified_revenue_minor for c in channels) <= 0:
                    continue
                cursor.execute(
                    "SELECT public.b28_recompute_allocation(%s::jsonb, %s)",
                    (evidence, budget),
                )
                assert cursor.fetchone()[0] == [
                    {
                        "channel_id": line.channel_id,
                        "allocation_minor": line.allocation_minor,
                        "weight_basis_points": line.weight_basis_points,
                    }
                    for line in allocate_budget(
                        channels=channels, total_budget_minor=budget
                    )
                ]
    finally:
        admin.close()


def test_p14_r5_governed_constants_are_mirrored_by_the_migration() -> None:
    """A constant that moves in one place and not the other is merge-blocking."""

    from pathlib import Path

    migration = (
        Path(__file__).resolve().parents[3]
        / "alembic/versions/007_skeldir_foundation"
        / "202609061200_b25_p14_r5_causal_authority.py"
    ).read_text(encoding="utf-8")

    for constant in (
        f'_SOLVER_PROFILE = "{SOLVER_PROFILE}"',
        f'_SUFFICIENCY_POLICY_VERSION = "{SUFFICIENCY_POLICY_VERSION}"',
        f"_MIN_CHANNELS = {MIN_CHANNELS}",
        f"_MIN_TOTAL_CONVERSIONS = {MIN_TOTAL_CONVERSIONS}",
        f"_MIN_CHANNELS_WITH_EVIDENCE = {MIN_CHANNELS_WITH_EVIDENCE}",
        f"_MIN_TOTAL_REVENUE_MINOR = {MIN_TOTAL_REVENUE_MINOR}",
        f'_REQUEST_PRINCIPAL = "{B28_REQUEST_PRINCIPAL}"',
        f'_SOLVER_PRINCIPAL = "{B28_SOLVER_PRINCIPAL}"',
    ):
        assert constant in migration, f"migration no longer mirrors: {constant}"


def test_p14_r5_no_runtime_principal_holds_b28_insert() -> None:
    """The privilege layer refuses before any trigger runs."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT r.rolname, c.relname,"
                " has_table_privilege(r.rolname, c.oid, 'INSERT'),"
                " has_table_privilege(r.rolname, c.oid, 'UPDATE'),"
                " has_table_privilege(r.rolname, c.oid, 'DELETE')"
                " FROM pg_class c CROSS JOIN pg_roles r"
                " WHERE c.relname IN ('b28_simulation_requests',"
                " 'b28_simulation_results','b28_proposals')"
                " AND r.rolname IN ('app_user','app_worker','app_rw','app_ro',"
                " 'app_trust_issuer','app_trust_signer','app_dispatch_publisher',"
                " 'app_celery_transport','app_b28_requester','app_b28_solver')"
                " ORDER BY 2, 1"
            )
            matrix = {(row[0], row[1]): (row[2], row[3], row[4]) for row in cursor}

            cursor.execute(
                "SELECT rolname, rolsuper, rolbypassrls FROM pg_roles"
                " WHERE rolname IN ('app_b28_requester','app_b28_solver')"
            )
            flags = {row[0]: (row[1], row[2]) for row in cursor}

            cursor.execute(
                "SELECT member.rolname, grantor.rolname"
                " FROM pg_auth_members m"
                " JOIN pg_roles member ON member.oid = m.member"
                " JOIN pg_roles grantor ON grantor.oid = m.roleid"
                " WHERE member.rolname IN ('app_b28_requester','app_b28_solver')"
                " OR grantor.rolname IN ('app_b28_requester','app_b28_solver')"
            )
            memberships = cursor.fetchall()
    finally:
        admin.close()

    for relation in (
        "b28_simulation_requests",
        "b28_simulation_results",
        "b28_proposals",
    ):
        for role in ("app_user", "app_worker", "app_rw", "app_ro"):
            assert matrix[(role, relation)] == (False, False, False), (
                f"{role} still writes {relation}"
            )

    assert matrix[("app_b28_requester", "b28_simulation_requests")][0] is True
    assert matrix[("app_b28_requester", "b28_simulation_results")][0] is False
    assert matrix[("app_b28_requester", "b28_proposals")][0] is False
    assert matrix[("app_b28_solver", "b28_simulation_requests")][0] is False
    assert matrix[("app_b28_solver", "b28_simulation_results")][0] is True
    assert matrix[("app_b28_solver", "b28_proposals")][0] is True

    # Append-only holds at the privilege layer for the dedicated authorities too.
    for role in ("app_b28_requester", "app_b28_solver"):
        for relation in (
            "b28_simulation_requests",
            "b28_simulation_results",
            "b28_proposals",
        ):
            assert matrix[(role, relation)][1] is False
            assert matrix[(role, relation)][2] is False
        assert flags[role] == (False, False)

    assert memberships == [], f"the causal authorities are entangled: {memberships}"
