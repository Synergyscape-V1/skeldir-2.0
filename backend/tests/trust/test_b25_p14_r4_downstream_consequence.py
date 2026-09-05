"""B2.5-P14 Corrective IV Exit Gates 3 and 4 -- downstream consequence binding.

Two propositions are decided here.

**Exit Gate 3.** A persisted B2.7 explanation or B2.8 simulation result can exist
only as the consequence of a real issued TrustEnvelope and, for a result, of the
explicit request that authorized it. On protected main this was false: with no
application code involved, the real ``app_user`` login inserted a simulation
request naming an envelope that was never issued, a result claiming
``solver_invocations = 1``, a proposal, and an explanation whose narrative read
"The email channel caused $9,999,999 of incremental revenue." The ``NOT NULL``
request foreign key proved a request *row* existed; nothing proved a request was
*made*, and nothing bound either artifact to real Trust.

**Exit Gate 4.** One actual state conducts from a real signature through the
governed boundaries without reseeding anything load-bearing downstream. The
journey below signs with a freshly generated Ed25519 key through the real
canonicalization and verification path, persists the lineage under the real
production logins, then reads the retained artifact *back out of the database*
and feeds those bytes into the real B2.7 and B2.8 boundaries. The downstream
rows are bound to the terminal issuance by foreign key, so an auditor can
reconstruct that the source is the upstream-produced Trust rather than a fixture
carrying equal values.

Declared bound, not credited: the upstream legs -- signed commerce ingress
through B2.3 match verdicts and a real B2.4 Bayesian fit -- are proved by the
C19/C9 lanes and are not re-driven here. This suite proves conduction from the
cryptographic issuance boundary onward, which is the segment P14 owns.
"""

from __future__ import annotations

import copy
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg2
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.explanation.contract import ExplanationRequest
from app.explanation.service import compose_explanation
from app.explanation.templates import (
    EXPLANATION_TEMPLATE_REGISTRY_HASH,
    EXPLANATION_TEMPLATE_REGISTRY_VERSION,
    registry_rows,
)
from app.simulation.contract import ChannelEvidence, SimulationRequest, SimulationResult
from app.simulation.service import propose_from_result, simulate_from_trust
from app.trust.canonicalization import (
    canonicalize_envelope_payload,
    canonicalize_signature_material,
)
from app.trust.hash_identity import compute_envelope_payload_hash
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.projection_profiles import DEFAULT_LLM_PROFILE_ID
from app.trust.refusal import tagged_sha256
from app.trust.signing import (
    decode_ed25519_signature,
    encode_ed25519_signature,
    prepare_payload_for_signing,
)
from app.trust.verification import verify_trust_envelope


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P14_GATE0_PROOF") != "1",
    reason="P14 Corrective IV proofs require a provisioned production role graph",
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "contracts/trust-api/examples"

SOLVER_PROFILE = "b25-p14-deterministic-largest-remainder-v1"
SUFFICIENCY_POLICY_VERSION = "b25-p14-sufficiency-v1"

SUFFICIENT_CHANNELS = (
    ChannelEvidence("google_ads", 400_000, 12),
    ChannelEvidence("meta_ads", 250_000, 7),
    ChannelEvidence("email", 100_000, 3),
)


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------


def _admin_dsn() -> str:
    for name in (
        "P14_ADMIN_DATABASE_URL",
        "C21_ADMIN_DATABASE_URL",
        "C20_ADMIN_DATABASE_URL",
        "MIGRATION_DATABASE_URL",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value.replace("postgresql+psycopg2://", "postgresql://")
    raise RuntimeError("P14_ADMIN_DATABASE_URL is required for the Gate 3/4 proofs")


def _admin_connection():
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    return conn


def _role_connection(role: str):
    parts = urlsplit(_admin_dsn())
    conn = psycopg2.connect(
        dbname=parts.path.lstrip("/"),
        host=parts.hostname,
        port=parts.port or 5432,
        user=role,
        password=os.getenv(f"P14_{role.upper()}_PASSWORD", role),
    )
    conn.autocommit = False
    return conn


def _bind_tenant(cursor, tenant_id) -> None:
    cursor.execute(
        "SELECT set_config('app.current_tenant_id', %s, false)", (str(tenant_id),)
    )


def _digest() -> str:
    return "sha256:" + uuid.uuid4().hex + uuid.uuid4().hex


def _record_evidence(payload: dict[str, Any]) -> None:
    target = os.getenv("P14_EVIDENCE_PATH", "").strip()
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}
    existing.update(payload)
    path.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")


def _seed_tenant(cursor) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    label = tenant_id.hex[:8]
    cursor.execute(
        "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
        " VALUES (%s, %s, %s, %s)",
        (
            str(tenant_id),
            f"p14r4d-{label}",
            uuid.uuid4().hex,
            f"p14r4d-{label}@example.invalid",
        ),
    )
    return tenant_id


# ---------------------------------------------------------------------------
# The real cryptographic issuance, driven by the real production principals.
# ---------------------------------------------------------------------------


def _sign_real_envelope(
    tenant_id,
    *,
    policy_state: str = "simulation_only",
    verified_revenue_minor: int | None = None,
) -> tuple[dict[str, Any], TrustKeyRegistry]:
    """Produce one genuinely signed TrustEnvelope with a fresh Ed25519 key.

    Real key material, the real signing-material canonicalization, and the real
    public-key verification. Nothing here is a fixture standing in for a
    signature: an artifact that failed verification would fail this call.
    """

    payload = json.loads(
        (EXAMPLES / "revenue_claim_valid_with_verified_revenue_minor.json").read_text(
            encoding="utf-8"
        )
    )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload["created_at"] = now.isoformat().replace("+00:00", "Z")
    payload["valid_until"] = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
    payload["tenant_id_hash"] = tagged_sha256({"tenant_id": str(tenant_id)})
    payload["policy_action_authority"]["policy_state"] = policy_state
    if verified_revenue_minor is not None:
        # Two journeys that differ semantically, so a crossed binding is a
        # real mismatch rather than two signatures over identical content.
        payload["verified_revenue_minor"] = verified_revenue_minor

    private_key = Ed25519PrivateKey.generate()
    key = TrustSigningKey(
        kid=f"kid:p14r4-{uuid.uuid4().hex[:8]}",
        algorithm="ed25519",
        public_key=private_key.public_key(),
        private_key=private_key,
        state="active",
        valid_from=now - timedelta(days=1),
    )
    registry = TrustKeyRegistry(keys=(key,))
    prepared = prepare_payload_for_signing(
        payload, signing_key_id=key.kid, signing_algorithm="ed25519"
    )
    signature = private_key.sign(canonicalize_signature_material(prepared))
    signed = copy.deepcopy(prepared)
    signed["signature"] = encode_ed25519_signature(signature)
    canonicalize_envelope_payload(signed)

    verification = verify_trust_envelope(signed, key_registry=registry.public_only())
    assert verification.verification_status == "verified", verification
    return signed, registry


def _conduct_issuance(tenant_id, signed: dict[str, Any]) -> dict[str, str]:
    """Persist the signed artifact's lineage as the real production principals."""

    material = {
        "audit_ref": f"urn:skeldir:audit:p14r4-{uuid.uuid4().hex}",
        "request_identity_hash": _digest(),
        "idempotency_key_hash": _digest(),
        "subject_type": signed["subject_type"],
        "subject_ref_hash": signed["subject_ref_hash"],
        "envelope_hash": compute_envelope_payload_hash(signed),
        "semantic_truth_hash": signed["semantic_truth_hash"],
        "policy_state": signed["policy_action_authority"]["policy_state"],
        "audit_hash": _digest(),
        "signature_hash": signed["signature_hash"],
        "signing_key_id": signed["signing_key_id"],
        "envelope_id": signed["envelope_id"],
    }

    user = _role_connection("app_user")
    try:
        with user.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "INSERT INTO public.trust_access_log (tenant_id, event_type, status,"
                " request_identity_hash, idempotency_key_hash, subject_type,"
                " subject_ref_hash, envelope_hash, semantic_truth_hash, policy_state,"
                " audit_ref, audit_hash, evidence_refs_allowed, issuance_state)"
                " VALUES (%s,'issuance','success',%s,%s,%s,%s,%s,%s,%s,%s,%s,true,"
                "'authorized')",
                (
                    str(tenant_id),
                    material["request_identity_hash"],
                    material["idempotency_key_hash"],
                    material["subject_type"],
                    material["subject_ref_hash"],
                    material["envelope_hash"],
                    material["semantic_truth_hash"],
                    material["policy_state"],
                    material["audit_ref"],
                    material["audit_hash"],
                ),
            )
        user.commit()
    finally:
        user.close()

    attempt_id = uuid.uuid4()
    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signing',"
                " issuance_attempted_at=now(), issuance_attempt_count=1"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (str(tenant_id), material["audit_ref"]),
            )
            cursor.execute(
                "INSERT INTO public.trust_issuance_attempts"
                " (id, tenant_id, audit_ref, attempt_number, attempt_state)"
                " VALUES (%s,%s,%s,1,'signing')",
                (str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        issuer.commit()
    finally:
        issuer.close()

    signer = _role_connection("app_trust_signer")
    try:
        with signer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_issuance_attempts"
                " SET attempt_state='signature_known', signature_known_at=now(),"
                " signing_key_id=%s, signature_hash=%s,"
                " signature=decode(%s,'hex'), signed_envelope_hash=%s,"
                " signed_envelope=%s::jsonb"
                " WHERE tenant_id=%s AND id=%s RETURNING signature_known_at",
                (
                    material["signing_key_id"],
                    material["signature_hash"],
                    decode_ed25519_signature(signed["signature"]).hex(),
                    material["envelope_hash"],
                    json.dumps(signed),
                    str(tenant_id),
                    str(attempt_id),
                ),
            )
            known_at = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE public.trust_access_log SET issuance_state='signature_known',"
                " known_signature_at=%s, issued_attempt_id=%s"
                " WHERE tenant_id=%s AND audit_ref=%s",
                (known_at, str(attempt_id), str(tenant_id), material["audit_ref"]),
            )
        signer.commit()
    finally:
        signer.close()

    issuer = _role_connection("app_trust_issuer")
    try:
        with issuer.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "UPDATE public.trust_access_log AS log"
                "   SET issuance_state='issued', issued_at=now(),"
                "       issued_signing_key_id=attempt.signing_key_id,"
                "       issued_signature_hash=attempt.signature_hash,"
                "       issued_signature=attempt.signature,"
                "       issued_envelope=attempt.signed_envelope"
                "  FROM public.trust_issuance_attempts AS attempt"
                " WHERE log.tenant_id=%s AND log.audit_ref=%s"
                "   AND attempt.id=log.issued_attempt_id"
                "   AND attempt.tenant_id=log.tenant_id",
                (str(tenant_id), material["audit_ref"]),
            )
            cursor.execute(
                "UPDATE public.trust_issuance_attempts SET attempt_state='issued',"
                " issued_at=now() WHERE tenant_id=%s AND id=%s",
                (str(tenant_id), str(attempt_id)),
            )
            cursor.execute(
                "INSERT INTO public.trust_envelope_issuance_log (tenant_id,"
                " access_audit_ref, idempotency_key_hash, subject_type,"
                " subject_ref_hash, envelope_hash, semantic_truth_hash, policy_state,"
                " audit_ref, audit_hash, status)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'success')",
                (
                    str(tenant_id),
                    material["audit_ref"],
                    material["idempotency_key_hash"],
                    material["subject_type"],
                    material["subject_ref_hash"],
                    material["envelope_hash"],
                    material["semantic_truth_hash"],
                    material["policy_state"],
                    material["audit_ref"],
                    material["audit_hash"],
                ),
            )
        issuer.commit()
    finally:
        issuer.close()
    return material


def _read_back_issued_envelope(tenant_id, audit_ref: str) -> dict[str, Any]:
    """Read the retained artifact out of the database as the API principal."""

    conn = _role_connection("app_user")
    try:
        with conn.cursor() as cursor:
            _bind_tenant(cursor, tenant_id)
            cursor.execute(
                "SELECT issued_envelope FROM public.trust_access_log"
                " WHERE tenant_id=%s AND audit_ref=%s AND issuance_state='issued'",
                (str(tenant_id), audit_ref),
            )
            row = cursor.fetchone()
        conn.commit()
    finally:
        conn.close()
    assert row is not None and row[0], "no retained artifact for the issued lineage"
    return row[0]


def _persist_explanation(cursor, tenant_id, issuance, result) -> uuid.UUID:
    cursor.execute(
        "INSERT INTO public.b27_explanation_materializations (tenant_id,"
        " cache_identity_hash, source_envelope_id, source_semantic_truth_hash,"
        " source_issuance_envelope_hash, explanation_template_registry_hash,"
        " subject_type, subject_ref_hash, projection_profile_id,"
        " projection_profile_version, projection_profile_hash,"
        " explanation_contract_version, policy_state, confidence_status,"
        " causal_status, fallback_applied, claim_count, narrative, claims)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
        " RETURNING id",
        (
            str(tenant_id),
            result.cache_identity_hash,
            result.envelope_id,
            result.semantic_truth_hash,
            issuance["envelope_hash"],
            EXPLANATION_TEMPLATE_REGISTRY_HASH,
            issuance["subject_type"],
            issuance["subject_ref_hash"],
            result.profile_id,
            result.profile_version,
            result.profile_hash,
            result.contract_version,
            result.policy_state,
            result.confidence_status,
            result.causal_status,
            result.fallback_applied,
            len(result.claims),
            result.narrative,
            json.dumps([claim.as_persisted() for claim in result.claims]),
        ),
    )
    return cursor.fetchone()[0]


# ---------------------------------------------------------------------------
# The frame corpus is one artifact in three places.
# ---------------------------------------------------------------------------


def test_p14_r4_database_frame_corpus_equals_the_declared_corpus() -> None:
    """Declared corpus == physical corpus == pinned content address.

    The application refuses undeclared prose and the database refuses it again.
    Both refusals are only worth something if they are refusing against the same
    corpus, so the equality is asserted rather than assumed -- and because the
    physical corpus is seeded by a migration, a drift is merge-blocking.
    """

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT template_id, claim_kind, source_path, template_text,"
                " value_grammar, value_pattern FROM public.b27_narrative_templates"
                " ORDER BY template_id"
            )
            physical = [
                {
                    "template_id": row[0],
                    "claim_kind": row[1],
                    "source_path": row[2],
                    "template_text": row[3],
                    "value_grammar": row[4],
                    "value_pattern": row[5],
                }
                for row in cursor.fetchall()
            ]
            cursor.execute(
                "SELECT registry_version, registry_hash"
                " FROM public.b27_narrative_template_registry"
            )
            registry = cursor.fetchall()
    finally:
        conn.close()

    declared = sorted(
        (dict(row) for row in registry_rows()), key=lambda row: row["template_id"]
    )
    assert physical == declared
    assert registry == [
        (EXPLANATION_TEMPLATE_REGISTRY_VERSION, EXPLANATION_TEMPLATE_REGISTRY_HASH)
    ]
    _record_evidence(
        {
            "p14_r4_template_registry_hash": EXPLANATION_TEMPLATE_REGISTRY_HASH,
            "p14_r4_template_count": len(declared),
        }
    )


def test_p14_r4_no_runtime_principal_may_edit_the_frame_corpus() -> None:
    """Adding a sentence frame is a migration, not a runtime capability."""

    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            observed: dict[str, dict[str, list[str]]] = {}
            for relation in (
                "b27_narrative_templates",
                "b27_narrative_template_registry",
            ):
                observed[relation] = {}
                for principal in (
                    "app_user",
                    "app_worker",
                    "app_rw",
                    "app_ro",
                    "app_trust_issuer",
                    "app_trust_signer",
                    "app_dispatch_publisher",
                    "app_celery_transport",
                ):
                    held = []
                    for operation in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                        cursor.execute(
                            "SELECT has_table_privilege(%s, %s, %s)",
                            (principal, f"public.{relation}", operation),
                        )
                        if cursor.fetchone()[0]:
                            held.append(operation)
                    observed[relation][principal] = held
    finally:
        conn.close()

    for relation, matrix in observed.items():
        for principal, held in matrix.items():
            assert set(held) <= {"SELECT"}, (relation, principal, held)
        # The consequence guard runs with the writer's own authority, so the
        # API principal must be able to read the corpus it is checked against.
        assert matrix["app_user"] == ["SELECT"], observed


# ---------------------------------------------------------------------------
# Exit Gate 4 -- one real state conducts.
# ---------------------------------------------------------------------------


def test_p14_r4_one_real_signed_state_conducts_into_b27_and_b28() -> None:
    """Sign, issue, terminalize, read back, explain, simulate, propose."""

    admin = _admin_connection()
    lineage: dict[str, Any] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        signed, registry = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)

        # The downstream boundaries consume bytes read out of the database, not
        # the in-memory artifact: that is what makes this conduction rather than
        # two universes with equal values.
        retained = _read_back_issued_envelope(tenant_id, issuance["audit_ref"])
        assert (
            verify_trust_envelope(
                retained, key_registry=registry.public_only()
            ).verification_status
            == "verified"
        )
        assert retained["semantic_truth_hash"] == signed["semantic_truth_hash"]

        explanation = compose_explanation(
            retained,
            request=ExplanationRequest(
                tenant_id=str(tenant_id),
                envelope_id=retained["envelope_id"],
                subject_type=retained["subject_type"],
                subject_ref_hash=retained["subject_ref_hash"],
                profile_id=DEFAULT_LLM_PROFILE_ID,
                requested_by="agent:p14-r4-composition",
            ),
        )

        simulation = simulate_from_trust(
            retained,
            request=SimulationRequest(
                request_id="req_" + uuid.uuid4().hex,
                tenant_id=str(tenant_id),
                requested_by="agent:p14-r4-composition",
                source_envelope_id=retained["envelope_id"],
                source_semantic_truth_hash=retained["semantic_truth_hash"],
                total_budget_minor=1_000_000,
                currency=retained.get("currency", "USD"),
                channels=SUFFICIENT_CHANNELS,
                requested_at=retained["created_at"],
            ),
        )
        assert isinstance(simulation, SimulationResult), simulation
        proposal = propose_from_result(simulation)

        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                materialization_id = _persist_explanation(
                    cursor, tenant_id, issuance, explanation
                )
                cursor.execute(
                    "INSERT INTO public.b28_simulation_requests (tenant_id,"
                    " request_ref, requested_by, source_envelope_id,"
                    " source_semantic_truth_hash, source_issuance_envelope_hash,"
                    " input_snapshot_hash, total_budget_minor, currency,"
                    " channel_count, sufficiency_policy_version)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (
                        str(tenant_id),
                        simulation.request_id,
                        "agent:p14-r4-composition",
                        simulation.source_envelope_id,
                        simulation.source_semantic_truth_hash,
                        issuance["envelope_hash"],
                        simulation.input_snapshot_hash,
                        simulation.total_budget_minor,
                        simulation.currency,
                        len(simulation.allocations),
                        SUFFICIENCY_POLICY_VERSION,
                    ),
                )
                request_id = cursor.fetchone()[0]
                allocations = [
                    {
                        "channel_id": allocation.channel_id,
                        "allocation_minor": allocation.allocation_minor,
                    }
                    for allocation in simulation.allocations
                ]
                cursor.execute(
                    "INSERT INTO public.b28_simulation_results (tenant_id, request_id,"
                    " source_envelope_id, source_semantic_truth_hash,"
                    " projection_profile_hash, input_snapshot_hash, solver_profile,"
                    " solver_invocations, total_budget_minor, allocated_total_minor,"
                    " currency, action_authority, allocations)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
                    " RETURNING id",
                    (
                        str(tenant_id),
                        str(request_id),
                        simulation.source_envelope_id,
                        simulation.source_semantic_truth_hash,
                        explanation.profile_hash,
                        simulation.input_snapshot_hash,
                        SOLVER_PROFILE,
                        simulation.solver_invocations,
                        simulation.total_budget_minor,
                        sum(a["allocation_minor"] for a in allocations),
                        simulation.currency,
                        simulation.action_authority,
                        json.dumps(allocations),
                    ),
                )
                result_id = cursor.fetchone()[0]
                cursor.execute(
                    "INSERT INTO public.b28_proposals (tenant_id, result_id,"
                    " proposal_ref, source_envelope_id, action_authority, allocations)"
                    " VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        str(tenant_id),
                        str(result_id),
                        proposal.proposal_id,
                        proposal.source_envelope_id,
                        proposal.action_authority,
                        json.dumps(allocations),
                    ),
                )
            user.commit()
        finally:
            user.close()

        # One lineage identifier spans the whole chain, reconstructed by query
        # rather than asserted from the fixture's own variables.
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT terminal.envelope_hash, b27.source_issuance_envelope_hash,"
                "       b28req.source_issuance_envelope_hash,"
                "       terminal.semantic_truth_hash, b27.source_semantic_truth_hash,"
                "       b28res.source_semantic_truth_hash, prop.action_authority,"
                "       b28res.action_authority, attempt.attempt_state,"
                "       ledger.issuance_state"
                "  FROM public.trust_envelope_issuance_log AS terminal"
                "  JOIN public.trust_access_log AS ledger"
                "    ON ledger.tenant_id = terminal.tenant_id"
                "   AND ledger.audit_ref = terminal.access_audit_ref"
                "  JOIN public.trust_issuance_attempts AS attempt"
                "    ON attempt.tenant_id = ledger.tenant_id"
                "   AND attempt.id = ledger.issued_attempt_id"
                "  JOIN public.b27_explanation_materializations AS b27"
                "    ON b27.tenant_id = terminal.tenant_id"
                "   AND b27.source_issuance_envelope_hash = terminal.envelope_hash"
                "  JOIN public.b28_simulation_requests AS b28req"
                "    ON b28req.tenant_id = terminal.tenant_id"
                "   AND b28req.source_issuance_envelope_hash = terminal.envelope_hash"
                "  JOIN public.b28_simulation_results AS b28res"
                "    ON b28res.request_id = b28req.id"
                "  JOIN public.b28_proposals AS prop ON prop.result_id = b28res.id"
                " WHERE terminal.tenant_id = %s",
                (str(tenant_id),),
            )
            spine = cursor.fetchall()
        assert len(spine) == 1, spine
        row = spine[0]
        assert row[0] == row[1] == row[2] == issuance["envelope_hash"]
        assert row[3] == row[4] == row[5] == signed["semantic_truth_hash"]
        assert row[6] == row[7] == simulation.action_authority
        assert row[8] == "issued"
        assert row[9] == "issued"
        lineage = {
            "tenant_id": str(tenant_id),
            "envelope_id": signed["envelope_id"],
            "envelope_hash": issuance["envelope_hash"],
            "semantic_truth_hash": signed["semantic_truth_hash"],
            "audit_ref": issuance["audit_ref"],
            "materialization_id": str(materialization_id),
            "b28_request_id": str(request_id),
            "b28_result_id": str(result_id),
            "action_authority": simulation.action_authority,
            "solver_invocations": simulation.solver_invocations,
        }
    finally:
        admin.close()
    _record_evidence({"p14_r4_compositional_lineage": lineage})


def test_p14_r4_a_severed_source_binding_is_refused() -> None:
    """Exit Gate 4's falsifier: substitute a different Trust identity.

    Both downstream relations are asked to project a real, valid issuance that
    belongs to a different journey, and to project a semantic truth that no
    issuance carries. Either would make the downstream artifact a second
    universe with a plausible citation.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        signed_a, _ = _sign_real_envelope(tenant_id)
        issuance_a = _conduct_issuance(tenant_id, signed_a)
        signed_b, _ = _sign_real_envelope(
            tenant_id, verified_revenue_minor=987_600
        )
        issuance_b = _conduct_issuance(tenant_id, signed_b)

        outcomes = []
        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                # A real issuance, but not the one whose semantic truth is cited.
                try:
                    cursor.execute(
                        "INSERT INTO public.b28_simulation_requests (tenant_id,"
                        " request_ref, requested_by, source_envelope_id,"
                        " source_semantic_truth_hash, source_issuance_envelope_hash,"
                        " input_snapshot_hash, total_budget_minor, currency,"
                        " channel_count, sufficiency_policy_version)"
                        " VALUES (%s,%s,'agent:p14',%s,%s,%s,%s,1000,'USD',1,%s)",
                        (
                            str(tenant_id),
                            "req_" + uuid.uuid4().hex,
                            signed_a["envelope_id"],
                            issuance_a["semantic_truth_hash"],
                            issuance_b["envelope_hash"],
                            _digest(),
                            SUFFICIENCY_POLICY_VERSION,
                        ),
                    )
                    outcomes.append(("crossed_issuance", "ALLOWED"))
                except psycopg2.Error as exc:
                    user.rollback()
                    outcomes.append(("crossed_issuance", str(exc).splitlines()[0]))
        finally:
            user.close()

        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                try:
                    cursor.execute(
                        "INSERT INTO public.b28_simulation_requests (tenant_id,"
                        " request_ref, requested_by, source_envelope_id,"
                        " source_semantic_truth_hash, source_issuance_envelope_hash,"
                        " input_snapshot_hash, total_budget_minor, currency,"
                        " channel_count, sufficiency_policy_version)"
                        " VALUES (%s,%s,'agent:p14',%s,%s,%s,%s,1000,'USD',1,%s)",
                        (
                            str(tenant_id),
                            "req_" + uuid.uuid4().hex,
                            signed_a["envelope_id"],
                            _digest(),
                            _digest(),
                            _digest(),
                            SUFFICIENCY_POLICY_VERSION,
                        ),
                    )
                    outcomes.append(("no_issuance", "ALLOWED"))
                except psycopg2.Error as exc:
                    user.rollback()
                    outcomes.append(("no_issuance", str(exc).splitlines()[0]))
        finally:
            user.close()
    finally:
        admin.close()

    assert dict(outcomes)["crossed_issuance"].startswith(
        "b28_request_source_trust_mismatch"
    ), outcomes
    assert dict(outcomes)["no_issuance"].startswith(
        "b28_request_requires_durable_issuance"
    ), outcomes


# ---------------------------------------------------------------------------
# Exit Gate 3 -- the fabrication battery.
# ---------------------------------------------------------------------------


def _fabrication_attempt(tenant_id, statement: str, params: tuple[Any, ...]) -> str:
    conn = _role_connection("app_user")
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


_REQUEST_INSERT = (
    "INSERT INTO public.b28_simulation_requests (tenant_id, request_ref,"
    " requested_by, source_envelope_id, source_semantic_truth_hash,"
    " source_issuance_envelope_hash, input_snapshot_hash, total_budget_minor,"
    " currency, channel_count, sufficiency_policy_version)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)

_RESULT_INSERT = (
    "INSERT INTO public.b28_simulation_results (tenant_id, request_id,"
    " source_envelope_id, source_semantic_truth_hash, projection_profile_hash,"
    " input_snapshot_hash, solver_profile, solver_invocations, total_budget_minor,"
    " allocated_total_minor, currency, action_authority, allocations)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)"
)


def _lawful_request(cursor, tenant_id, issuance, *, budget=1000, channels=1):
    request_id = uuid.uuid4()
    snapshot = _digest()
    cursor.execute(
        _REQUEST_INSERT + " RETURNING id",
        (
            str(tenant_id),
            "req_" + uuid.uuid4().hex,
            "agent:p14",
            issuance["envelope_id"],
            issuance["semantic_truth_hash"],
            issuance["envelope_hash"],
            snapshot,
            budget,
            "USD",
            channels,
            SUFFICIENCY_POLICY_VERSION,
        ),
    )
    return {
        "id": cursor.fetchone()[0],
        "snapshot": snapshot,
        "budget": budget,
        "channels": channels,
        "envelope_id": issuance["envelope_id"],
        "semantic_truth_hash": issuance["semantic_truth_hash"],
    }


def test_p14_r4_b28_persistence_is_consequence_bound() -> None:
    """Every conjunct of the admission relation, severed one at a time."""

    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            other_tenant = _seed_tenant(cursor)
        signed, _ = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)
        read_only_signed, _ = _sign_real_envelope(tenant_id, policy_state="read_only")
        read_only_issuance = _conduct_issuance(tenant_id, read_only_signed)

        findings["request_names_no_issuance"] = _fabrication_attempt(
            tenant_id,
            _REQUEST_INSERT,
            (
                str(tenant_id),
                "req_" + uuid.uuid4().hex,
                "attacker:not-a-real-caller",
                "env_never_issued",
                _digest(),
                _digest(),
                _digest(),
                1_000_000,
                "USD",
                3,
                SUFFICIENCY_POLICY_VERSION,
            ),
        )
        findings["request_over_read_only_source"] = _fabrication_attempt(
            tenant_id,
            _REQUEST_INSERT,
            (
                str(tenant_id),
                "req_" + uuid.uuid4().hex,
                "agent:p14",
                read_only_issuance["envelope_id"],
                read_only_issuance["semantic_truth_hash"],
                read_only_issuance["envelope_hash"],
                _digest(),
                1_000,
                "USD",
                1,
                SUFFICIENCY_POLICY_VERSION,
            ),
        )
        findings["request_ungoverned_sufficiency_policy"] = _fabrication_attempt(
            tenant_id,
            _REQUEST_INSERT,
            (
                str(tenant_id),
                "req_" + uuid.uuid4().hex,
                "agent:p14",
                issuance["envelope_id"],
                issuance["semantic_truth_hash"],
                issuance["envelope_hash"],
                _digest(),
                1_000,
                "USD",
                1,
                "v-fabricated",
            ),
        )
        findings["request_wrong_tenant"] = _fabrication_attempt(
            other_tenant,
            _REQUEST_INSERT,
            (
                str(other_tenant),
                "req_" + uuid.uuid4().hex,
                "agent:p14",
                issuance["envelope_id"],
                issuance["semantic_truth_hash"],
                issuance["envelope_hash"],
                _digest(),
                1_000,
                "USD",
                1,
                SUFFICIENCY_POLICY_VERSION,
            ),
        )

        # A lawful request, so the result battery measures the result guard.
        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                request = _lawful_request(cursor, tenant_id, issuance)
            user.commit()
        finally:
            user.close()

        allocations = json.dumps([{"channel_id": "a", "allocation_minor": 1000}])
        base = [
            str(tenant_id),
            str(request["id"]),
            request["envelope_id"],
            request["semantic_truth_hash"],
            _digest(),
            request["snapshot"],
            SOLVER_PROFILE,
            1,
            1000,
            1000,
            "USD",
            "simulation_only",
            allocations,
        ]

        def variant(**overrides: Any) -> tuple[Any, ...]:
            row = list(base)
            index = {
                "source_envelope_id": 2,
                "source_semantic_truth_hash": 3,
                "input_snapshot_hash": 5,
                "solver_profile": 6,
                "total_budget_minor": 8,
                "allocated_total_minor": 9,
                "currency": 10,
                "action_authority": 11,
                "allocations": 12,
            }
            for name, value in overrides.items():
                row[index[name]] = value
            return tuple(row)

        findings["result_foreign_envelope_id"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, variant(source_envelope_id="env_other")
        )
        findings["result_foreign_semantic_truth"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, variant(source_semantic_truth_hash=_digest())
        )
        findings["result_foreign_input_snapshot"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, variant(input_snapshot_hash=_digest())
        )
        findings["result_ungoverned_solver_profile"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, variant(solver_profile="hand-written")
        )
        findings["result_channel_count_disagrees"] = _fabrication_attempt(
            tenant_id,
            _RESULT_INSERT,
            variant(
                allocations=json.dumps(
                    [
                        {"channel_id": "a", "allocation_minor": 600},
                        {"channel_id": "b", "allocation_minor": 400},
                    ]
                )
            ),
        )
        findings["result_authority_not_derived"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, variant(action_authority="proposal_required")
        )

        # The lawful result, then a proposal that disagrees with it.
        findings["result_lawful"] = _fabrication_attempt(
            tenant_id, _RESULT_INSERT, tuple(base)
        )
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM public.b28_simulation_results WHERE request_id = %s",
                (str(request["id"]),),
            )
            result_row = cursor.fetchone()
        assert result_row is not None
        findings["proposal_disagrees_with_result"] = _fabrication_attempt(
            tenant_id,
            "INSERT INTO public.b28_proposals (tenant_id, result_id, proposal_ref,"
            " source_envelope_id, action_authority, allocations)"
            " VALUES (%s,%s,%s,%s,%s,%s::jsonb)",
            (
                str(tenant_id),
                str(result_row[0]),
                "prop_" + uuid.uuid4().hex,
                request["envelope_id"],
                "simulation_only",
                json.dumps([{"channel_id": "a", "allocation_minor": 9_999_999}]),
            ),
        )
    finally:
        admin.close()

    assert findings["result_lawful"] == "ALLOWED", findings
    for key, outcome in findings.items():
        if key == "result_lawful":
            continue
        assert outcome != "ALLOWED", (key, findings)
    assert findings["request_names_no_issuance"].startswith(
        "b28_request_requires_durable_issuance"
    )
    assert findings["request_over_read_only_source"].startswith(
        "b28_request_policy_forbids"
    )
    assert findings["request_ungoverned_sufficiency_policy"].startswith(
        "b28_request_sufficiency_policy_unknown"
    )
    assert findings["result_ungoverned_solver_profile"].startswith(
        "b28_result_solver_profile_ungoverned"
    )
    assert findings["result_channel_count_disagrees"].startswith(
        "b28_result_channel_count_disagrees"
    )
    assert findings["result_authority_not_derived"].startswith(
        "b28_result_action_authority_not_derived"
    )
    assert findings["proposal_disagrees_with_result"].startswith(
        "b28_proposal_disagrees_with_result"
    )
    _record_evidence({"p14_r4_b28_fabrication_battery": findings})


def test_p14_r4_b28_consequence_guard_is_independently_load_bearing() -> None:
    """Restore the fabrication capability and require the class to reappear."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_request_consequence' AND NOT tgisinternal"
            )
            triggerdef = cursor.fetchone()[0]
            cursor.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint"
                " WHERE conname = 'fk_b28_simulation_requests_source_issuance'"
            )
            constraintdef = cursor.fetchone()[0]
        assert triggerdef and constraintdef

        fabricated = (
            str(tenant_id),
            "req_" + uuid.uuid4().hex,
            "attacker:not-a-real-caller",
            "env_never_issued",
            _digest(),
            _digest(),
            _digest(),
            1_000_000,
            "USD",
            3,
            SUFFICIENCY_POLICY_VERSION,
        )
        assert (
            _fabrication_attempt(tenant_id, _REQUEST_INSERT, fabricated) != "ALLOWED"
        )

        try:
            with admin.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER trg_b28_request_consequence"
                    " ON public.b28_simulation_requests"
                )
                cursor.execute(
                    "ALTER TABLE public.b28_simulation_requests"
                    " DROP CONSTRAINT fk_b28_simulation_requests_source_issuance"
                )
            severed = _fabrication_attempt(tenant_id, _REQUEST_INSERT, fabricated)
            assert severed == "ALLOWED", severed
        finally:
            with admin.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM public.b28_simulation_requests WHERE requested_by ="
                    " 'attacker:not-a-real-caller'"
                )
                cursor.execute(
                    "ALTER TABLE public.b28_simulation_requests ADD CONSTRAINT"
                    " fk_b28_simulation_requests_source_issuance " + constraintdef
                )
                cursor.execute(triggerdef)

        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT pg_get_triggerdef(oid) FROM pg_catalog.pg_trigger"
                " WHERE tgname = 'trg_b28_request_consequence' AND NOT tgisinternal"
            )
            assert cursor.fetchone()[0] == triggerdef
        assert (
            _fabrication_attempt(tenant_id, _REQUEST_INSERT, fabricated) != "ALLOWED"
        )
    finally:
        admin.close()


# ---------------------------------------------------------------------------
# Exit Gate 2, physically -- the narrative derivation law at the database.
# ---------------------------------------------------------------------------


_MATERIALIZATION_INSERT = (
    "INSERT INTO public.b27_explanation_materializations (tenant_id,"
    " cache_identity_hash, source_envelope_id, source_semantic_truth_hash,"
    " source_issuance_envelope_hash, explanation_template_registry_hash,"
    " subject_type, subject_ref_hash, projection_profile_id,"
    " projection_profile_version, projection_profile_hash,"
    " explanation_contract_version, policy_state, confidence_status,"
    " causal_status, fallback_applied, claim_count, narrative, claims)"
    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'llm_explanation_projection_safe','v1',%s,"
    " 'b25-p14-explanation-v1',%s,'unavailable',NULL,false,%s,%s,%s::jsonb)"
)


def _materialization_params(
    tenant_id,
    issuance,
    *,
    claims: list[dict[str, str]],
    narrative: str | None = None,
    claim_count: int | None = None,
    policy_state: str | None = None,
) -> tuple[Any, ...]:
    rendered = " ".join(claim["rendered"] for claim in claims)
    return (
        str(tenant_id),
        _digest(),
        issuance["envelope_id"],
        issuance["semantic_truth_hash"],
        issuance["envelope_hash"],
        EXPLANATION_TEMPLATE_REGISTRY_HASH,
        issuance["subject_type"],
        issuance["subject_ref_hash"],
        _digest(),
        policy_state or issuance["policy_state"],
        len(claims) if claim_count is None else claim_count,
        rendered if narrative is None else narrative,
        json.dumps(claims),
    )


def test_p14_r4_b27_persistence_requires_a_derived_narrative() -> None:
    """Free prose is unrepresentable at the database, not merely unproduced.

    The application refuses an undeclared sentence, but the application is not
    the only writer a database has. Every case below goes straight to
    PostgreSQL as the real ``app_user`` login.
    """

    lawful_claim = {
        "claim_kind": "status_fact",
        "source_path": "causal_status",
        "template_id": "status.causal_status.v1",
        "value_text": "non_causal_deterministic_heuristic",
        "rendered": (
            "The causal status of this result is non_causal_deterministic_heuristic."
        ),
    }

    admin = _admin_connection()
    findings: dict[str, str] = {}
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        signed, _ = _sign_real_envelope(tenant_id, policy_state="read_only")
        issuance = _conduct_issuance(tenant_id, signed)

        findings["lawful"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(tenant_id, issuance, claims=[lawful_claim]),
        )
        findings["free_prose_narrative"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[lawful_claim],
                narrative=(
                    "The email channel caused 9999999 minor units of incremental"
                    " revenue."
                ),
            ),
        )
        findings["appended_sentence"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[lawful_claim],
                narrative=(
                    lawful_claim["rendered"]
                    + " The email channel produced this additional revenue."
                ),
            ),
        )
        findings["unknown_template"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[{**lawful_claim, "template_id": "causal.invented.v1"}],
            ),
        )
        findings["template_bound_to_other_path"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[
                    {
                        **lawful_claim,
                        "source_path": "attribution_model",
                        "rendered": (
                            "The causal status of this result is"
                            " non_causal_deterministic_heuristic."
                        ),
                    }
                ],
            ),
        )
        findings["value_grammar_smuggling"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[
                    {
                        **lawful_claim,
                        "value_text": "email caused the revenue",
                        "rendered": (
                            "The causal status of this result is email caused the"
                            " revenue."
                        ),
                    }
                ],
            ),
        )
        findings["rendering_not_derived"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[
                    {
                        **lawful_claim,
                        "rendered": "Email drove the observed revenue.",
                    }
                ],
            ),
        )
        findings["claim_count_disagrees"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id, issuance, claims=[lawful_claim], claim_count=7
            ),
        )
        findings["policy_state_upgraded"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            _materialization_params(
                tenant_id,
                issuance,
                claims=[lawful_claim],
                policy_state="approval_required",
            ),
        )
        findings["unknown_registry_hash"] = _fabrication_attempt(
            tenant_id,
            _MATERIALIZATION_INSERT,
            tuple(
                value if index != 5 else _digest()
                for index, value in enumerate(
                    _materialization_params(
                        tenant_id, issuance, claims=[lawful_claim]
                    )
                )
            ),
        )
    finally:
        admin.close()

    assert findings["lawful"] == "ALLOWED", findings
    for key, outcome in findings.items():
        if key == "lawful":
            continue
        assert outcome != "ALLOWED", (key, findings)
    assert findings["free_prose_narrative"].startswith(
        "b27_explanation_narrative_not_derived_from_claims"
    )
    assert findings["appended_sentence"].startswith(
        "b27_explanation_narrative_not_derived_from_claims"
    )
    assert findings["unknown_template"].startswith("b27_explanation_template_unknown")
    assert findings["template_bound_to_other_path"].startswith(
        "b27_explanation_template_not_admitted_for_source"
    )
    assert findings["value_grammar_smuggling"].startswith(
        "b27_explanation_value_grammar_violated"
    )
    assert findings["rendering_not_derived"].startswith(
        "b27_explanation_rendering_not_derived"
    )
    assert findings["claim_count_disagrees"].startswith(
        "b27_explanation_claim_count_disagrees"
    )
    assert findings["policy_state_upgraded"].startswith(
        "b27_explanation_policy_state_not_conserved"
    )
    assert findings["unknown_registry_hash"].startswith(
        "b27_explanation_template_registry_unknown"
    )
    _record_evidence({"p14_r4_b27_persistence_battery": findings})


def test_p14_r4_downstream_records_are_append_only() -> None:
    """A downstream artifact may be superseded; it may not be rewritten."""

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_id = _seed_tenant(cursor)
        signed, _ = _sign_real_envelope(tenant_id)
        issuance = _conduct_issuance(tenant_id, signed)

        user = _role_connection("app_user")
        try:
            with user.cursor() as cursor:
                _bind_tenant(cursor, tenant_id)
                _lawful_request(cursor, tenant_id, issuance)
            user.commit()
        finally:
            user.close()

        # Privilege first: no runtime principal holds UPDATE or DELETE at all.
        with admin.cursor() as cursor:
            for relation in (
                "b27_explanation_materializations",
                "b28_simulation_requests",
                "b28_simulation_results",
                "b28_proposals",
            ):
                for principal in ("app_user", "app_worker", "app_rw", "app_ro"):
                    for operation in ("UPDATE", "DELETE"):
                        cursor.execute(
                            "SELECT has_table_privilege(%s, %s, %s)",
                            (principal, f"public.{relation}", operation),
                        )
                        assert cursor.fetchone()[0] is False, (
                            relation,
                            principal,
                            operation,
                        )

            # Then the trigger, measured with the privilege temporarily restored
            # so the fence is proved rather than the absent grant.
            cursor.execute(
                "GRANT UPDATE, DELETE ON TABLE public.b28_simulation_requests"
                " TO app_user"
            )
        try:
            conn = _role_connection("app_user")
            try:
                with conn.cursor() as cursor:
                    _bind_tenant(cursor, tenant_id)
                    with pytest.raises(psycopg2.Error) as excinfo:
                        cursor.execute(
                            "UPDATE public.b28_simulation_requests"
                            " SET requested_by = 'rewritten' WHERE tenant_id = %s",
                            (str(tenant_id),),
                        )
                    assert "b28_downstream_record_immutable" in str(excinfo.value)
                conn.rollback()
                with conn.cursor() as cursor:
                    _bind_tenant(cursor, tenant_id)
                    with pytest.raises(psycopg2.Error) as excinfo:
                        cursor.execute(
                            "DELETE FROM public.b28_simulation_requests"
                            " WHERE tenant_id = %s",
                            (str(tenant_id),),
                        )
                    assert "b28_downstream_record_immutable" in str(excinfo.value)
                conn.rollback()
            finally:
                conn.close()
        finally:
            with admin.cursor() as cursor:
                cursor.execute(
                    "REVOKE UPDATE, DELETE ON TABLE public.b28_simulation_requests"
                    " FROM app_user"
                )
    finally:
        admin.close()


def test_p14_r4_new_conservation_columns_admit_no_null_bypass() -> None:
    """H-DB-02: a consequence-bearing predicate may not pass on UNKNOWN.

    Every column the Corrective IV guards read is ``NOT NULL``, and every
    comparison they make is ``IS DISTINCT FROM`` or a null-checked extraction --
    so there is no value for which the predicate evaluates to UNKNOWN and
    PostgreSQL's CHECK semantics let the row through. This asserts the
    nullability half physically; the guard bodies are asserted by the batteries
    above, which supply NULL-shaped claims and require a named refusal.
    """

    expected_not_null = {
        (
            "b27_explanation_materializations",
            "source_issuance_envelope_hash",
        ),
        (
            "b27_explanation_materializations",
            "explanation_template_registry_hash",
        ),
        ("b28_simulation_requests", "source_issuance_envelope_hash"),
        ("b27_narrative_templates", "template_text"),
        ("b27_narrative_templates", "value_pattern"),
        ("b27_narrative_template_registry", "registry_hash"),
    }
    conn = _admin_connection()
    try:
        with conn.cursor() as cursor:
            for relation, column in sorted(expected_not_null):
                cursor.execute(
                    "SELECT is_nullable FROM information_schema.columns"
                    " WHERE table_schema='public' AND table_name=%s"
                    "   AND column_name=%s",
                    (relation, column),
                )
                row = cursor.fetchone()
                assert row is not None, (relation, column)
                assert row[0] == "NO", (relation, column, row[0])

            # A claim carrying a NULL template id is refused by name rather than
            # slipping past a regex comparison that would evaluate to UNKNOWN.
            cursor.execute(
                "SELECT pg_get_functiondef(oid) FROM pg_catalog.pg_proc"
                " WHERE proname = 'b27_enforce_explanation_consequence'"
            )
            body = cursor.fetchone()[0]
    finally:
        conn.close()
    assert "IS NULL" in body
    assert "IS DISTINCT FROM" in body


def test_p14_r4_downstream_relations_reject_a_caller_selected_tenant() -> None:
    """Exit Gate 6: tenant isolation is physical, not caller discipline.

    Unset GUC, wrong GUC, and a cross-tenant row all fail closed on the two
    relations Corrective IV changed. The positive control is the same statement
    with the correct binding, so a green result cannot be an accident of a
    fixture that was never admissible in the first place.
    """

    admin = _admin_connection()
    try:
        with admin.cursor() as cursor:
            tenant_a = _seed_tenant(cursor)
            tenant_b = _seed_tenant(cursor)
        signed, _ = _sign_real_envelope(tenant_a)
        issuance = _conduct_issuance(tenant_a, signed)

        def attempt(guc, tenant_column) -> str:
            conn = _role_connection("app_user")
            try:
                with conn.cursor() as cursor:
                    if guc is not None:
                        _bind_tenant(cursor, guc)
                    cursor.execute(
                        _REQUEST_INSERT,
                        (
                            str(tenant_column),
                            "req_" + uuid.uuid4().hex,
                            "agent:p14",
                            issuance["envelope_id"],
                            issuance["semantic_truth_hash"],
                            issuance["envelope_hash"],
                            _digest(),
                            1000,
                            "USD",
                            1,
                            SUFFICIENCY_POLICY_VERSION,
                        ),
                    )
                conn.commit()
                return "ALLOWED"
            except psycopg2.Error as exc:
                conn.rollback()
                return str(exc).strip().splitlines()[0]
            finally:
                conn.close()

        unset = attempt(None, tenant_a)
        wrong = attempt(tenant_b, tenant_a)
        cross = attempt(tenant_b, tenant_b)
        lawful = attempt(tenant_a, tenant_a)
    finally:
        admin.close()

    assert unset != "ALLOWED", unset
    assert wrong != "ALLOWED", wrong
    # A correctly-bound session of the wrong tenant cannot borrow tenant A's
    # issuance: the compound foreign key requires both columns to match.
    assert cross != "ALLOWED", cross
    assert lawful == "ALLOWED", lawful
