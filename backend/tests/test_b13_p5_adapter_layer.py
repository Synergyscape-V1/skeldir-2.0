from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from app.services.oauth_lifecycle_dispatcher import ProviderOAuthLifecycleDispatcher
from app.services.provider_oauth_lifecycle import (
    OAuthAccountMetadataRequest,
    OAuthAuthorizeURLRequest,
    OAuthCallbackStateValidationRequest,
    OAuthCodeExchangeRequest,
    OAuthDisconnectRequest,
    OAuthLifecycleNotImplementedError,
    OAuthTokenRefreshRequest,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_SCRIPT = REPO_ROOT / "scripts" / "ci" / "enforce_b13_p5_adapter_layer.py"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def test_b13_p5_gate_passes_repo_state() -> None:
    result = _run([sys.executable, str(GATE_SCRIPT)])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p5_negative_control_detects_missing_required_context(tmp_path: Path) -> None:
    checks_contract = REPO_ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
    payload = json.loads(checks_contract.read_text(encoding="utf-8"))
    payload["required_contexts"] = [
        value
        for value in payload.get("required_contexts", [])
        if value != "B1.3 P5 Adapter Layer Proofs"
    ]
    mutated = tmp_path / "required_checks.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--required-checks-contract",
            str(mutated),
        ]
    )
    assert result.returncode != 0
    assert "missing context" in f"{result.stdout}\n{result.stderr}"


def test_b13_p5_negative_control_detects_missing_adapter_method(tmp_path: Path) -> None:
    adapter_file = REPO_ROOT / "backend/app/services/provider_oauth_lifecycle.py"
    mutated = adapter_file.read_text(encoding="utf-8").replace(
        "async def refresh_token(",
        "async def refresh_token_disabled(",
        1,
    )
    mutated_path = tmp_path / "provider_oauth_lifecycle.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--adapter-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "method set mismatch" in f"{result.stdout}\n{result.stderr}"


def test_b13_p5_negative_control_detects_missing_deterministic_adapter_registration(tmp_path: Path) -> None:
    adapter_file = REPO_ROOT / "backend/app/services/provider_oauth_lifecycle.py"
    mutated = adapter_file.read_text(encoding="utf-8").replace(
        "DeterministicOAuthLifecycleAdapter(),",
        "StripeOAuthLifecycleAdapter(),",
        1,
    )
    mutated_path = tmp_path / "provider_oauth_lifecycle.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--adapter-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "missing DeterministicOAuthLifecycleAdapter registration" in f"{result.stdout}\n{result.stderr}"


def test_b13_p5_negative_control_detects_capability_overclaim(tmp_path: Path) -> None:
    p5_contract = REPO_ROOT / "contracts-internal/governance/b13_p5_oauth_adapter_capabilities.main.json"
    payload = json.loads(p5_contract.read_text(encoding="utf-8"))
    payload["adapter_capabilities"].append(
        {
            "provider": "paypal",
            "mode": "runtime_backed",
            "adapter_kind": "runtime_scaffold",
            "supports_authorize_url": True,
            "supports_callback_state_validation": True,
            "supports_code_exchange": True,
            "supports_token_refresh": True,
            "supports_revoke_disconnect": True,
            "supports_account_metadata": True,
        }
    )
    mutated = tmp_path / "p5_contract.json"
    mutated.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--p5-capability-contract",
            str(mutated),
        ]
    )
    assert result.returncode != 0
    assert "must match P0 runtime-backed + internal providers" in f"{result.stdout}\n{result.stderr}"


def test_b13_p5_negative_control_detects_route_local_provider_branching(tmp_path: Path) -> None:
    platforms_file = REPO_ROOT / "backend/app/api/platforms.py"
    injected = (
        platforms_file.read_text(encoding="utf-8")
        + "\n"
        + "def _regression_branch(platform: str) -> str:\n"
        + "    if platform == \"stripe\":\n"
        + "        return \"bad\"\n"
        + "    return \"ok\"\n"
    )
    mutated = tmp_path / "platforms.py"
    mutated.write_text(injected, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--api-files",
            str(mutated),
        ]
    )
    assert result.returncode != 0
    assert "provider-specific platform branch in API file" in f"{result.stdout}\n{result.stderr}"


def test_b13_p5_negative_control_detects_outbound_http_import_in_adapter(tmp_path: Path) -> None:
    adapter_file = REPO_ROOT / "backend/app/services/provider_oauth_lifecycle.py"
    mutated = "import httpx\n" + adapter_file.read_text(encoding="utf-8")
    mutated_path = tmp_path / "provider_oauth_lifecycle.py"
    mutated_path.write_text(mutated, encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(GATE_SCRIPT),
            "--adapter-file",
            str(mutated_path),
        ]
    )
    assert result.returncode != 0
    assert "outbound HTTP firewall violated" in f"{result.stdout}\n{result.stderr}"


@pytest.mark.asyncio
async def test_b13_p5_dispatcher_executes_full_deterministic_lifecycle() -> None:
    dispatcher = ProviderOAuthLifecycleDispatcher()

    authorize = await dispatcher.build_authorize_url(
        platform="dummy",
        request=OAuthAuthorizeURLRequest(
            tenant_id=uuid4(),
            user_id=uuid4(),
            correlation_id=uuid4(),
            redirect_uri="https://app.example/callback",
            state_nonce="state-abc",
            code_challenge="challenge-xyz",
            code_challenge_method="S256",
        ),
    )
    assert authorize.authorization_url.startswith("https://deterministic.provider.local/oauth/authorize?")
    assert authorize.provider_session_metadata["provider"] == "dummy"

    state_result = await dispatcher.validate_callback_state(
        platform="dummy",
        request=OAuthCallbackStateValidationRequest(
            expected_state_nonce="state-abc",
            received_state_nonce="state-abc",
        ),
    )
    assert state_result.is_valid is True

    exchanged = await dispatcher.exchange_auth_code(
        platform="dummy",
        request=OAuthCodeExchangeRequest(
            tenant_id=uuid4(),
            user_id=uuid4(),
            correlation_id=uuid4(),
            authorization_code="code-123",
            redirect_uri="https://app.example/callback",
            code_verifier="verifier-123",
        ),
    )
    assert exchanged.access_token.startswith("det-access-")
    assert exchanged.refresh_token is not None
    assert exchanged.provider_account_id.startswith("det-acct-")

    refreshed = await dispatcher.refresh_token(
        platform="dummy",
        request=OAuthTokenRefreshRequest(
            tenant_id=uuid4(),
            correlation_id=uuid4(),
            refresh_token=exchanged.refresh_token or "det-refresh-fallback",
            scope=exchanged.scope,
        ),
    )
    assert refreshed.access_token.startswith("det-refresh-access-")
    assert refreshed.provider_account_id.startswith("det-acct-")

    metadata = await dispatcher.fetch_account_metadata(
        platform="dummy",
        request=OAuthAccountMetadataRequest(
            tenant_id=uuid4(),
            correlation_id=uuid4(),
            provider_account_id=refreshed.provider_account_id,
            access_token=refreshed.access_token,
        ),
    )
    assert metadata.provider_account_id.startswith("det-acct-")
    assert metadata.account_metadata["environment"] == "deterministic"

    revoked = await dispatcher.revoke_disconnect(
        platform="dummy",
        request=OAuthDisconnectRequest(
            tenant_id=uuid4(),
            correlation_id=uuid4(),
            provider_account_id=metadata.provider_account_id,
            access_token=refreshed.access_token,
            refresh_token=refreshed.refresh_token,
            reason="user_disconnect",
        ),
    )
    assert revoked.revoked is True


@pytest.mark.asyncio
async def test_b13_p5_dispatcher_rejects_unknown_provider() -> None:
    dispatcher = ProviderOAuthLifecycleDispatcher()
    with pytest.raises(KeyError):
        await dispatcher.build_authorize_url(
            platform="not_registered",
            request=OAuthAuthorizeURLRequest(
                tenant_id=uuid4(),
                user_id=uuid4(),
                correlation_id=uuid4(),
                redirect_uri="https://app.example/callback",
                state_nonce="state",
            ),
        )


@pytest.mark.asyncio
async def test_b13_p5_stripe_adapter_is_scaffold_only_in_p5() -> None:
    dispatcher = ProviderOAuthLifecycleDispatcher()
    with pytest.raises(OAuthLifecycleNotImplementedError):
        await dispatcher.build_authorize_url(
            platform="stripe",
            request=OAuthAuthorizeURLRequest(
                tenant_id=uuid4(),
                user_id=uuid4(),
                correlation_id=uuid4(),
                redirect_uri="https://app.example/callback",
                state_nonce="state",
            ),
        )
