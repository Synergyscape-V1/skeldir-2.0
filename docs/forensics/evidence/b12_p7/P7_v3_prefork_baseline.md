# P7 v3 Baseline (Prefork + Authority Boundary + Context Canonicalization)

Date: 2026-03-07  
Branch inspected: `b12-p6-v5-default-deny-schemes`  
Scope: Corrective-action hypotheses H01-H03 from the P7 worker coherence directive.

## Hypothesis Validation Summary

- H01 (prefork fork-safety and listener init physics unproven): **Validated**.
- H02 (SystemContext origination boundary not merge-blocked): **Validated**.
- H03 (signature purity present but canonical context-access proof incomplete): **Validated**.

## H01 — Prefork fork-safety proof gap

Findings:
- Real-worker revocation runtime proof used solo pool only:
  - `backend/tests/integration/test_b12_p7_worker_revocation_runtime.py` (pre-remediation worker command was `-P solo -c 1`).
- No CI proof asserted prefork child-process listener isolation, no protocol-error guard, and no prefork steady-state zero-I/O invariant.

Impact:
- LISTEN/NOTIFY socket inheritance risk under prefork remained unproven at adjudication time.

## H02 — System authority origination boundary missing

Findings:
- `SystemAuthorityEnvelope` construction existed in multiple modules:
  - `backend/app/api/webhooks.py`
  - `backend/app/services/attribution.py`
  - `backend/app/services/llm_dispatch.py`
  - `backend/app/tasks/maintenance.py`
  - `backend/app/tasks/matviews.py`
- No merge-blocking lint/test prevented future system-authority origination in disallowed user-reachable modules.

Impact:
- Session-revocation bypass semantics for `SystemAuthorityEnvelope` were structurally exposed without a CI boundary guard.

## H03 — Canonical context proof gap after signature purity

Findings:
- Tenant-task signatures were already authority-cleaned, but there was no dedicated proof gate asserting canonical context helper usage (`task_tenant_id`) across all tenant-scoped tasks plus fail-fast helper semantics.

Impact:
- Future drift risk (ad-hoc context access or signature pollution regression) lacked a dedicated merge blocker.

## Baseline Conclusion

P7 remained not-complete for this directive’s EG1/EG2/EG3 set until:
1. prefork runtime/fork-safety proofs were added,
2. system-authority origination boundary was enforced by merge-blocking test,
3. canonical context-access proof was added as its own gate.
