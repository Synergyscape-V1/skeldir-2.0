#!/usr/bin/env python3
"""B2.6-P2 Corrective XI effect-coverage registry (extends X).

X_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XI changes the reachable universe itself:

- authentication-authoring capability moves to the dedicated ingress
  principal: ``b26_p2_record_ingress_auth_witness`` and
  ``b26_p2_attest_provenance_evidence`` are EXECUTable by app_ingress
  (and migration admins) alone. ``app_user`` EXECUTE on the attester
  is revoked (XI migration + XI-A battery XA-*): the predecessor
  surface ``app_user:EXECUTE:b26_p2_attest_provenance_evidence`` is
  removed here because the grant no longer exists.
- the P3 eligibility predicate
  (``b26_p2_state_eligible_for_p3``) is EXECUTable by the runtime
  roles as read-only classification (XI census validator + XI-D/XE
  battery): it mints nothing and no P3 principal can override it.
- the semantic-temporal manifest mechanism
  (``validate_b26_p2_xi_semantic_temporal``) derives the live SQL
  read-set and fails closed on unknown dependencies (XI-C battery
  XC-*: match_quality-style additions RED automatically).

The governing topology proof loads XI_COVERED_SURFACES; UNTESTED>0
fails coverage. Meaning drift is governed by the reviewed universe
pin plus the X live source-equivalence check and the XI semantic
manifest.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_x_coverage import X_COVERED_SURFACES as _X  # noqa: PLC0415
except ImportError:
    from b26_p2_x_coverage import X_COVERED_SURFACES as _X  # noqa: PLC0415

_XI_REMOVED = frozenset(
    {
        # XI revokes ordinary-application attestation authority: the
        # grant no longer exists, so the predecessor surface is
        # removed (adjudicated by the XI-A negative controls, not by
        # absence from this list).
        "app_user:EXECUTE:b26_p2_attest_provenance_evidence",
    }
)

_XI_NEW = frozenset(
    {
        # Evidence-backed authentication (Corrective XI, Class A):
        # the ingress principal alone authors witnesses and attests.
        "app_ingress:EXECUTE:b26_p2_record_ingress_auth_witness",
        "app_ingress:EXECUTE:b26_p2_attest_provenance_evidence",
        # Ingress persistence (Corrective XI, Class B): the ingress
        # principal alone persists HMAC-verified arrivals. Lawful
        # insert + witness + attest is the XB/XA battery path;
        # cross-tenant insert is refused (F-XI-B3); every other
        # runtime principal is refused authorship (F-XI-B1/B2).
        "app_ingress:INSERT:webhook_ingress_identities.event_timestamp",
        "app_ingress:INSERT:webhook_ingress_identities.provider",
        "app_ingress:INSERT:webhook_ingress_identities.tenant_id",
        "app_ingress:INSERT:webhook_ingress_identities.verified_amount_currency",
        "app_ingress:INSERT:webhook_ingress_identities.verified_amount_minor",
        "app_ingress:INSERT:webhook_ingress_identities.verified_commerce_ingress_state",
        # Precursor promotion / duplicate adoption of the ingress
        # principal's own rows (AR8 battery cell as amended for XI):
        # sovereign custody, authorship, and provenance triggers
        # bound every such write; non-ingress UPDATE paths refuse.
        "app_ingress:UPDATE:webhook_ingress_identities.event_timestamp",
        "app_ingress:UPDATE:webhook_ingress_identities.provider",
        "app_ingress:UPDATE:webhook_ingress_identities.tenant_id",
        "app_ingress:UPDATE:webhook_ingress_identities.verified_amount_currency",
        "app_ingress:UPDATE:webhook_ingress_identities.verified_amount_minor",
        "app_ingress:UPDATE:webhook_ingress_identities.verified_commerce_ingress_state",
        # P3 eligibility boundary (Corrective XI, Class D/P3):
        # read-only classification consumed by P3, overridable by none.
        "app_user:EXECUTE:b26_p2_state_eligible_for_p3",
        "app_worker:EXECUTE:b26_p2_state_eligible_for_p3",
        "app_relay:EXECUTE:b26_p2_state_eligible_for_p3",
        "app_beat:EXECUTE:b26_p2_state_eligible_for_p3",
        "app_ingress:EXECUTE:b26_p2_state_eligible_for_p3",
    }
)

XI_COVERED_SURFACES: frozenset[str] = (_X - _XI_REMOVED) | _XI_NEW

__all__ = ("XI_COVERED_SURFACES",)
