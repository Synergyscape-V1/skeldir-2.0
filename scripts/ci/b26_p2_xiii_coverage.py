#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII effect-coverage registry (extends XII).

XII_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XIII changes the reachable universe itself:

- the predecessor event P is authored ONLY by the dedicated
  authentication trust root: ``b26_p2_record_provider_auth_consequence``
  is EXECUTable by app_ingress (and migration admins) alone; app_user
  holds zero EXECUTE and zero INSERT/UPDATE (XIII-A battery);
- consequence rows are immutable and provider-bound (no digest rewrite,
  no cross-provider substitution);
- the atomic transition ``b26_p2_authenticate_ingress_atomic`` is
  EXECUTable by app_ingress alone (single-txn consequence + witness +
  evidence + terminal provenance);
- the witness remains bound to P (ingress-only mint refused without P);
  ``governed_attestation`` at runtime is migration/admin custody only;
- one serviceable regime: the XIII migration refuses without the
  ingress principal; INSERT-time provenance never lands
  authenticated_known (pending_authentication); dispatch requires the
  terminal state plus witness; late provisioning converges
  deterministically (contract B).

The governing topology proof loads XIII_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_xii_coverage import XII_COVERED_SURFACES as _XII  # noqa: PLC0415
except ImportError:
    from b26_p2_xii_coverage import XII_COVERED_SURFACES as _XII  # noqa: PLC0415

_XIII_NEW = frozenset(
    {
        # Predecessor event P (Corrective XIII, Class A): authored ONLY
        # by the dedicated authentication trust root.
        "app_ingress:EXECUTE:b26_p2_record_provider_auth_consequence",
        # Atomic transition (Corrective XIII, Class C): single-txn
        # consequence + witness + evidence + terminal provenance.
        "app_ingress:EXECUTE:b26_p2_authenticate_ingress_atomic",
        # Topology adjudication (Corrective XIII, Class C).
        "app_user:EXECUTE:b26_p2_xiii_topology_check",
        "app_worker:EXECUTE:b26_p2_xiii_topology_check",
        "app_relay:EXECUTE:b26_p2_xiii_topology_check",
        "app_beat:EXECUTE:b26_p2_xiii_topology_check",
        "app_ingress:EXECUTE:b26_p2_xiii_topology_check",
    }
)

# Retire XII app_user authorship surfaces (no longer reachable; the
# database denies them). They remain in _XII for history but are
# subtracted here so coverage does not require testing impossible
# effects.
_XIII_RETIRED = frozenset(
    {
        "app_user:EXECUTE:b26_p2_record_provider_auth_consequence",
        "app_user:INSERT:b26_p2_provider_auth_consequence.auth_method",
        "app_user:INSERT:b26_p2_provider_auth_consequence.auth_version",
        "app_user:INSERT:b26_p2_provider_auth_consequence.body_sha256",
        "app_user:INSERT:b26_p2_provider_auth_consequence.provider",
        "app_user:INSERT:b26_p2_provider_auth_consequence.provider_event_reference",
        "app_user:INSERT:b26_p2_provider_auth_consequence.signature_envelope_sha256",
        "app_user:INSERT:b26_p2_provider_auth_consequence.tenant_id",
        "app_user:INSERT:b26_p2_provider_auth_consequence.webhook_ingress_identity_id",
    }
)

XIII_COVERED_SURFACES: frozenset[str] = (_XII | _XIII_NEW) - _XIII_RETIRED

__all__ = ("XIII_COVERED_SURFACES",)
