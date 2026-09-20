#!/usr/bin/env python3
"""B2.6-P2 Corrective VII effect-coverage registry (extends VI).

VI_COVERED_SURFACES remains the predecessor baseline (unchanged file).
VII adds the new sovereign-fact, finiteness, and observability surfaces
introduced by migration 202609210001. The governing topology proof loads
VII_COVERED_SURFACES; UNTESTED>0 fails coverage. A new sibling outside
both registries appears via the open-world census (capability_surface)
as UNCLASSIFIED_RUNTIME_AUTHORITY, never as silent UNTESTED=0.
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_vi_coverage import VI_COVERED_SURFACES as _VI  # noqa: PLC0415
except ImportError:
    from b26_p2_vi_coverage import VI_COVERED_SURFACES as _VI  # noqa: PLC0415

_VII_NEW = frozenset(
    {
        # Complete sovereign-fact custody (P2-CA7-02): verified/currency/
        # amount share the custody law; issuer lawful mint + worker mint
        # dead-end for the new columns (VII battery R7 cells).
        "app_user:INSERT:webhook_ingress_identities.verified_amount_currency",
        "app_user:INSERT:webhook_ingress_identities.verified_amount_minor",
        "app_user:INSERT:webhook_ingress_identities.verified_commerce_ingress_state",
        "app_user:UPDATE:webhook_ingress_identities.verified_amount_currency",
        "app_user:UPDATE:webhook_ingress_identities.verified_amount_minor",
        "app_user:UPDATE:webhook_ingress_identities.verified_commerce_ingress_state",
        "app_worker:INSERT:webhook_ingress_identities.verified_amount_currency",
        "app_worker:INSERT:webhook_ingress_identities.verified_amount_minor",
        "app_worker:INSERT:webhook_ingress_identities.verified_commerce_ingress_state",
        # Heartbeat finiteness/observability (P2-CA7-05/06): relay writes,
        # API/user/ro read (VII battery OF7/OI7 cells + topology).
        "app_relay:INSERT:b26_p2_evaluator_heartbeat",
        "app_relay:INSERT:b26_p2_evaluator_heartbeat.last_tick",
        "app_relay:INSERT:b26_p2_evaluator_heartbeat.tenant_id",
        "app_relay:UPDATE:b26_p2_evaluator_heartbeat.last_tick",
        "app_relay:UPDATE:b26_p2_evaluator_heartbeat.tenant_id",
    }
)

VII_COVERED_SURFACES: frozenset[str] = _VI | _VII_NEW

__all__ = ("VII_COVERED_SURFACES",)
