#!/usr/bin/env python3
"""B2.6-P2 Corrective VI effect-coverage manifest (static registry).

Maps every mechanically reachable load-bearing surface (as enumerated by
b26_p2_capability_surface.py from live catalog facts) to the required-CI
cell that exercises it. The governing topology proof loads this registry
and fails coverage (UNTESTED > 0) unless every reachable surface is
exercised. A new sibling grant/function/column that can produce a
prohibited effect appears in the generator output automatically and fails
this gate until a falsifier covers it (Gate 29 active falsifier).

Cell vocabulary:
  R6-xx   root-authority battery (test_b26_p2_corrective_vi_sovereign_root.py)
  CP6-xx  consequence-proof battery (same file)
  OD6-xx  operational-disposition battery (same file)
  V-*     predecessor batteries (still green under VI head)
  TOPO-*  compiled topology falsifier/journey (prove_b26_p2_production_topology.py)
  NEG-*   active negative controls (b26_p2_vi_negatives.py)
"""

from __future__ import annotations

# --- forged_canonical_root (ROOT_TABLES + ROOT_ROUTINES) ---
_ROOT = frozenset(
    {
        # Issuer dispatch issuance: lawful accept + wrong-day/12h refusal
        # (R6-01/03/04) + deployed forged-dispatch falsifier (TOPO-F-vi1).
        "app_user:INSERT:b23_match_task_dispatches",
        "app_user:INSERT:b23_match_task_dispatches.delivery_state",
        "app_user:INSERT:b23_match_task_dispatches.provider",
        "app_user:INSERT:b23_match_task_dispatches.queue",
        "app_user:INSERT:b23_match_task_dispatches.task_name",
        "app_user:INSERT:b23_match_task_dispatches.tenant_id",
        "app_user:INSERT:b23_match_task_dispatches.webhook_ingress_identity_id",
        "app_user:INSERT:b23_match_task_dispatches.window_end",
        "app_user:INSERT:b23_match_task_dispatches.window_start",
        # Issuer directory projections: coherent accept (journeys) +
        # forged-directory falsifier (TOPO forged_window, V battery).
        "app_user:INSERT:b26_p2_task_authority_directory",
        "app_user:INSERT:b26_p2_task_authority_directory.tenant_id",
        "app_user:INSERT:b26_p2_task_authority_directory.webhook_ingress_identity_id",
        "app_user:INSERT:b26_p2_task_authority_directory.window_end",
        "app_user:INSERT:b26_p2_task_authority_directory.window_start",
        # Issuer ingress custody: lawful mint (journeys) + clock/provider/
        # tenant immutability once authoritative (R6-07/07b).
        "app_user:INSERT:webhook_ingress_identities",
        "app_user:INSERT:webhook_ingress_identities.event_timestamp",
        "app_user:INSERT:webhook_ingress_identities.provider",
        "app_user:INSERT:webhook_ingress_identities.tenant_id",
        "app_user:UPDATE:webhook_ingress_identities.event_timestamp",
        "app_user:UPDATE:webhook_ingress_identities.provider",
        "app_user:UPDATE:webhook_ingress_identities.tenant_id",
        # Issuer dispatch mutation: frozen-column matrix (R6-08/08b/11) +
        # direct-publish transport safety (R6 direct_publish).
        "app_user:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_user:UPDATE:b23_match_task_dispatches.provider",
        "app_user:UPDATE:b23_match_task_dispatches.queue",
        "app_user:UPDATE:b23_match_task_dispatches.task_name",
        "app_user:UPDATE:b23_match_task_dispatches.tenant_id",
        "app_user:UPDATE:b23_match_task_dispatches.webhook_ingress_identity_id",
        "app_user:UPDATE:b23_match_task_dispatches.window_end",
        "app_user:UPDATE:b23_match_task_dispatches.window_start",
        # Admission resolver EXECUTE: role-DSN resolution (R6-09) +
        # worker admission before B2.3 in every journey (TOPO).
        "app_user:EXECUTE:b26_p2_resolve_dispatch_authority",
        "app_worker:EXECUTE:b26_p2_resolve_dispatch_authority",
        # Worker ingress-plane dead end: mint allowed, execution denied
        # (R6 worker_ingress cell); relay lawful publish (TOPO recovery).
        "app_worker:INSERT:webhook_ingress_identities",
        "app_worker:INSERT:webhook_ingress_identities.event_timestamp",
        "app_worker:INSERT:webhook_ingress_identities.provider",
        "app_worker:INSERT:webhook_ingress_identities.tenant_id",
        "app_worker:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_relay:UPDATE:b23_match_task_dispatches.delivery_state",
    }
)

# --- false_conducted (COMPLETION_TABLES + COMPLETION_ROUTINES) ---
_CONDUCTED = frozenset(
    {
        # Relay lawful publish + mint refusal (TOPO recovery + F-v3).
        "app_relay:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_relay:UPDATE:b26_p2_execution_outbox.state",
        # Issuer issuance (TOPO journeys) + direct-publish safety (R6).
        "app_user:INSERT:b23_match_task_dispatches",
        "app_user:INSERT:b23_match_task_dispatches.delivery_state",
        "app_user:INSERT:b26_p2_execution_outbox",
        "app_user:INSERT:b26_p2_execution_outbox.state",
        "app_user:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_user:UPDATE:b26_p2_execution_outbox.state",
        # Worker gate + record EXECUTE: lawful conduction (TOPO journeys,
        # CP6-01), refusals (CP6 battery), synthetic-proof REDs
        # (TOPO F-vi2, NEG-M-VI-05/06).
        "app_worker:EXECUTE:b26_p2_mark_conducted",
        "app_worker:EXECUTE:b26_p2_record_conduction_receipt",
        # Worker B2.3 authorship duty: engine verdict writes in every
        # journey + maturity-duty cell (CP6 worker_duty).
        "app_worker:INSERT:b23_match_verdicts",
        "app_worker:INSERT:b23_match_verdicts.status",
        "app_worker:UPDATE:b23_match_verdicts.status",
        # Worker/outbox delivery writes: direct-publish safety (R6).
        "app_worker:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_worker:UPDATE:b26_p2_execution_outbox.state",
    }
)

# --- stale_suppression (DISPOSITION_TABLES + DISPOSITION_ROUTINES) ---
_STALE = frozenset(
    {
        # Transport result writes per principal: single-channel shapes
        # never suppress (OD6 telemetry cells per role).
        "app_beat:INSERT:celery_taskmeta",
        "app_beat:INSERT:celery_taskmeta.status",
        "app_beat:UPDATE:celery_taskmeta.status",
        "app_relay:INSERT:celery_taskmeta",
        "app_relay:INSERT:celery_taskmeta.status",
        "app_relay:UPDATE:celery_taskmeta.status",
        "app_worker:INSERT:celery_taskmeta",
        "app_worker:INSERT:celery_taskmeta.status",
        "app_worker:UPDATE:celery_taskmeta.status",
        # Signal EXECUTE per consumer: health endpoint (TOPO F-v2, user),
        # beat-scheduled evaluator (TOPO evaluator wiring, relay),
        # worker reads cell.
        "app_relay:EXECUTE:b26_p2_operational_disposition",
        "app_relay:EXECUTE:b26_p2_stale_unconducted",
        "app_user:EXECUTE:b26_p2_operational_disposition",
        "app_user:EXECUTE:b26_p2_stale_unconducted",
        "app_worker:EXECUTE:b26_p2_operational_disposition",
        "app_worker:EXECUTE:b26_p2_stale_unconducted",
        # Relay recovery writes: lawful publish (TOPO recovery) +
        # multi-role metadata bumps keep stale actionable (OD6-08).
        "app_relay:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_relay:UPDATE:b23_match_task_dispatches.last_publish_error",
        "app_relay:UPDATE:b23_match_task_dispatches.publish_attempts",
        "app_relay:UPDATE:b23_match_task_dispatches.updated_at",
        "app_relay:UPDATE:b26_p2_execution_outbox.last_publish_error",
        "app_relay:UPDATE:b26_p2_execution_outbox.next_retry_at",
        "app_relay:UPDATE:b26_p2_execution_outbox.publish_attempts",
        "app_relay:UPDATE:b26_p2_execution_outbox.state",
        "app_relay:UPDATE:b26_p2_execution_outbox.updated_at",
        # Issuer issuance/instrumentation: anchor-preset stripping,
        # mint-published/retry-bound refusals, multi-role bumps.
        "app_user:INSERT:b23_match_task_dispatches",
        "app_user:INSERT:b23_match_task_dispatches.delivery_state",
        "app_user:INSERT:b23_match_task_dispatches.dispatched_at",
        "app_user:INSERT:b23_match_task_dispatches.first_published_at",
        "app_user:INSERT:b23_match_task_dispatches.last_publish_error",
        "app_user:INSERT:b23_match_task_dispatches.publish_attempts",
        "app_user:INSERT:b23_match_task_dispatches.updated_at",
        "app_user:INSERT:b26_p2_execution_outbox",
        "app_user:INSERT:b26_p2_execution_outbox.last_publish_error",
        "app_user:INSERT:b26_p2_execution_outbox.next_retry_at",
        "app_user:INSERT:b26_p2_execution_outbox.publish_attempts",
        "app_user:INSERT:b26_p2_execution_outbox.state",
        "app_user:INSERT:b26_p2_execution_outbox.updated_at",
        "app_user:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_user:UPDATE:b23_match_task_dispatches.dispatched_at",
        "app_user:UPDATE:b23_match_task_dispatches.first_published_at",
        "app_user:UPDATE:b23_match_task_dispatches.last_publish_error",
        "app_user:UPDATE:b23_match_task_dispatches.publish_attempts",
        "app_user:UPDATE:b23_match_task_dispatches.updated_at",
        "app_user:UPDATE:b26_p2_execution_outbox.last_publish_error",
        "app_user:UPDATE:b26_p2_execution_outbox.next_retry_at",
        "app_user:UPDATE:b26_p2_execution_outbox.publish_attempts",
        "app_user:UPDATE:b26_p2_execution_outbox.state",
        "app_user:UPDATE:b26_p2_execution_outbox.updated_at",
        # Issuer/worker DLQ writes: DLQ-alone never suppresses; joint
        # agreement is terminal-counted; status edits are monotonic
        # (OD6 telemetry cells).
        "app_user:INSERT:worker_failed_jobs",
        "app_user:INSERT:worker_failed_jobs.status",
        "app_user:INSERT:worker_failed_jobs.task_id",
        "app_user:UPDATE:worker_failed_jobs.status",
        "app_user:UPDATE:worker_failed_jobs.task_id",
        "app_worker:INSERT:worker_failed_jobs",
        "app_worker:INSERT:worker_failed_jobs.status",
        "app_worker:INSERT:worker_failed_jobs.task_id",
        "app_worker:UPDATE:worker_failed_jobs.status",
        "app_worker:UPDATE:worker_failed_jobs.task_id",
        # Worker instrumentation: multi-role bumps + direct-publish
        # safety + duty cells.
        "app_worker:UPDATE:b23_match_task_dispatches.delivery_state",
        "app_worker:UPDATE:b23_match_task_dispatches.last_publish_error",
        "app_worker:UPDATE:b23_match_task_dispatches.publish_attempts",
        "app_worker:UPDATE:b23_match_task_dispatches.updated_at",
        "app_worker:UPDATE:b26_p2_execution_outbox.last_publish_error",
        "app_worker:UPDATE:b26_p2_execution_outbox.next_retry_at",
        "app_worker:UPDATE:b26_p2_execution_outbox.publish_attempts",
        "app_worker:UPDATE:b26_p2_execution_outbox.state",
        "app_worker:UPDATE:b26_p2_execution_outbox.updated_at",
    }
)

# --- silent_quarantine (readers per principal) ---
_Q = frozenset(
    {
        # Health endpoint (issuer reads, TOPO F-v2 asserts the field),
        # beat-scheduled evaluator (relay reads, TOPO wiring asserts
        # execution), worker reads cell.
        "app_relay:SELECT:b26_p2_execution_quarantine",
        "app_user:SELECT:b26_p2_execution_quarantine",
        "app_worker:SELECT:b26_p2_execution_quarantine",
    }
)

VI_COVERED_SURFACES: frozenset[str] = _ROOT | _CONDUCTED | _STALE | _Q

__all__ = ("VI_COVERED_SURFACES",)
