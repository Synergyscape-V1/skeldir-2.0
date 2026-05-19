"""Local signed webhook replay controls for M4 diagnostics."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlsplit

import httpx

from common import connect, emit, read_fixture_state, set_tenant

UNSAFE_REPLAY_TARGET_MESSAGE = (
    "production payload replay is forbidden in M4; --api-base-url/OPS_API_BASE_URL "
    "must resolve to a local or Docker-network HTTP target before any request is sent"
)
ALLOWED_LOCAL_REPLAY_HOSTS = frozenset({"api", "localhost", "127.0.0.1", "::1"})


def validate_local_api_base_url(api_base_url: str) -> str:
    parsed = urlsplit(api_base_url)
    host = parsed.hostname or ""
    if parsed.scheme != "http":
        raise SystemExit(f"{UNSAFE_REPLAY_TARGET_MESSAGE}: rejected scheme {parsed.scheme!r}")
    if host.lower() not in ALLOWED_LOCAL_REPLAY_HOSTS:
        raise SystemExit(f"{UNSAFE_REPLAY_TARGET_MESSAGE}: rejected host {host!r}")
    if not parsed.port:
        raise SystemExit(f"{UNSAFE_REPLAY_TARGET_MESSAGE}: explicit local port is required")
    return api_base_url.rstrip("/")


def _stripe_signature(raw_body: bytes, secret: str, *, tampered: bool = False) -> str:
    timestamp = str(int(time.time()))
    signed_payload = f"{timestamp}.{raw_body.decode('utf-8')}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if tampered:
        digest = "0" + digest[1:]
    return f"t={timestamp},v1={digest}"


def _payload(
    state: dict,
    *,
    duplicate: bool = False,
    replay_variant: str = "primary",
) -> tuple[bytes, str]:
    idempotency_key = state["webhook_idempotency_key"]
    pi_id = state["stripe_payment_intent_id"]
    event_id = state["stripe_event_id"]
    if replay_variant == "tampered-negative-control":
        # Keep the signature negative control independent from the successful
        # replay so idempotency cannot mask a failed signature check.
        idempotency_key = f"{idempotency_key}:tampered"
        pi_id = f"{pi_id}-tampered"
        event_id = f"{event_id}-tampered"
    if not duplicate:
        # The fresh replay and duplicate replay intentionally use the same
        # key within one run. Freshness is provided by the run-scoped seed.
        pass
    body = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "created": int(time.time()),
        "data": {
            "object": {
                "id": pi_id,
                "amount": 12500,
                "currency": "usd",
                "metadata": {
                    "order_id": pi_id,
                    "utm_source": "direct",
                    "vendor": "stripe",
                },
            }
        },
    }
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"), idempotency_key


def _post(api_base_url: str, state: dict, *, tampered: bool = False, duplicate: bool = False) -> dict:
    replay_variant = "tampered-negative-control" if tampered else "primary"
    raw_body, idempotency_key = _payload(
        state,
        duplicate=duplicate,
        replay_variant=replay_variant,
    )
    headers = {
        "content-type": "application/json",
        "X-Skeldir-Tenant-Key": state["api_key"],
        "X-Idempotency-Key": idempotency_key,
        "Stripe-Signature": _stripe_signature(
            raw_body,
            state["stripe_webhook_secret"],
            tampered=tampered,
        ),
    }
    with httpx.Client(timeout=20) as client:
        response = client.post(
            f"{api_base_url.rstrip('/')}/api/webhooks/stripe/payment_intent/succeeded",
            content=raw_body,
            headers=headers,
        )
    try:
        body = response.json()
    except ValueError:
        body = {"raw": response.text[:500]}
    return {"status_code": response.status_code, "body": body}


def _event_count(state: dict) -> int:
    with connect() as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            set_tenant(cur, state["tenant_id"])
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM public.attribution_events
                WHERE tenant_id = %s
                  AND idempotency_key = %s
                """,
                (state["tenant_id"], state["webhook_idempotency_key"]),
            )
            return int(cur.fetchone()["count"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["valid", "tampered", "duplicate", "all"], default="all")
    parser.add_argument("--api-base-url", default=os.getenv("OPS_API_BASE_URL", "http://api:8000"))
    args = parser.parse_args()

    api_base_url = validate_local_api_base_url(args.api_base_url)
    state = read_fixture_state()
    result: dict[str, object] = {
        "command_class": "local_fixture_replay",
        "signature_sensitive": True,
        "idempotency_sensitive": True,
        "api_base_url": api_base_url,
        "replay_target_guard": "local_http_only",
    }
    if args.mode in {"valid", "all"}:
        result["valid_signature"] = _post(api_base_url, state)
    if args.mode in {"tampered", "all"}:
        result["tampered_signature"] = _post(api_base_url, state, tampered=True)
    if args.mode in {"duplicate", "all"}:
        before = _event_count(state)
        first = _post(api_base_url, state)
        after_first = _event_count(state)
        second = _post(api_base_url, state, duplicate=True)
        after_second = _event_count(state)
        result["duplicate_idempotency"] = {
            "before_count": before,
            "first_response": first,
            "after_first_count": after_first,
            "second_response": second,
            "after_second_count": after_second,
            "duplicate_detected": after_first == after_second and after_second >= 1,
        }
    emit(result)

    if "tampered_signature" in result and result["tampered_signature"]["status_code"] != 401:  # type: ignore[index]
        raise SystemExit(1)
    if "duplicate_idempotency" in result and not result["duplicate_idempotency"]["duplicate_detected"]:  # type: ignore[index]
        raise SystemExit(1)


if __name__ == "__main__":
    main()
