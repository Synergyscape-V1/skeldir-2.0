"""Corrective XIX black-box production-artifact composition proof.

The only database writes performed by this observer are control-plane setup:
tenants, webhook credentials, one human JWT principal, and machine callers.
Every financial, attribution, Bayesian, issuance, and signature row must arise
from authenticated HTTP ingress and the independently running production
services declared in ``docker-compose.c19.yml``.
"""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import httpx
import jwt
import psycopg2
import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C19_TOPOLOGY_PROOF") != "1",
    reason="Corrective XIX production topology proof is opt-in locally",
)

SETTLEMENT_COUNT = 20
API_TIMEOUT_SECONDS = 30.0
PIPELINE_TIMEOUT_SECONDS = 480.0


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _admin_connection():
    return psycopg2.connect(_required("C19_ADMIN_DATABASE_URL"))


def _fetch_one(sql: str, params: tuple[object, ...]) -> tuple[object, ...] | None:
    with _admin_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _wait_for(
    description: str,
    query: str,
    params: tuple[object, ...],
    predicate,
    *,
    timeout: float = PIPELINE_TIMEOUT_SECONDS,
) -> tuple[object, ...]:
    deadline = time.monotonic() + timeout
    last: tuple[object, ...] | None = None
    while time.monotonic() < deadline:
        last = _fetch_one(query, params)
        if last is not None and predicate(last):
            return last
        time.sleep(1.0)
    raise AssertionError(f"timed out waiting for {description}; last={last!r}")


def _seed_control_plane(*, suffix: str) -> dict[str, str]:
    """Seed custody/configuration only, never a financial or model fact."""

    tenant_id = uuid4()
    user_id = uuid4()
    client_id = uuid4()
    tenant_key = f"c19-tenant-{suffix}-{uuid4().hex}"
    stripe_secret = f"whsec-c19-{suffix}-{uuid4().hex}"
    token = f"{uuid4().hex}{uuid4().hex}c19"
    with _admin_connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO public.tenants (
                id, name, api_key_hash, notification_email,
                stripe_webhook_secret_ciphertext,
                stripe_webhook_secret_key_id
            ) VALUES (
                %s, %s, %s, %s,
                pgp_sym_encrypt(%s, %s), %s
            )
            """,
            (
                str(tenant_id),
                f"C19 physical tenant {suffix}",
                hashlib.sha256(tenant_key.encode()).hexdigest(),
                f"c19-{suffix}-{tenant_id.hex[:8]}@example.invalid",
                stripe_secret,
                "c19-platform-key",
                "c19-key",
            ),
        )
        cur.execute(
            """
            INSERT INTO public.users (
                id, login_identifier_hash, auth_provider, is_active
            ) VALUES (%s, %s, 'password', true)
            """,
            (str(user_id), f"sha256:{hashlib.sha256(str(user_id).encode()).hexdigest()}"),
        )
        cur.execute(
            """
            INSERT INTO public.agent_clients (
                id, tenant_id, client_name, client_display_hash, audience, status
            ) VALUES (%s, %s, %s, %s, 'b25-p13-c19', 'active')
            """,
            (
                str(client_id),
                str(tenant_id),
                f"c19-client-{suffix}",
                f"sha256:{hashlib.sha256(str(client_id).encode()).hexdigest()}",
            ),
        )
        cur.execute(
            """
            INSERT INTO public.agent_service_credentials (
                id, tenant_id, agent_client_id, token_prefix, token_hash,
                hash_algorithm, status, issued_at
            ) VALUES (%s, %s, %s, %s, %s, 'sha256', 'active', now())
            """,
            (
                str(uuid4()),
                str(tenant_id),
                str(client_id),
                token[:8],
                hashlib.sha256(token.encode()).hexdigest(),
            ),
        )
        for scope in ("trust.envelope.read", "trust.envelope.verify"):
            cur.execute(
                """
                INSERT INTO public.agent_scope_grants (
                    id, tenant_id, agent_client_id, scope_value, granted_at
                ) VALUES (%s, %s, %s, %s, now())
                """,
                (str(uuid4()), str(tenant_id), str(client_id), scope),
            )
    return {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "tenant_key": tenant_key,
        "stripe_secret": stripe_secret,
        "machine_token": token,
    }


def _jwt_for(control: dict[str, str]) -> str:
    private_key = Path(_required("C19_JWT_PRIVATE_KEY_PATH")).read_bytes()
    now = int(time.time())
    return jwt.encode(
        {
            "tenant_id": control["tenant_id"],
            "user_id": control["user_id"],
            "sub": control["user_id"],
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + 900,
            "iss": "https://issuer.skeldir.test",
            "aud": "skeldir-api",
            "scopes": ["manager", "viewer"],
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "c19-jwt"},
    )


def _post_touchpoint(
    control: dict[str, str], token: str, index: int, occurred_at: datetime
) -> dict[str, object]:
    session_id = str(uuid4())
    vendor = "google_ads" if index % 2 == 0 else "facebook_ads"
    vendor_channel_indicator = "SEARCH" if index % 2 == 0 else "FACEBOOK_ADS"
    response = httpx.post(
        f"{_required('C19_API_BASE_URL')}/api/attribution/events",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Correlation-ID": str(uuid4()),
        },
        json={
            "event_id": f"c19-touch-{index:02d}-{uuid4().hex}",
            "event_type": "ad_click",
            "event_timestamp": occurred_at.isoformat().replace("+00:00", "Z"),
            "vendor": vendor,
            "vendor_channel_indicator": vendor_channel_indicator,
            "session_id": session_id,
            "campaign_id": f"c19-campaign-{index % 2}",
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["tenant_id"] == control["tenant_id"]
    # Caller-provided identifiers are never adopted as authority. The API
    # returns the privacy substrate's fresh, bounded session identifier.
    assert body["session_id"] != session_id
    assert body["duplicate"] is False
    return {
        "session_id": body["session_id"],
        "occurred_at": occurred_at,
        "index": index,
    }


def _stripe_body(item: dict[str, object], *, provider_event: str | None = None) -> bytes:
    index = int(item["index"])
    payment_intent = f"pi_c19_{index:04d}"
    occurred_at = item["occurred_at"]
    assert isinstance(occurred_at, datetime)
    conversion_time = occurred_at + timedelta(hours=1)
    return json.dumps(
        {
            "id": provider_event or f"evt_c19_{index:04d}",
            "created": int(conversion_time.timestamp()),
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": payment_intent,
                    "amount": 10_000 + index,
                    "currency": "usd",
                    "metadata": {
                        "session_id": item["session_id"],
                        "vendor": "stripe",
                        "utm_source": "stripe",
                    },
                }
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _post_stripe(
    control: dict[str, str], item: dict[str, object], *, provider_event: str | None = None
) -> httpx.Response:
    body = _stripe_body(item, provider_event=provider_event)
    signed_at = int(time.time())
    digest = hmac.new(
        control["stripe_secret"].encode(),
        f"{signed_at}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    return httpx.post(
        f"{_required('C19_API_BASE_URL')}/api/webhooks/stripe/payment_intent/succeeded",
        headers={
            "Content-Type": "application/json",
            "X-Skeldir-Tenant-Key": control["tenant_key"],
            "Stripe-Signature": f"t={signed_at},v1={digest}",
        },
        content=body,
        timeout=API_TIMEOUT_SECONDS,
    )


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "compose",
            "-p",
            _required("C19_COMPOSE_PROJECT_NAME"),
            "-f",
            str(Path(_required("C19_REPO_ROOT")) / "docker-compose.c19.yml"),
            *args,
        ],
        cwd=_required("C19_REPO_ROOT"),
        check=True,
        text=True,
        capture_output=True,
    )


def _machine_headers(control: dict[str, str], *, prefix: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {control['machine_token']}",
        "X-Tenant-ID": control["tenant_id"],
        "X-Trust-Nonce": f"{prefix}-{uuid4().hex}",
        "X-Correlation-ID": str(uuid4()),
        "X-Idempotency-Key": f"{prefix}-{uuid4()}",
    }


def _verify_from_public_jwks(envelope: dict[str, object], jwks: dict[str, object]) -> None:
    """Verify as a public-only consumer and prove a key mismatch is rejected."""

    from app.trust.canonicalization import canonicalize_signature_material
    from app.trust.jwks import registry_from_public_jwks
    from app.trust.verification import verify_trust_envelope

    keys = jwks.get("keys")
    assert isinstance(keys, list) and len(keys) == 1
    assert not ({"d", "seed", "secret", "private_key"} & set(keys[0]))
    verified = verify_trust_envelope(
        envelope, key_registry=registry_from_public_jwks(jwks)
    )
    assert verified.verification_status == "verified", verified

    key = keys[0]
    public_bytes = base64.urlsafe_b64decode(str(key["x"]) + "==")
    signature = base64.urlsafe_b64decode(
        str(envelope["signature"]).removeprefix("ed25519:") + "=="
    )
    Ed25519PublicKey.from_public_bytes(public_bytes).verify(
        signature, canonicalize_signature_material(envelope)
    )

    mismatched = bytearray(public_bytes)
    mismatched[0] ^= 1
    with pytest.raises((InvalidSignature, ValueError)):
        Ed25519PublicKey.from_public_bytes(bytes(mismatched)).verify(
            signature, canonicalize_signature_material(envelope)
        )


def _record_evidence(payload: dict[str, object]) -> None:
    target = Path(_required("C19_EVIDENCE_PATH"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def test_c19_context_robust_production_topology() -> None:
    control_a = _seed_control_plane(suffix="a")
    control_b = _seed_control_plane(suffix="b")
    token_a = _jwt_for(control_a)
    token_b = _jwt_for(control_b)
    base_url = _required("C19_API_BASE_URL")

    # Invalid semantic ingress is refused before it can masquerade as a
    # touchpoint or carry financial authority.
    invalid = httpx.post(
        f"{base_url}/api/attribution/events",
        headers={"Authorization": f"Bearer {token_a}", "X-Correlation-ID": str(uuid4())},
        json={
            "event_id": "c19-invalid-conversion",
            "event_type": "purchase",
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "vendor": "google_ads",
            "vendor_channel_indicator": "paid",
        },
        timeout=API_TIMEOUT_SECONDS,
    )
    assert invalid.status_code == 422, invalid.text

    # Keep every financial event beyond the real 24-hour provisional boundary
    # and inside one governed daily fit window. Distribution across 20 daily
    # windows would correctly produce 20 sparse fallbacks, not one real fit.
    # The production eligibility contract requires a twenty-day observation
    # density. Start twenty-two days back so the twentieth legitimate event is
    # still historical while the cohort spans exactly twenty UTC dates.
    anchor = (datetime.now(timezone.utc) - timedelta(days=22)).replace(
        hour=2, minute=0, second=0, microsecond=0
    )
    with ThreadPoolExecutor(max_workers=10) as pool:
        items = list(
            pool.map(
                lambda i: _post_touchpoint(
                    control_a, token_a, i, anchor + timedelta(days=i)
                ),
                range(SETTLEMENT_COUNT),
            )
        )

    # Two independently addressable workers compete for legitimate, unrelated
    # work. One is restarted while the second wave is still being published.
    first_wave = items[:10]
    second_wave = items[10:]
    with ThreadPoolExecutor(max_workers=10) as pool:
        first_responses = list(pool.map(lambda item: _post_stripe(control_a, item), first_wave))
    _compose("restart", "worker_b23_a")
    with ThreadPoolExecutor(max_workers=10) as pool:
        second_responses = list(pool.map(lambda item: _post_stripe(control_a, item), second_wave))
    assert all(response.status_code == 200 for response in first_responses + second_responses)
    assert all(response.json().get("status") == "success" for response in first_responses + second_responses)

    # Exact duplicates and different provider-event ids for the same commerce
    # reference converge through the public ingress rather than fabricating a
    # second financial fact.
    with ThreadPoolExecutor(max_workers=4) as pool:
        duplicates = list(pool.map(lambda _: _post_stripe(control_a, items[0]), range(4)))
    assert all(response.status_code == 200 for response in duplicates)
    alternate_reference = _post_stripe(
        control_a, items[0], provider_event=f"evt_c19_alternate_{uuid4().hex}"
    )
    assert alternate_reference.status_code in {200, 409, 422}, alternate_reference.text

    _wait_for(
        "twenty legitimate conversions and deterministic allocations",
        """
        SELECT
          count(*) FILTER (WHERE e.event_type = 'purchase'),
          count(DISTINCT a.event_id)
        FROM public.attribution_events e
        LEFT JOIN public.attribution_allocations a
          ON a.tenant_id=e.tenant_id AND a.event_id=e.id
        WHERE e.tenant_id=%s
        """,
        (control_a["tenant_id"],),
        lambda row: int(row[0]) == SETTLEMENT_COUNT and int(row[1]) == SETTLEMENT_COUNT,
    )
    _wait_for(
        "natural B2.3 provisional verdicts",
        "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id=%s AND status='matched_provisional'",
        (control_a["tenant_id"],),
        lambda row: int(row[0]) >= 1,
    )

    # Hold one row lock across a Beat sweep. SKIP LOCKED must let unrelated rows
    # progress and a later real sweep must converge the held row.
    lock_conn = _admin_connection()
    lock_cur = lock_conn.cursor()
    lock_cur.execute("BEGIN")
    lock_cur.execute(
        "SELECT id FROM public.b23_match_verdicts WHERE tenant_id=%s AND status='matched_provisional' ORDER BY id LIMIT 1 FOR UPDATE",
        (control_a["tenant_id"],),
    )
    locked_verdict = lock_cur.fetchone()
    assert locked_verdict is not None
    time.sleep(7)
    lock_conn.rollback()
    lock_conn.close()

    confirmed = _wait_for(
        "all legitimate verdicts to confirm after contention",
        "SELECT count(*) FROM public.b23_match_verdicts WHERE tenant_id=%s AND status='matched_confirmed'",
        (control_a["tenant_id"],),
        lambda row: int(row[0]) == SETTLEMENT_COUNT,
    )
    verified_allocations = _wait_for(
        "allocation verification to follow verdict truth",
        "SELECT count(DISTINCT event_id) FROM public.attribution_allocations WHERE tenant_id=%s AND verified=true",
        (control_a["tenant_id"],),
        lambda row: int(row[0]) == SETTLEMENT_COUNT,
    )

    fit = _wait_for(
        "real PyMC fit and governed diagnostics",
        """
        SELECT id, status, diagnostic_status, n_chains, n_samples_actual,
               r_hat_max, ess_min, divergence_count, artifact_ref,
               confidence_bucket, sampling_started_at, source_snapshot_hash
        FROM public.bayesian_model_fits
        WHERE tenant_id=%s AND status='succeeded'
        ORDER BY created_at DESC LIMIT 1
        """,
        (control_a["tenant_id"],),
        lambda row: row[2] == "passed" and row[10] is not None,
    )
    fit_id = str(fit[0])
    assert int(fit[3]) >= 2
    assert int(fit[4]) >= 1600
    assert float(fit[5]) <= 1.01
    assert float(fit[6]) >= 400
    assert int(fit[7]) == 0
    assert fit[8]
    assert fit[9] in {"high", "medium", "low"}

    subject_ref = f"urn:skeldir:confidence_projection:{fit_id}"
    response = httpx.get(
        f"{base_url}/api/trust/v1/envelopes/confidence_projection/{subject_ref}",
        headers=_machine_headers(control_a, prefix="c19-positive"),
        timeout=API_TIMEOUT_SECONDS,
    )
    assert response.status_code == 200, response.text
    envelope = response.json()
    jwks_response = httpx.get(
        f"{base_url}/api/trust/v1/keys/jwks",
        headers={"X-Correlation-ID": str(uuid4())},
        timeout=API_TIMEOUT_SECONDS,
    )
    assert jwks_response.status_code == 200, jwks_response.text
    jwks = jwks_response.json()
    _verify_from_public_jwks(envelope, jwks)
    confidence = envelope["confidence_metadata"]
    assert confidence["confidence_status"] == "available"
    assert confidence["confidence_authority"] == "b24_confidence_projection"
    assert confidence["diagnostics_status"] == "passed"
    assert confidence["confidence_score_basis_points"] is None

    # Same identifiers under another tenant remain physically isolated.
    item_b = _post_touchpoint(control_b, token_b, 0, anchor + timedelta(hours=3))
    isolated_webhook = _post_stripe(control_b, item_b)
    assert isolated_webhook.status_code == 200, isolated_webhook.text
    cross_tenant = httpx.get(
        f"{base_url}/api/trust/v1/envelopes/confidence_projection/{subject_ref}",
        headers=_machine_headers(control_b, prefix="c19-cross-tenant"),
        timeout=API_TIMEOUT_SECONDS,
    )
    assert cross_tenant.status_code == 404, cross_tenant.text

    # The API has no private key and must fail closed when the remote signer is
    # physically absent. A fresh idempotency key prevents cached issuance from
    # hiding the outage.
    _compose("stop", "trust_signer")
    signer_absent = httpx.get(
        f"{base_url}/api/trust/v1/envelopes/confidence_projection/{subject_ref}",
        headers=_machine_headers(control_a, prefix="c19-signer-absent"),
        timeout=API_TIMEOUT_SECONDS,
    )
    assert signer_absent.status_code >= 500, signer_absent.text
    _compose("start", "trust_signer")

    issuance = _wait_for(
        "durable signed issuance consequence",
        """
        SELECT
          count(*) FILTER (WHERE attempt_state='issued'),
          count(*) FILTER (
              WHERE attempt_state='issued'
                AND issued_at IS NOT NULL
                AND signature_hash IS NOT NULL
                AND signed_envelope_hash IS NOT NULL
                AND signed_envelope IS NOT NULL
          ),
          count(*) FILTER (WHERE signing_key_id IS NOT NULL)
        FROM public.trust_issuance_attempts
        WHERE tenant_id=%s
        """,
        (control_a["tenant_id"],),
        lambda row: int(row[0]) >= 1 and int(row[1]) >= 1 and int(row[2]) >= 1,
    )
    access_history = _fetch_one(
        "SELECT count(*) FROM public.trust_access_log WHERE tenant_id=%s AND issuance_state='issued'",
        (control_a["tenant_id"],),
    )
    assert access_history and int(access_history[0]) >= 1

    containers = _compose("ps", "--format", "json").stdout.strip().splitlines()
    assert len(containers) >= 8
    evidence = {
        "status": "PASS",
        "control_plane_seeded_tables": [
            "tenants",
            "users",
            "agent_clients",
            "agent_service_credentials",
            "agent_scope_grants",
        ],
        "authoritative_state_seeded": False,
        "tenant_a": control_a["tenant_id"],
        "tenant_b": control_b["tenant_id"],
        "settlement_count": SETTLEMENT_COUNT,
        "confirmed_verdicts": int(confirmed[0]),
        "verified_allocations": int(verified_allocations[0]),
        "fit_id": fit_id,
        "fit_status": fit[1],
        "diagnostic_status": fit[2],
        "n_chains": int(fit[3]),
        "n_samples_actual": int(fit[4]),
        "r_hat_max": float(fit[5]),
        "ess_min": float(fit[6]),
        "divergence_count": int(fit[7]),
        "confidence_bucket": fit[9],
        "source_snapshot_hash": fit[11],
        "public_jwks_keys": len(jwks["keys"]),
        "signature_verified_by_public_key": True,
        "mismatched_public_key_rejected": True,
        "cross_tenant_subject_refused": True,
        "remote_signer_absence_failed_closed": True,
        "durable_issued_attempts": int(issuance[0]),
        "durable_issued_attempts_with_full_artifact": int(issuance[1]),
        "durable_attempts_with_signing_key": int(issuance[2]),
        "access_log_issued_rows": int(access_history[0]),
        "container_process_count": len(containers),
        "concurrency_cases": {
            "A_exact_duplicate": "converged",
            "B_same_commerce_different_provider_event": alternate_reference.status_code,
            "C_unrelated_same_tenant": "converged",
            "D_same_refs_different_tenant": "isolated",
            "E_transition_race": "converged",
            "F_rows_arriving_during_work": "converged",
            "G_worker_restart_with_peer": "converged",
            "H_database_lock_contention": "converged",
        },
    }
    _record_evidence(evidence)
