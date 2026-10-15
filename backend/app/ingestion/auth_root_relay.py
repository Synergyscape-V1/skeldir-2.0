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


#: Process-wide persistent relay clients, one per running event loop.
#: Corrective XXI (F2): constructing httpx.AsyncClient per mint rebuilt
#: the SSL context every request (~340 ms on Windows cert-store load;
#: pure waste for a plaintext loopback call, and per-request connection
#: setup under burst). The client is transport plumbing only: same
#: timeout, same endpoint, same fail-closed errors. Clients are keyed by
#: event loop so multi-loop hosts (tests, reloads) never share a client
#: across loops. Entries are process-lifetime (one per loop); servers
#: run a single loop per worker.
_RELAY_CLIENTS: dict[int, Any] = {}


def _relay_client(timeout_seconds: float) -> Any:
    """Return the shared relay client for the running event loop."""
    import asyncio  # noqa: PLC0415
    import httpx  # noqa: PLC0415  -- bounded transport lives here only.

    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    client = _RELAY_CLIENTS.get(loop_id)
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_seconds)
        _RELAY_CLIENTS[loop_id] = client
    return client


def _drop_relay_client() -> None:
    """Forget the cached relay client for the running event loop.

    Used when the transport itself fails (stale pooled connection after
    a root restart/deploy): the next call builds a fresh client. Only
    transport errors refresh the pool; root refusals (status != 200)
    never retry and fail closed below.
    """
    import asyncio  # noqa: PLC0415

    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    _RELAY_CLIENTS.pop(loop_id, None)


async def relay_verified_ingress_to_auth_root(
    root_url: str,
    payload: Mapping[str, Any],
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    """POST the relay envelope to the auth root; return its JSON body.

    Async: the single-worker API event loop must never block on the
    relay round-trip, or sustained webhook load serializes behind it.
    Raises AuthRootRelayError when the root is unreachable or refuses
    (invalid signature, unknown tenant, schema violation). Callers
    must fail closed on this error, never fall back to manufacturing
    authority locally.

    Transport resilience: exactly one retry on CONNECT failure (stale
    pooled connection after a root restart/deploy, refused listener),
    with the cached client dropped first so the retry redials. A failed
    connect can never have reached the root, so no mint can execute
    twice because of it. Timeouts and root refusals never retry and
    fail closed: a timed-out call may already have minted (idempotent
    by event_id, but the caller decides, never this transport).
    """
    import httpx  # noqa: PLC0415  -- bounded transport lives here only.

    url = root_url.rstrip("/") + "/v1/authenticate-ingress"
    body = dict(payload)
    try:
        response = await _relay_client(timeout_seconds).post(url, json=body)
    except httpx.ConnectError:
        _drop_relay_client()
        try:
            response = await _relay_client(timeout_seconds).post(url, json=body)
        except Exception as exc:
            raise AuthRootRelayError(
                f"b26_p2_ingress_relay_unreachable:{type(exc).__name__}"
            ) from exc
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
