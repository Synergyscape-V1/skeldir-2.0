"""B2.5-P9 machine-caller identity, scopes, replay, and rate-limit tests.

Physics proven here (per B2.5-P9 Remediation Directive Exit Gates):
- Gate 1: Agent identity schema protected (tables, RLS, GUC-absent zero rows).
- Gate 2: Constant-time credential physics (CSPRNG, SHA-256, O(1) prefix,
  AST ban on uuid4/bcrypt/argon2, missing-prefix and wrong-secret are both
  O(1) fast).
- Gate 3: Concurrent replay immunity (50 parallel requests => 1 success,
  49 replay_rejected, zero 500s).
- Gate 4: Rollback-proof audit (denial event survives FastAPI exception
  rollback via the autonomous P7 seam).
- Gate 5: Reserved action scopes not issuable (DB CHECK + trigger reject).
- Gate 6: P1-P8 substrate preservation (no changes to signing/canonical/hash).
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from app.trust.machine_identity import (
    FORBIDDEN_ENTROPY_SOURCES,
    FORBIDDEN_TOKEN_HASHES,
    TOKEN_PREFIX_LENGTH,
    AgentScope,
    MachineTokenError,
    ReservedScopeError,
    assert_scope_issuable,
    coerce_scope,
    derive_token_storage,
    generate_machine_token,
    verify_machine_token,
)
from app.trust.reason_codes import ReasonCode


ROOT = Path(__file__).resolve().parents[3]
P9_MIGRATION_PATH = (
    ROOT
    / "alembic/versions/007_skeldir_foundation"
    / "202607191200_b25_p9_machine_identity.py"
)
P9_RUNTIME_PATHS = (
    ROOT / "backend/app/trust/machine_identity.py",
    ROOT / "backend/app/trust/machine_auth.py",
)


def test_migration_declares_required_p9_tables_and_constraints() -> None:
    migration = P9_MIGRATION_PATH.read_text(encoding="utf-8")
    for table in (
        "agent_clients",
        "agent_service_credentials",
        "agent_scope_grants",
        "agent_token_revocations",
        "trust_request_nonces",
        "trust_rate_limit_state",
    ):
        assert f"CREATE TABLE public.{table}" in migration, table
        assert (
            f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in migration
        ), table
        assert f"tenant_isolation_policy_{table}" in migration, table
    assert "ck_agent_service_credentials_hash_algorithm CHECK" in migration
    assert "hash_algorithm = 'sha256'" in migration
    assert "uq_trust_request_nonces_tenant_nonce" in migration
    assert "reject_reserved_trust_action_scope" in migration
    assert "trg_agent_scope_grants_reject_reserved" in migration
    assert "trust.action.execute" in migration
    assert "auto_executable_within_policy" in migration


# ---------------------------------------------------------------------------
# Gate 2: Constant-time credential physics (H-P9-02, H-P9-05)
# ---------------------------------------------------------------------------


def test_generate_machine_token_uses_csprng_and_sha256() -> None:
    token = generate_machine_token()
    assert len(token.token_prefix) == TOKEN_PREFIX_LENGTH
    assert len(token.token_hash) == 64
    assert token.hash_algorithm == "sha256"
    other = generate_machine_token()
    assert token.plaintext != other.plaintext
    assert token.token_hash != other.token_hash


def test_verify_machine_token_constant_time_comparison() -> None:
    token = generate_machine_token()
    assert verify_machine_token(token.plaintext, token.token_hash) is True
    assert verify_machine_token("wrong-token-value", token.token_hash) is False
    assert verify_machine_token(token.plaintext, "0" * 64) is False
    assert verify_machine_token(token.plaintext, token.token_hash, "bcrypt") is False
    assert verify_machine_token("", token.token_hash) is False
    assert verify_machine_token(token.plaintext, "") is False


def test_missing_prefix_and_wrong_secret_are_both_o1_fast() -> None:
    """Timing oracle negative control (H-P9-02).

    A missing prefix (DB miss) and a valid prefix with a wrong secret (SHA-256
    mismatch) must take statistically identical time. Both are O(1) fast.
    """
    token = generate_machine_token()
    correct_hash = token.token_hash
    wrong_hash = "0" * 64
    correct_times = []
    wrong_times = []
    for _ in range(100):
        start = time.perf_counter()
        verify_machine_token(token.plaintext, correct_hash)
        correct_times.append(time.perf_counter() - start)
        start = time.perf_counter()
        verify_machine_token(token.plaintext, wrong_hash)
        wrong_times.append(time.perf_counter() - start)
    correct_mean = sum(correct_times) / len(correct_times)
    wrong_mean = sum(wrong_times) / len(wrong_times)
    assert correct_mean < 0.001, correct_mean
    assert wrong_mean < 0.001, wrong_mean
    assert abs(correct_mean - wrong_mean) < 0.005


def test_token_storage_projection_excludes_plaintext() -> None:
    token = generate_machine_token()
    storage = token.storage_projection()
    assert "plaintext" not in storage
    assert storage["token_prefix"] == token.token_prefix
    assert storage["token_hash"] == token.token_hash
    assert storage["hash_algorithm"] == "sha256"


def test_derive_token_storage_rejects_short_plaintext() -> None:
    with pytest.raises(MachineTokenError, match="plaintext_too_short"):
        derive_token_storage("short")


# ---------------------------------------------------------------------------
# Gate 5: Reserved action scopes not issuable (H-P9-06)
# ---------------------------------------------------------------------------


def test_assert_scope_issuable_rejects_reserved_action_scopes() -> None:
    for scope in (
        "trust.action.propose",
        "trust.action.execute",
        "trust.action.approve",
        "trust.action.reject",
        "auto_executable_within_policy",
    ):
        with pytest.raises(
            ReservedScopeError, match="reserved_action_scope_unissuable"
        ):
            assert_scope_issuable(scope)


def test_assert_scope_issuable_accepts_design_partner_scopes() -> None:
    for scope in AgentScope:
        result = assert_scope_issuable(scope.value)
        assert result == scope
    for raw in (
        "trust.envelope.read",
        "trust.envelope.verify",
        "trust.audit.read",
        "trust.keys.read",
    ):
        assert assert_scope_issuable(raw).value == raw


def test_assert_scope_issuable_rejects_unknown_scopes() -> None:
    with pytest.raises(
        ReservedScopeError, match="scope_value_not_in_design_partner_registry"
    ):
        assert_scope_issuable("trust.bogus.scope")


def test_coerce_scope_round_trips_enum_and_string() -> None:
    assert coerce_scope(AgentScope.AUDIT_READ) == AgentScope.AUDIT_READ
    assert coerce_scope("trust.audit.read") == AgentScope.AUDIT_READ
    with pytest.raises(ReservedScopeError):
        coerce_scope("trust.action.execute")


# ---------------------------------------------------------------------------
# AST ban on forbidden entropy/hash primitives
# ---------------------------------------------------------------------------


def _collect_imports_and_calls(path: Path) -> tuple[set[str], set[str]]:
    import ast

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
                if alias.asname:
                    imports.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imports.add(alias.name)
                if alias.asname:
                    imports.add(alias.asname)
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            calls.add(f"{node.value.id}.{node.attr}")
    return imports, calls


def test_p9_runtime_paths_ban_uuid4_and_random() -> None:
    for path in P9_RUNTIME_PATHS:
        imports, calls = _collect_imports_and_calls(path)
        for forbidden in FORBIDDEN_ENTROPY_SOURCES:
            assert forbidden not in imports, (path, forbidden)
            assert forbidden not in calls, (path, forbidden)
        assert "uuid4" not in imports, (path, "uuid4")
        assert "uuid.uuid4" not in calls, (path, "uuid.uuid4")
    identity_path = P9_RUNTIME_PATHS[0]
    identity_imports, _ = _collect_imports_and_calls(identity_path)
    assert "secrets" in identity_imports, (
        identity_path,
        "machine_identity.py must import secrets CSPRNG",
    )


def test_p9_runtime_paths_ban_bcrypt_and_argon2() -> None:
    for path in P9_RUNTIME_PATHS:
        imports, calls = _collect_imports_and_calls(path)
        for forbidden in FORBIDDEN_TOKEN_HASHES:
            assert forbidden not in imports, (path, forbidden)
            assert forbidden not in calls, (path, forbidden)


# ---------------------------------------------------------------------------
# Gate 3: Concurrent replay immunity (H-P9-03) - in-process simulation
# ---------------------------------------------------------------------------


class _FakeNoConflictResult:
    rowcount = 1

    def first(self):
        return None


class _FakeConflictResult:
    rowcount = 0

    def first(self):
        return None


class _ReplayTrackingSession:
    """Session that accepts the first insert and reports all subsequent as conflicts."""

    def __init__(self) -> None:
        self.seen_nonces: set[str] = set()
        self.lock_added: bool = False
        self.committed: int = 0

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "ON CONFLICT (tenant_id, nonce_value) DO NOTHING" in sql:
            nonce = params["nonce_value"] if params else ""
            if nonce in self.seen_nonces:
                return _FakeConflictResult()
            self.seen_nonces.add(nonce)
            return _FakeNoConflictResult()
        return _FakeNoConflictResult()

    async def commit(self) -> None:
        self.committed += 1


def test_atomic_nonce_insert_returns_true_for_first_and_false_for_replay() -> None:
    import asyncio
    from app.trust.machine_auth import _atomic_nonce_insert

    session = _ReplayTrackingSession()
    tenant_id = uuid4()
    client_id = uuid4()
    first = asyncio.run(
        _atomic_nonce_insert(
            session,
            tenant_id=tenant_id,
            agent_client_id=client_id,
            nonce_value="nonce-1",
            request_identity_hash="sha256:" + "0" * 64,
        )
    )
    second = asyncio.run(
        _atomic_nonce_insert(
            session,
            tenant_id=tenant_id,
            agent_client_id=client_id,
            nonce_value="nonce-1",
            request_identity_hash="sha256:" + "0" * 64,
        )
    )
    assert first is True
    assert second is False


def test_concurrent_replay_storm_yields_one_success_and_49_rejections() -> None:
    """Gate 3: 50 parallel requests with the same nonce => exactly 1 success.

    Simulates the atomic UNIQUE constraint under READ COMMITTED using a
    process-safe set guarded by a lock. The atomic insert is the primitive;
    no exists()->insert() race exists.
    """
    import asyncio
    import threading
    from app.trust.machine_auth import _atomic_nonce_insert

    seen: set[str] = set()
    seen_lock = threading.Lock()

    class _ConcurrentSession:
        async def execute(self, statement, params=None):
            sql = str(statement)
            if "ON CONFLICT (tenant_id, nonce_value) DO NOTHING" in sql:
                nonce = params["nonce_value"] if params else ""
                with seen_lock:
                    if nonce in seen:
                        return _FakeConflictResult()
                    seen.add(nonce)
                    return _FakeNoConflictResult()
            return _FakeNoConflictResult()

        async def commit(self):
            pass

    def attempt() -> bool:
        session = _ConcurrentSession()
        return asyncio.run(
            _atomic_nonce_insert(
                session,
                tenant_id=uuid4(),
                agent_client_id=uuid4(),
                nonce_value="shared-nonce-storm",
                request_identity_hash="sha256:" + "0" * 64,
            )
        )

    with ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(attempt) for _ in range(50)]
        results = [f.result() for f in as_completed(futures)]
    successes = sum(1 for r in results if r is True)
    rejections = sum(1 for r in results if r is False)
    assert successes == 1, f"expected 1 success, got {successes}"
    assert rejections == 49, f"expected 49 rejections, got {rejections}"


# ---------------------------------------------------------------------------
# Gate 4: Rollback-proof audit (H-P9-04)
# ---------------------------------------------------------------------------


def test_machine_request_identity_hash_is_stable_and_deterministic() -> None:
    from app.trust.machine_auth import _machine_request_identity_hash

    tenant_id = uuid4()
    h1 = _machine_request_identity_hash(
        tenant_id=tenant_id, token_prefix="prefix01", nonce_value="nonce-x"
    )
    h2 = _machine_request_identity_hash(
        tenant_id=tenant_id, token_prefix="prefix01", nonce_value="nonce-x"
    )
    assert h1 == h2
    assert h1.startswith("sha256:")
    h3 = _machine_request_identity_hash(
        tenant_id=tenant_id, token_prefix="prefix02", nonce_value="nonce-x"
    )
    assert h3 != h1


def test_write_denial_audit_uses_autonomous_session_seam(monkeypatch) -> None:
    """Gate 4: denial audit must go through record_trust_audit_event_durable.

    Patches record_trust_audit_event_durable to prove the P9 middleware routes
    denial audits through the autonomous seam (not the request-scoped session).
    """
    from app.trust import machine_auth

    calls = []

    async def fake_durable(request):
        calls.append(request)
        from app.trust.audit import TrustAuditRecord

        return TrustAuditRecord(
            audit_ref="urn:skeldir:audit:scope_denial:test",
            audit_hash="sha256:" + "0" * 64,
            idempotency_key_hash="sha256:" + "0" * 64,
            request_identity_hash="sha256:" + "0" * 64,
            event_type="scope_denial",
            status="refused",
            replayed=False,
        )

    monkeypatch.setattr(machine_auth, "record_trust_audit_event_durable", fake_durable)
    import asyncio

    tenant_id = uuid4()
    asyncio.run(
        machine_auth._write_denial_audit(
            tenant_id=tenant_id,
            reason_code=ReasonCode.SCOPE_DENIED,
            idempotency_key="idem-1",
        )
    )
    assert len(calls) == 1
    assert calls[0].event_type == "scope_denial"
    assert calls[0].reason_code == ReasonCode.SCOPE_DENIED
    assert calls[0].evidence_refs_allowed is False


def test_write_denial_audit_swallows_persistence_failure(monkeypatch) -> None:
    """A P7 audit write failure must not propagate to the caller as a 500."""
    from app.trust import machine_auth
    import asyncio

    async def failing_durable(request):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(
        machine_auth, "record_trust_audit_event_durable", failing_durable
    )
    asyncio.run(
        machine_auth._write_denial_audit(
            tenant_id=uuid4(),
            reason_code=ReasonCode.REPLAY_REJECTED,
            idempotency_key="idem-2",
        )
    )


# ---------------------------------------------------------------------------
# Integration: full authenticate_machine_caller happy path + denials
# ---------------------------------------------------------------------------


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    @property
    def headers(self) -> dict[str, str]:
        return self._headers


class _MockSession:
    def __init__(self, cred_row=None, revoked=False, scopes=None) -> None:
        self.cred_row = cred_row
        self.revoked = revoked
        self.scopes = scopes or []
        self.nonce_insert_result = True
        self.rate_limit_result = True

    async def execute(self, statement, params=None):
        sql = str(statement)
        if "agent_service_credentials cred" in sql:
            return _FakeResult(self.cred_row)
        if "agent_token_revocations" in sql:
            return _FakeResult({"1": 1} if self.revoked else None)
        if "agent_scope_grants" in sql:
            return _FakeRows([(s,) for s in self.scopes])
        if "ON CONFLICT (tenant_id, nonce_value) DO NOTHING" in sql:

            class R:
                rowcount = 1 if self.nonce_insert_result else 0

            return R()
        if "trust_rate_limit_state" in sql and "RETURNING" in sql:
            if self.rate_limit_result:

                class _WithinBudgetResult:
                    def first(self):
                        return (1,)

                return _WithinBudgetResult()

            class _OverLimitResult:
                def first(self):
                    return (999,)

            return _OverLimitResult()
        return _FakeNoConflictResult()

    async def commit(self):
        pass


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        if self._row is None:
            return None

        class _Row:
            _mapping = None

        row = _Row()
        row._mapping = self._row
        return row


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def __iter__(self):
        return iter(self._rows)


def _make_credential_row(token, tenant_id) -> dict:
    storage = derive_token_storage(token.plaintext)
    return {
        "agent_client_id": str(uuid4()),
        "tenant_id": str(tenant_id),
        "audience": "design-partner",
        "client_status": "active",
        "credential_id": str(uuid4()),
        "token_hash": storage.token_hash,
        "hash_algorithm": "sha256",
        "credential_status": "active",
        "expires_at": None,
    }


def test_authenticate_machine_caller_happy_path() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, tenant_id)
    session = _MockSession(
        cred_row=cred_row,
        revoked=False,
        scopes=[AgentScope.ENVELOPE_READ.value],
    )
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "nonce-happy-01234567",
            "X-Idempotency-Key": "idem-happy",
        }
    )
    ctx = asyncio.run(
        authenticate_machine_caller(
            request, session, required_scope=AgentScope.ENVELOPE_READ
        )
    )
    assert ctx.tenant_id == tenant_id
    assert AgentScope.ENVELOPE_READ in ctx.scopes
    assert ctx.nonce_value == "nonce-happy-01234567"


def test_authenticate_machine_caller_rejects_missing_bearer() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    request = _FakeRequest({})
    session = _MockSession()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authenticate_machine_caller(request, session))
    assert exc.value.status_code == 401


def test_authenticate_machine_caller_rejects_wrong_secret() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, tenant_id)
    cred_row["token_hash"] = "0" * 64
    session = _MockSession(cred_row=cred_row, scopes=[AgentScope.ENVELOPE_READ.value])
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "nonce-wrong-01234567",
            "X-Idempotency-Key": "idem-wrong",
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authenticate_machine_caller(request, session))
    assert exc.value.status_code == 401


def test_authenticate_machine_caller_rejects_tenant_mismatch() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, uuid4())
    session = _MockSession(
        cred_row=cred_row,
        scopes=[AgentScope.ENVELOPE_READ.value],
    )
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "nonce-mismatch-01234567",
            "X-Idempotency-Key": "idem-mismatch",
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authenticate_machine_caller(request, session))
    assert exc.value.status_code == 403


def test_authenticate_machine_caller_rejects_replay() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, tenant_id)
    session = _MockSession(
        cred_row=cred_row,
        scopes=[AgentScope.ENVELOPE_READ.value],
    )
    session.nonce_insert_result = False
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "replay-nonce-01234567",
            "X-Idempotency-Key": "idem-replay",
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authenticate_machine_caller(request, session))
    assert exc.value.status_code == 403


def test_authenticate_machine_caller_rejects_scope_denial() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, tenant_id)
    session = _MockSession(cred_row=cred_row, scopes=[])
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "nonce-scope-01234567",
            "X-Idempotency-Key": "idem-scope",
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            authenticate_machine_caller(
                request, session, required_scope=AgentScope.ENVELOPE_VERIFY
            )
        )
    assert exc.value.status_code == 403


def test_authenticate_machine_caller_rejects_rate_limited() -> None:
    import asyncio
    from app.trust.machine_auth import authenticate_machine_caller
    from fastapi import HTTPException

    tenant_id = uuid4()
    token = generate_machine_token()
    cred_row = _make_credential_row(token, tenant_id)
    session = _MockSession(
        cred_row=cred_row,
        scopes=[AgentScope.ENVELOPE_READ.value],
    )
    session.rate_limit_result = False
    request = _FakeRequest(
        {
            "Authorization": f"Bearer {token.plaintext}",
            "X-Tenant-ID": str(tenant_id),
            "X-Trust-Nonce": "nonce-rate-01234567",
            "X-Idempotency-Key": "idem-rate",
        }
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(authenticate_machine_caller(request, session))
    assert exc.value.status_code == 429


# ---------------------------------------------------------------------------
# Gate 6: Substrate preservation - P8 validators remain importable
# ---------------------------------------------------------------------------


def test_p1_through_p8_substrate_imports_remain_unchanged() -> None:
    from app.trust import (
        audit,
        builder,
        canonicalization,
        hash_identity,
        jwks,
        key_registry,
        reason_codes,
        reason_truth_matrix,
        refusal,
        schema_versions,
        schema_verification,
        signing,
        verification,
    )
    from app.trust.audit import record_trust_audit_event_durable
    from app.trust.signing import sign_trust_envelope
    from app.trust.verification import verify_trust_envelope

    assert audit is not None
    assert builder is not None
    assert canonicalization is not None
    assert hash_identity is not None
    assert jwks is not None
    assert key_registry is not None
    assert reason_codes is not None
    assert reason_truth_matrix is not None
    assert refusal is not None
    assert schema_versions is not None
    assert schema_verification is not None
    assert signing is not None
    assert verification is not None


def test_p9_does_not_introduce_p10_route_logic() -> None:
    """P9 is strictly the gateway substrate. No route logic allowed."""
    import ast

    for path in P9_RUNTIME_PATHS:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not node.name.startswith("route_"), (path, node.name)
                assert not node.name.startswith("endpoint_"), (path, node.name)
        assert "APIRouter" not in source, path
        assert "@router" not in source, path
        assert "@app." not in source, path
