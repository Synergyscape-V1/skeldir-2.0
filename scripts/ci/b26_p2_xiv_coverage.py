#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV effect-coverage registry (extends XIII).

XIII_COVERED_SURFACES remains the predecessor baseline (unchanged file).
XIV changes the reachable universe itself:

- the immutable auth-root evidence identity
  ``b26_p2_auth_root_evidence``: SELECT-only observability for
  app_user/app_ingress (no runtime INSERT/UPDATE/DELETE; writes occur
  only through the SECURITY DEFINER atomic transition);
- the atomic transition additionally binds root evidence in the same
  transaction (same grant surface, new effect);
- the read-only XIV topology adjudicator
  ``b26_p2_xiv_topology_check`` (EXECUTE runtime roles; mints nothing;
  supersedes XIII with the root-evidence substrate).

The governing topology proof loads XIV_COVERED_SURFACES; UNTESTED>0
fails coverage.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_xiii_coverage import (
        XIII_COVERED_SURFACES as _XIII,
    )  # noqa: PLC0415
except ImportError:
    from b26_p2_xiii_coverage import XIII_COVERED_SURFACES as _XIII  # noqa: PLC0415

_XIV_NEW = frozenset(
    {
        # Immutable auth-root evidence (Corrective XIV, Classes A/B):
        # read-only observability, zero authorship.
        "app_user:SELECT:b26_p2_auth_root_evidence.auth_method",
        "app_user:SELECT:b26_p2_auth_root_evidence.auth_version",
        "app_user:SELECT:b26_p2_auth_root_evidence.body_sha256",
        "app_user:SELECT:b26_p2_auth_root_evidence.created_at",
        "app_user:SELECT:b26_p2_auth_root_evidence.id",
        "app_user:SELECT:b26_p2_auth_root_evidence.idempotency_key",
        "app_user:SELECT:b26_p2_auth_root_evidence.provider",
        "app_user:SELECT:b26_p2_auth_root_evidence.provider_native_event_reference",
        "app_user:SELECT:b26_p2_auth_root_evidence.signature_envelope_sha256",
        "app_user:SELECT:b26_p2_auth_root_evidence.tenant_id",
        "app_user:SELECT:b26_p2_auth_root_evidence.webhook_ingress_identity_id",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.auth_method",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.auth_version",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.body_sha256",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.created_at",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.id",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.idempotency_key",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.provider",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.provider_native_event_reference",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.signature_envelope_sha256",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.tenant_id",
        "app_ingress:SELECT:b26_p2_auth_root_evidence.webhook_ingress_identity_id",
        # Topology adjudication (Corrective XIV, Class B).
        "app_user:EXECUTE:b26_p2_xiv_topology_check",
        "app_worker:EXECUTE:b26_p2_xiv_topology_check",
        "app_relay:EXECUTE:b26_p2_xiv_topology_check",
        "app_beat:EXECUTE:b26_p2_xiv_topology_check",
        "app_ingress:EXECUTE:b26_p2_xiv_topology_check",
    }
)

XIV_COVERED_SURFACES: frozenset[str] = _XIII | _XIV_NEW

__all__ = ("XIV_COVERED_SURFACES",)
