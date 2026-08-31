"""B2.5-P13 Corrective XV falsifiers: issuance capability, audit truth, history.

Every test here exists because a falsifier succeeded against protected main at
``0941d3599680b6317638bad69a4b0c44d0e365fa``. The counters this module prints
are ``len()`` of lists appended by the code path that actually observed the
event, following the C5 convention: a printed literal proves someone typed a
number, a derived length proves the event happened.

Coverage:

* **H-XV-01** -- alternate acquisition of TrustEnvelope signing capability.
  Three constructions previously minted a capability over a caller-authored
  payload carrying fabricated money and obtained a publicly verifiable
  signature. All six vectors must now fail closed.
* **H-XV-02 / H-XV-03** -- durable audit history versus physical event history,
  under forced failure at each consequence boundary after P7 durability, plus
  retry lineage.
* **H-XV-10** -- historical TrustEnvelope serviceability across key rotation,
  through the real authenticated HTTP boundary, with public-only verification
  and no recomputation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.dsn import to_asyncpg_postgres_dsn
from app.trust import semantic_authority as _semantic_authority
from app.trust.builder import TrustEnvelopeBuildError, TrustEnvelopeBuildWitness
from app.trust.canonicalization import canonicalize_envelope_payload
from app.trust.issuance_authority_ledger import (
    TRUSTED_ISSUANCE_MODULES,
    IssuanceAuthorityLedgerError,
    mint_build_witness_authority,
    mint_issuance_capability,
)
from app.trust.issuance_session import trust_issuance_database_url
from app.trust.jwks import build_jwks_response
from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
from app.trust.machine_identity import AgentScope
from app.trust.semantic_authority import AuthorizedTrustEnvelope
from app.trust.signing import TrustEnvelopeSigningError, sign_trust_envelope

from test_b25_p13_e2e_trust_closure import (
    SIGNING_KID,
    _build_authenticated_app,
    _grant_scope,
    _insert_agent_client,
    _insert_tenant,
    _issue_credential,
    _seed_verdict,
    _worker_database_url,
)


ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 8, 29, 12, 0, 2, tzinfo=timezone.utc)
REVENUE_EXAMPLE = (
    ROOT
    / "contracts/trust-api/examples/revenue_claim_valid_with_verified_revenue_minor.json"
)

#: Observation ledgers. Each append is made by the code path that witnessed it.
CAPABILITY_BYPASS_REFUSALS: list[str] = []
ISSUANCE_TRUTH_OBSERVATIONS: list[str] = []
HISTORICAL_SERVICEABILITY_OBSERVATIONS: list[str] = []

_DB_PROOF = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_E2E_PROOF") != "1",
    reason="B2.5-P13 C15 durable-truth proofs require PostgreSQL and are opt-in",
)


# --------------------------------------------------------------------------
# H-XV-01: alternate capability acquisition
# --------------------------------------------------------------------------


class _CountingPrivateKey:
    """Counts private-key uses so a bypass cannot pass by never reaching crypto."""

    def __init__(self, seed: bytes) -> None:
        self.delegate = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(seed).digest()
        )
        self.sign_calls = 0

    def sign(self, material: bytes) -> bytes:
        self.sign_calls += 1
        return self.delegate.sign(material)

    def public_key(self):
        return self.delegate.public_key()


def _signing_registry(kid: str = "kid:b25-p13-c15", seed: bytes = b"c15") -> tuple:
    private = _CountingPrivateKey(seed)
    key = TrustSigningKey(
        kid=kid,
        algorithm="ed25519",
        public_key=private.public_key(),
        private_key=private,
        state="active",
        valid_from=NOW - timedelta(days=1),
        valid_until=NOW + timedelta(days=30),
        retired_at=None,
    )
    return TrustKeyRegistry((key,)), private


def _forged_claim(amount: int) -> dict:
    """A schema-valid TrustEnvelope carrying money no tenant ever earned."""

    payload = json.loads(REVENUE_EXAMPLE.read_text(encoding="utf-8"))
    payload["verified_revenue_minor"] = amount
    return payload


def _attempt(label: str, fn) -> None:
    """Run one bypass and require it to fail closed."""

    registry, private = _signing_registry()
    try:
        signed = fn(registry)
    except Exception as exc:  # noqa: BLE001 - any refusal is a pass
        CAPABILITY_BYPASS_REFUSALS.append(f"{label}:{type(exc).__name__}")
        assert private.sign_calls == 0, "refused, but the private key was still used"
        return
    pytest.fail(
        f"H-XV-01 FALSIFIED via {label}: signing capability was acquired outside "
        f"the authorised P5->P7 mint path and produced "
        f"verified_revenue_minor={signed.get('verified_revenue_minor')}"
    )


def test_c15_declared_trusted_computing_base_is_explicit() -> None:
    """The TCB is named in code, not implied by convention."""

    assert TRUSTED_ISSUANCE_MODULES == frozenset(
        {
            "app.trust.builder",
            "app.trust.semantic_authority",
        }
    )
    doc = ROOT / "docs/security/b25_p13_c15_trusted_computing_base.md"
    assert doc.exists(), "the TCB must be documented, not merely coded"
    text_body = doc.read_text(encoding="utf-8")
    for required in ("Trusted computing base", "Outside the threat model"):
        assert required in text_body, f"TCB document missing section: {required}"


def test_c15_direct_constructor_cannot_mint_capability() -> None:
    def attack(registry):
        payload = _forged_claim(999_999_999)
        capability = AuthorizedTrustEnvelope(
            authority_proof_hash=_semantic_authority._authority_proof_hash(
                canonicalize_envelope_payload(payload)
            ),
            authority_manifest_version=_semantic_authority.AUTHORITY_MANIFEST_VERSION,
            _authority_handle="attacker-authored-handle",
        )
        return sign_trust_envelope(capability, key_registry=registry)

    _attempt("direct_constructor", attack)


def test_c15_object_new_and_setattr_cannot_mint_capability() -> None:
    def attack(registry):
        payload = _forged_claim(888_888_888)
        capability = object.__new__(AuthorizedTrustEnvelope)
        object.__setattr__(
            capability,
            "authority_proof_hash",
            _semantic_authority._authority_proof_hash(
                canonicalize_envelope_payload(payload)
            ),
        )
        object.__setattr__(
            capability,
            "authority_manifest_version",
            _semantic_authority.AUTHORITY_MANIFEST_VERSION,
        )
        object.__setattr__(capability, "_authority_handle", "fabricated-handle")
        return sign_trust_envelope(capability, key_registry=registry)

    _attempt("object_new_setattr", attack)


def test_c15_ledger_mint_outside_the_tcb_is_refused() -> None:
    """The ledger is callable, but only from the declared trusted modules."""

    with pytest.raises(IssuanceAuthorityLedgerError, match="untrusted_caller"):
        mint_issuance_capability(b'{"x":1}')
    CAPABILITY_BYPASS_REFUSALS.append("capability_ledger_mint:untrusted_caller")

    with pytest.raises(IssuanceAuthorityLedgerError, match="untrusted_caller"):
        mint_build_witness_authority(b'{"x":1}')
    CAPABILITY_BYPASS_REFUSALS.append("witness_ledger_mint:untrusted_caller")


def test_c15_forged_build_witness_is_refused() -> None:
    """A P5 witness assembled without the builder resolves to nothing."""

    payload = _forged_claim(777_777_777)
    witness = object.__new__(TrustEnvelopeBuildWitness)
    for name, value in (
        ("tenant_id_hash", payload["tenant_id_hash"]),
        ("subject_type", payload["subject_type"]),
        ("subject_ref", payload["subject_ref"]),
        ("subject_ref_hash", payload["subject_ref_hash"]),
        ("source_snapshot_hash", "c" * 64),
        ("field_authority_names", tuple(payload)),
        ("_authority_handle", "fabricated-witness-handle"),
    ):
        object.__setattr__(witness, name, value)
    with pytest.raises(TrustEnvelopeBuildError, match="witness_invalid"):
        witness.assert_authoritative_payload(payload)
    CAPABILITY_BYPASS_REFUSALS.append("forged_build_witness:witness_invalid")


def test_c15_raw_caller_dictionary_still_cannot_sign() -> None:
    """XIV's refusal is preserved, not traded away."""

    registry, private = _signing_registry()
    with pytest.raises(TrustEnvelopeSigningError, match="issuance_capability_required"):
        sign_trust_envelope(_forged_claim(1), key_registry=registry)
    assert private.sign_calls == 0
    CAPABILITY_BYPASS_REFUSALS.append("raw_dictionary:issuance_capability_required")


def test_c15_capability_carries_no_payload_to_transplant() -> None:
    """There is nothing on the capability for an attacker to author."""

    assert "_payload_snapshot" not in AuthorizedTrustEnvelope.__slots__
    assert "_seal" not in AuthorizedTrustEnvelope.__slots__
    assert not hasattr(_semantic_authority, "_CAPABILITY_SEAL")
    CAPABILITY_BYPASS_REFUSALS.append("capability_shape:no_transplantable_payload")


def test_c15_capability_bypass_ledger_is_complete() -> None:
    """Pinned exactly: a vector that stops being exercised must turn this red."""

    print("\nc15_capability_bypass_refusals=" + str(len(CAPABILITY_BYPASS_REFUSALS)))
    print(
        "c15_capability_bypass_provenance="
        + json.dumps(sorted(CAPABILITY_BYPASS_REFUSALS))
    )
    assert len(CAPABILITY_BYPASS_REFUSALS) == 7, CAPABILITY_BYPASS_REFUSALS


# --------------------------------------------------------------------------
# H-XV-02 / H-XV-03: durable audit truth under forced failure and retry
# --------------------------------------------------------------------------


async def _query_envelope(app, *, tenant_id, token, subject_ref, idempotency_key):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.post(
            "/api/trust/v1/envelopes/query",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Tenant-ID": str(tenant_id),
                "X-Trust-Nonce": f"c15-nonce-{uuid4().hex}",
                "X-Correlation-ID": str(uuid4()),
                "X-Idempotency-Key": idempotency_key,
            },
            json={
                "subject_types": ["match_verdict"],
                "subject_refs": [subject_ref],
            },
        )


async def _issuance_rows(engine, tenant_id: UUID) -> list[dict]:
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT set_config('app.current_tenant_id', :t, true)"),
            {"t": str(tenant_id)},
        )
        rows = await connection.execute(
            text(
                """
                SELECT audit_ref, event_type, status, issuance_state,
                       envelope_hash, issued_signing_key_id,
                       issued_signature_hash, issued_signature, issued_at,
                       issuance_attempted_at, issuance_outcome_unknown_at,
                       replay_count
                FROM public.trust_access_log
                WHERE tenant_id = :t AND event_type = 'issuance'
                ORDER BY created_at
                """
            ),
            {"t": str(tenant_id)},
        )
        return [dict(row) for row in rows.mappings().all()]


async def _seed_tenant(engine, label: str):
    tenant_id, client_id = uuid4(), uuid4()
    async with engine.begin() as connection:
        await _insert_tenant(connection, tenant_id, label)
        await _insert_agent_client(connection, tenant_id, client_id)
        subject_urn = await _seed_verdict(
            connection, tenant_id=tenant_id, reference=f"c15-{uuid4().hex[:12]}"
        )
        token = await _issue_credential(
            connection, tenant_id=tenant_id, agent_client_id=client_id
        )
        for scope in (AgentScope.ENVELOPE_READ, AgentScope.ENVELOPE_VERIFY):
            await _grant_scope(
                connection,
                tenant_id=tenant_id,
                agent_client_id=client_id,
                scope=scope.value,
            )
    return tenant_id, token, subject_urn


def _configure_signing(monkeypatch, *, kid: str = SIGNING_KID, seed: bytes) -> None:
    seed_value = (
        base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
        .rstrip(b"=")
        .decode("ascii")
    )
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL", seed_value)
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_ID", kid)
    monkeypatch.setenv("SKELDIR_TRUST_SIGNING_KEY_VALID_FROM", "2026-01-01T00:00:00Z")


@_DB_PROOF
@pytest.mark.asyncio
async def test_c15_durable_history_never_overstates_physical_issuance(
    monkeypatch,
) -> None:
    """Force two pre-return failures after durable P7 authorization.

    These injection points replace the signer and therefore do not prove a
    post-signature boundary. Corrective XVI's dedicated suite separately wraps
    the genuine signer and fails only the completion write. Before Corrective XV
    every one of these left a row reading
    ``event_type='issuance', status='success'`` carrying an ``envelope_hash``,
    for a request whose signature never physically existed.
    """

    _configure_signing(monkeypatch, seed=b"b25-p13-e2e-signing-key")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c15-truth")
        app = _build_authenticated_app()

        # Control: an ordinary journey really does complete.
        control = await _query_envelope(
            app,
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=f"c15-ok-{uuid4().hex}",
        )
        assert control.status_code == 200, control.text
        signed_envelopes_delivered = len(control.json()["envelopes"])
        assert signed_envelopes_delivered == 1
        ISSUANCE_TRUTH_OBSERVATIONS.append("control:signed_and_delivered")

        from app.api import trust_api

        async def signer_request_failure(**_kwargs):
            raise RuntimeError("c15_injected_signer_request_failure")

        async def signer_response_loss(**_kwargs):
            raise ConnectionError("c15_injected_signer_response_loss")

        boundaries = {
            "during_signer_request": signer_request_failure,
            "during_signer_response": signer_response_loss,
        }
        for label, exploding in boundaries.items():
            monkeypatch.setattr(
                trust_api, "request_trust_envelope_signature", exploding
            )
            with pytest.raises(Exception):
                await _query_envelope(
                    app,
                    tenant_id=tenant_id,
                    token=token,
                    subject_ref=subject_urn,
                    idempotency_key=f"c15-fail-{label}-{uuid4().hex}",
                )
            ISSUANCE_TRUTH_OBSERVATIONS.append(f"failure_injected:{label}")
        monkeypatch.undo()
        _configure_signing(monkeypatch, seed=b"b25-p13-e2e-signing-key")

        rows = await _issuance_rows(engine, tenant_id)
        issued = [row for row in rows if row["issuance_state"] == "issued"]
        unknown = [
            row for row in rows if row["issuance_state"] == "signature_outcome_unknown"
        ]

        # THE GOVERNING INVARIANT: AUDIT HISTORY = PHYSICAL EVENT HISTORY.
        assert len(issued) == signed_envelopes_delivered, rows
        assert len(unknown) == len(boundaries), rows

        # A completed-issuance row must carry the cryptographic evidence of it.
        for row in issued:
            assert row["issued_signing_key_id"], row
            assert row["issued_signature_hash"], row
            assert len(row["issued_signature"]) == 64, row
            assert row["issued_at"] is not None, row
            ISSUANCE_TRUTH_OBSERVATIONS.append("issued_row_carries_signature_identity")

        # Entering the signer makes the exact outcome unknowable on exception.
        for row in unknown:
            assert row["issued_signing_key_id"] is None, row
            assert row["issued_signature_hash"] is None, row
            assert row["issued_signature"] is None, row
            assert row["issued_at"] is None, row
            assert row["issuance_attempted_at"] is not None, row
            assert row["issuance_outcome_unknown_at"] is not None, row
            ISSUANCE_TRUTH_OBSERVATIONS.append("unknown_row_is_explicit")

        print(
            "\nc15_issuance_truth_observations=" + str(len(ISSUANCE_TRUTH_OBSERVATIONS))
        )
        print(
            "c15_issuance_states="
            + json.dumps(
                {
                    "issued": len(issued),
                    "signature_outcome_unknown": len(unknown),
                },
                sort_keys=True,
            )
        )
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c15_database_physically_refuses_unbacked_completion_claim(
    monkeypatch,
) -> None:
    """The constraint is the law, not the application's good manners.

    A future code path that forgets to finalise cannot fabricate completed
    issuance, because PostgreSQL rejects an ``issued`` row without a key id and
    a signature hash.

    B2.5-P13 Corrective XVI narrowed *who* may attempt such a write at all, so
    this proof now has two halves: an ordinary runtime principal is refused
    before the constraint is ever consulted, and the constraint itself is still
    proven load-bearing by driving the same mutation under the one principal
    that does hold issuance authority.
    """

    _configure_signing(monkeypatch, seed=b"b25-p13-e2e-signing-key")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c15-constraint")
        app = _build_authenticated_app()
        response = await _query_envelope(
            app,
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=f"c15-constraint-{uuid4().hex}",
        )
        assert response.status_code == 200, response.text
        rows = await _issuance_rows(engine, tenant_id)
        audit_ref = rows[0]["audit_ref"]

        unbacked_completion = text(
            """
            UPDATE public.trust_access_log
            SET issuance_state = 'issued',
                issued_at = now(),
                issued_signing_key_id = NULL,
                issued_signature_hash = NULL
            WHERE tenant_id = :t AND audit_ref = :a
            """
        )

        with pytest.raises(Exception) as ordinary_error:
            async with engine.begin() as connection:
                await connection.execute(
                    text("SELECT set_config('app.current_tenant_id', :t, true)"),
                    {"t": str(tenant_id)},
                )
                await connection.execute(
                    unbacked_completion,
                    {"t": str(tenant_id), "a": audit_ref},
                )
        assert "trust_issuance_authority_violation" in str(ordinary_error.value)

        issuer_engine = create_async_engine(
            to_asyncpg_postgres_dsn(trust_issuance_database_url()), future=True
        )
        try:
            with pytest.raises(Exception) as authority_error:
                async with issuer_engine.begin() as connection:
                    await connection.execute(
                        text("SELECT set_config('app.current_tenant_id', :t, true)"),
                        {"t": str(tenant_id)},
                    )
                    # Reach the constraint by transitioning a row that is legally
                    # allowed to become issued, so the refusal below is the
                    # constraint's doing rather than the transition graph's.
                    await connection.execute(
                        text(
                            """
                            UPDATE public.trust_access_log
                            SET issuance_state = 'signing',
                                issuance_attempted_at = now(),
                                issuance_attempt_count = issuance_attempt_count + 1
                            WHERE tenant_id = :t AND audit_ref = :a
                              AND issuance_state <> 'issued'
                            """
                        ),
                        {"t": str(tenant_id), "a": audit_ref},
                    )
                    await connection.execute(
                        unbacked_completion,
                        {"t": str(tenant_id), "a": audit_ref},
                    )
            message = str(authority_error.value)
            assert (
                "ck_trust_access_log_issued_requires_crypto" in message
                or "trust_issuance_authority_violation:terminal" in message
            ), message
        finally:
            await issuer_engine.dispose()

        ISSUANCE_TRUTH_OBSERVATIONS.append("db_refuses_unbacked_completion")
        print("\nc15_db_completion_constraint_enforced=1")
        print("c15_ordinary_principal_completion_refused=1")
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c15_retry_after_indeterminate_yields_one_coherent_lineage(
    monkeypatch,
) -> None:
    """One logical issuance request keeps one explainable lineage."""

    _configure_signing(monkeypatch, seed=b"b25-p13-e2e-signing-key")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c15-retry")
        app = _build_authenticated_app()
        idempotency_key = f"c15-retry-{uuid4().hex}"

        from app.api import trust_api

        # A retry is only the *same logical request* if its audited material is
        # identical. `created_at` is part of that material, so the wall clock is
        # pinned here; otherwise two attempts a second apart are genuinely
        # different requests and the system correctly refuses to conflate them
        # under one idempotency key.
        pinned = datetime.now(timezone.utc).replace(microsecond=0)
        monkeypatch.setattr(trust_api, "_utc_now", lambda: pinned)

        original_signer = trust_api.request_trust_envelope_signature

        async def fail_signer_request(**_kwargs):
            raise RuntimeError("c15_retry_failure")

        monkeypatch.setattr(
            trust_api,
            "request_trust_envelope_signature",
            fail_signer_request,
        )
        with pytest.raises(Exception):
            await _query_envelope(
                app,
                tenant_id=tenant_id,
                token=token,
                subject_ref=subject_urn,
                idempotency_key=idempotency_key,
            )
        after_failure = await _issuance_rows(engine, tenant_id)
        assert [row["issuance_state"] for row in after_failure] == [
            "signature_outcome_unknown"
        ]

        # Same logical request, retried after the transient is gone.
        monkeypatch.setattr(
            trust_api, "request_trust_envelope_signature", original_signer
        )
        retry = await _query_envelope(
            app,
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=idempotency_key,
        )
        assert retry.status_code == 200, retry.text

        after_retry = await _issuance_rows(engine, tenant_id)
        # One logical request -> exactly one row, ending at the truth.
        assert len(after_retry) == 1, after_retry
        assert after_retry[0]["issuance_state"] == "issued", after_retry
        assert after_retry[0]["issued_signature_hash"], after_retry
        assert after_retry[0]["audit_ref"] == after_failure[0]["audit_ref"]
        ISSUANCE_TRUTH_OBSERVATIONS.append("retry:single_coherent_lineage")
        print("\nc15_retry_lineage_rows=" + str(len(after_retry)))
    finally:
        await engine.dispose()


# --------------------------------------------------------------------------
# H-XV-10: historical serviceability over the real HTTP product boundary
# --------------------------------------------------------------------------


@_DB_PROOF
@pytest.mark.asyncio
async def test_c15_historical_envelope_serviceable_over_http_after_key_rotation(
    monkeypatch,
) -> None:
    """The governed historical contract, exercised end to end over HTTP.

    Skeldir does not persist signed envelopes for later server-side retrieval;
    the envelope *is* the artifact and the holder keeps it. The governed
    historical path is therefore bearer-of-artifact verification through
    ``POST /trust/v1/verify`` against historical key authority published as
    public-only JWKS. That contract is exercised here in full: issue under key
    generation N, rotate to N+1, rebuild the application, and retrieve the
    original historical envelope's verification through the real route.
    """

    historical_seed = b"c15-historical-generation-n"
    historical_kid = "kid:b25-p13-c15-generation-n"
    _configure_signing(monkeypatch, kid=historical_kid, seed=historical_seed)

    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_a, token_a, subject_a = await _seed_tenant(engine, "c15-hist-a")
        tenant_b, token_b, _ = await _seed_tenant(engine, "c15-hist-b")

        app = _build_authenticated_app()
        issued = await _query_envelope(
            app,
            tenant_id=tenant_a,
            token=token_a,
            subject_ref=subject_a,
            idempotency_key=f"c15-hist-{uuid4().hex}",
        )
        assert issued.status_code == 200, issued.text
        historical_envelope = issued.json()["envelopes"][0]
        assert historical_envelope["signing_key_id"] == historical_kid
        historical_copy = deepcopy(historical_envelope)
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("issued_under_generation_n")

        # ---- Rotate signing authority to generation N+1 -------------------
        historical_private = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(historical_seed).digest()
        )
        # The rotation timeline must be coherent with the artifact: the key was
        # active when this envelope was created and retired afterwards. Retiring
        # it earlier is a temporal forgery, and the P8 corrective control
        # correctly rejects that -- which is why the boundary is set from the
        # envelope's own created_at rather than from a fixture constant.
        issued_at = datetime.fromisoformat(
            str(historical_envelope["created_at"]).replace("Z", "+00:00")
        )
        retired_key = TrustSigningKey(
            kid=historical_kid,
            algorithm="ed25519",
            public_key=historical_private.public_key(),
            private_key=None,
            state="verification_only",
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_until=issued_at + timedelta(days=365),
            retired_at=issued_at + timedelta(seconds=1),
        )
        public_jwks = build_jwks_response(TrustKeyRegistry((retired_key,)))
        # Public-only: the historical key is served with no private material.
        assert all("d" not in key for key in public_jwks["keys"])
        monkeypatch.setenv("SKELDIR_TRUST_PUBLIC_JWKS_JSON", json.dumps(public_jwks))
        _configure_signing(
            monkeypatch,
            kid="kid:b25-p13-c15-generation-n-plus-1",
            seed=b"c15-historical-generation-n-plus-1",
        )
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("rotated_to_generation_n_plus_1")

        # ---- Process restart: a brand-new application object --------------
        rotated_app = _build_authenticated_app()
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("application_rebuilt")

        async with AsyncClient(
            transport=ASGITransport(app=rotated_app), base_url="http://test"
        ) as client:
            # The currently active key really is the new generation.
            jwks_response = await client.get(
                "/api/trust/v1/keys/jwks",
                headers={"X-Correlation-ID": str(uuid4())},
            )
            assert jwks_response.status_code == 200, jwks_response.text
            published = {key["kid"] for key in jwks_response.json()["keys"]}
            assert historical_kid in published, published
            assert all("d" not in key for key in jwks_response.json()["keys"])
            HISTORICAL_SERVICEABILITY_OBSERVATIONS.append(
                "historical_kid_publicly_resolvable"
            )

            verified = await client.post(
                "/api/trust/v1/verify",
                headers={
                    "Authorization": f"Bearer {token_a}",
                    "X-Tenant-ID": str(tenant_a),
                    "X-Trust-Nonce": f"c15-hist-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                },
                json=historical_envelope,
            )
        assert verified.status_code == 200, verified.text
        body = verified.json()
        assert body["verification_status"] == "verified", body
        # Historical identity is served, not rewritten as current authority.
        assert body["signing_key_id"] == historical_kid, body
        assert body["semantic_truth_hash"] == historical_copy["semantic_truth_hash"]
        assert body["signature_hash"] == historical_copy["signature_hash"]
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("historical_semantics_preserved")

        # The artifact was not silently replaced by a fresh signature.
        assert historical_envelope == historical_copy
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("no_substitute_reissue")

        # No financial or Bayesian recomputation happened on the retrieval path.
        rows_before = await _issuance_rows(engine, tenant_a)
        assert len(rows_before) == 1, rows_before
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("no_recompute_on_retrieval")

        # Tenant containment: B cannot present A's envelope as its own.
        async with AsyncClient(
            transport=ASGITransport(app=rotated_app), base_url="http://test"
        ) as client:
            crossed = await client.post(
                "/api/trust/v1/verify",
                headers={
                    "Authorization": f"Bearer {token_b}",
                    "X-Tenant-ID": str(tenant_a),
                    "X-Trust-Nonce": f"c15-hist-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                },
                json=historical_envelope,
            )
        assert crossed.status_code in {401, 403}, crossed.text
        HISTORICAL_SERVICEABILITY_OBSERVATIONS.append("cross_tenant_refused")

        print(
            "\nc15_historical_serviceability_observations="
            + str(len(HISTORICAL_SERVICEABILITY_OBSERVATIONS))
        )
        print(
            "c15_historical_provenance="
            + json.dumps(HISTORICAL_SERVICEABILITY_OBSERVATIONS)
        )
        assert len(HISTORICAL_SERVICEABILITY_OBSERVATIONS) == 8
    finally:
        await engine.dispose()


@_DB_PROOF
@pytest.mark.asyncio
async def test_c15_tampered_historical_envelope_fails_public_verification(
    monkeypatch,
) -> None:
    """The historical path verifies truth, not merely well-formedness."""

    _configure_signing(monkeypatch, seed=b"b25-p13-e2e-signing-key")
    engine = create_async_engine(
        to_asyncpg_postgres_dsn(_worker_database_url()), future=True
    )
    try:
        tenant_id, token, subject_urn = await _seed_tenant(engine, "c15-hist-tamper")
        app = _build_authenticated_app()
        issued = await _query_envelope(
            app,
            tenant_id=tenant_id,
            token=token,
            subject_ref=subject_urn,
            idempotency_key=f"c15-tamper-{uuid4().hex}",
        )
        assert issued.status_code == 200, issued.text
        envelope = issued.json()["envelopes"][0]
        envelope["verified_revenue_minor"] = 999_999_999

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/trust/v1/verify",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-ID": str(tenant_id),
                    "X-Trust-Nonce": f"c15-tamper-{uuid4().hex}",
                    "X-Correlation-ID": str(uuid4()),
                },
                json=envelope,
            )
        assert response.status_code in {200, 422}, response.text
        if response.status_code == 200:
            assert response.json()["verification_status"] == "rejected", response.text
        print("\nc15_historical_tamper_rejected=1")
    finally:
        await engine.dispose()
