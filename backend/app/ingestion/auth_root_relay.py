"""B2.6-P2 Corrective XIV authentication-root relay transport.

Bounded internal HTTP boundary (same shape as the trust signer
gateway): the general API, acting as a non-authoritative byte relay,
POSTs verified arrivals (exact raw bytes + signature envelope +
tenant routing key + commerce handoff) to the dedicated
authentication trust root, which independently re-verifies the
provider signature before persisting any authority. Only this module
may open the relay transport; callers pass memory-only payloads
(raw bytes never persist).
"""

from __future__ import annotations

from typing import Any, Mapping


class AuthRootRelayError(RuntimeError):
    """The relay transport or the root refused the arrival (fail closed)."""


def relay_verified_ingress_to_auth_root(
    root_url: str,
    payload: Mapping[str, Any],
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """POST the relay envelope to the auth root; return its JSON body.

    Raises AuthRootRelayError when the root is unreachable or refuses
    (invalid signature, unknown tenant, schema violation). Callers
    must fail closed on this error, never fall back to manufacturing
    authority locally.
    """
    import httpx  # noqa: PLC0415  -- bounded transport lives here only.

    try:
        response = httpx.post(
            root_url.rstrip("/") + "/v1/authenticate-ingress",
            json=dict(payload),
            timeout=timeout_seconds,
        )
    except Exception as exc:
        raise AuthRootRelayError(
            f"b26_p2_ingress_relay_unreachable:{type(exc).__name__}"
        ) from exc
    if response.status_code != 200:
        raise AuthRootRelayError(
            "b26_p2_ingress_relay_refused:"
            f" status={response.status_code}"
            f" body={response.text[:200]}"
        )
    try:
        return dict(response.json())
    except Exception as exc:
        raise AuthRootRelayError("b26_p2_ingress_relay_bad_response") from exc
