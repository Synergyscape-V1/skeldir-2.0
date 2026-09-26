#!/usr/bin/env python3
"""B2.6-P2 Corrective XII effect-coverage registry (extends XI).

XI_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XII changes the reachable universe itself:

- the predecessor event P (successful provider authentication) is
  authored by the API application principal:
  ``b26_p2_record_provider_auth_consequence`` is EXECUTable by app_user
  (and migration admins) alone; the ingress principal cannot author P
  (XII-A battery AUTH-*);
- the witness is bound to P:
  ``b26_p2_record_ingress_auth_witness(uuid,text,text,text)`` derives
  the token deterministically from the independently recorded
  consequence; the single-argument form is fail-closed
  (``b26_p2_witness_no_auth_consequence``); ``governed_attestation``
  at runtime is migration/admin custody only;
- one serviceable regime: the XII migration refuses without the
  ingress principal; no auth law branches on role existence; the
  topology adjudicator (read-only) is observable by runtime roles;
  late provisioning converges deterministically (contract B).

The governing topology proof loads XII_COVERED_SURFACES; UNTESTED>0
fails coverage. Meaning drift is governed by the reviewed universe
pin plus the XII semantic manifest.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_xi_coverage import XI_COVERED_SURFACES as _XI  # noqa: PLC0415
except ImportError:
    from b26_p2_xi_coverage import XI_COVERED_SURFACES as _XI  # noqa: PLC0415

_XII_NEW = frozenset(
    {
        # Predecessor event P (Corrective XII, Class A): authored by
        # the API application principal in the HMAC-verified path;
        # observed (never authored) by the ingress boundary.
        "app_user:EXECUTE:b26_p2_record_provider_auth_consequence",
        "app_user:INSERT:b26_p2_provider_auth_consequence.auth_method",
        "app_user:INSERT:b26_p2_provider_auth_consequence.auth_version",
        "app_user:INSERT:b26_p2_provider_auth_consequence.body_sha256",
        "app_user:INSERT:b26_p2_provider_auth_consequence.provider",
        "app_user:INSERT:b26_p2_provider_auth_consequence.provider_event_reference",
        "app_user:INSERT:b26_p2_provider_auth_consequence.signature_envelope_sha256",
        "app_user:INSERT:b26_p2_provider_auth_consequence.tenant_id",
        "app_user:INSERT:b26_p2_provider_auth_consequence.webhook_ingress_identity_id",
        # Bound witness (Corrective XII, Class A): derived from P by
        # the ingress boundary; credential-only mint refused.
        "app_ingress:EXECUTE:b26_p2_record_ingress_auth_witness",
        # Topology adjudication (Corrective XII, Class C):
        # read-only strict-regime check observable by runtime roles.
        "app_user:EXECUTE:b26_p2_xii_topology_check",
        "app_worker:EXECUTE:b26_p2_xii_topology_check",
        "app_relay:EXECUTE:b26_p2_xii_topology_check",
        "app_beat:EXECUTE:b26_p2_xii_topology_check",
        "app_ingress:EXECUTE:b26_p2_xii_topology_check",
    }
)

XII_COVERED_SURFACES: frozenset[str] = _XI | _XII_NEW

__all__ = ("XII_COVERED_SURFACES",)
