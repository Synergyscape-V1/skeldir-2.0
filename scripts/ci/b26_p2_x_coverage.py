#!/usr/bin/env python3
"""B2.6-P2 Corrective X effect-coverage registry (extends IX).

IX_COVERED_SURFACES remains the predecessor baseline (unchanged file).
X changes the reachable universe itself:

- the single per-candidate classifier
  (public.b26_p2_classify_candidate) is EXECUTable by
  app_worker/app_user. The thin Python adapter observes every
  disposition through it; the contract oracle judges it against
  hardcoded phase law (tab/unicode/edge cells).
- the ASCII-strip normalization family (ascii_strip,
  strip_provider/currency_token, normalize_provider/currency) is the
  only whitespace implementation on meaning-bearing paths.
- the conducted/receipt effect guards
  (public.b26_p2_guard_conducted_transition /
  public.b26_p2_guard_conduction_receipt + their triggers) adjudicate
  every conducted transition and every receipt write regardless of
  writer: weakened approved bodies, hint-named helpers, same-name
  overloads, and direct UPDATEs all refuse (X canary battery C1/C2/C5/
  C6 + PF-06/PF-09/PF-10 falsifiers). Trigger-fire is proven by those
  canaries; the capability manifest tracks the EXECUTE grants above.
- the provenance attester
  (public.b26_p2_attest_provenance_evidence) is EXECUTable by app_user
  and is the sole promotion path: bare status writes refuse, genuine
  signed re-ingestion restores through recorded evidence.
- the scheduler-plane tick executes inline in the beat scheduler
  (no queue consumer required) under the app_beat credential with
  column-scoped tenant enumeration.

The governing topology proof loads X_COVERED_SURFACES; UNTESTED>0
fails coverage. Meaning drift (same-name body/owner/signature change)
is governed separately by the reviewed universe pin
(contracts-internal/governance/b26_p2_authority_universe.pin.json)
plus the X live source-equivalence check
(validate_b26_p2_x_authority).
"""

from __future__ import annotations

try:
    from scripts.ci.b26_p2_ix_coverage import IX_COVERED_SURFACES as _IX  # noqa: PLC0415
except ImportError:
    from b26_p2_ix_coverage import IX_COVERED_SURFACES as _IX  # noqa: PLC0415

_X_REMOVED = frozenset(
    {
        # No IX surface is revoked by X; every predecessor grant
        # persists (verified by the conservation battery).
    }
)

_X_NEW = frozenset(
    {
        # Single semantic authority (Corrective X, Group A): the worker
        # adapter observes dispositions through the classifier; the
        # oracle judges tab/unicode/edge law against it. The
        # normalization family is the only whitespace implementation
        # on meaning-bearing paths (oracle cells).
        "app_worker:EXECUTE:b26_p2_classify_candidate",
        "app_user:EXECUTE:b26_p2_classify_candidate",
        "app_worker:EXECUTE:b26_p2_normalize_provider",
        "app_worker:EXECUTE:b26_p2_normalize_currency",
        "app_user:EXECUTE:b26_p2_normalize_provider",
        "app_user:EXECUTE:b26_p2_normalize_currency",
        "app_worker:EXECUTE:b26_p2_ascii_strip",
        "app_user:EXECUTE:b26_p2_ascii_strip",
        "app_worker:EXECUTE:b26_p2_strip_provider_token",
        "app_user:EXECUTE:b26_p2_strip_provider_token",
        "app_worker:EXECUTE:b26_p2_strip_currency_token",
        "app_user:EXECUTE:b26_p2_strip_currency_token",
        # Evidence-backed provenance (Corrective X, Group C): the
        # attester is the sole promotion path (canary C8 + adoption
        # restoration).
        "app_user:EXECUTE:b26_p2_attest_provenance_evidence",
        # Scheduler-plane execution (Corrective X, Group E): inline
        # beat-scheduler tick under the beat credential.
        "app_beat:EXECUTE:b26_p2_record_scheduler_heartbeat",
    }
)

X_COVERED_SURFACES: frozenset[str] = (_IX - _X_REMOVED) | _X_NEW

__all__ = ("X_COVERED_SURFACES",)
