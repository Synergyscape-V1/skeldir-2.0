# ADR-017: B2.5-P13 C10 Inference-Provenance Downgrade

Status: accepted
Date: 2026-08-24

## Context

Revision `202608250900` adds the producer-owned inference-policy bundle,
observed-versus-authorized posterior topology, and explicit policy-replan
evidence to `bayesian_model_fits`. These fields are historical evidence: they
record the exact regime and topology that produced a confidence result and
cannot be reconstructed truthfully from whatever policy happens to be deployed
later.

Repository migration policy requires every destructive downgrade statement to
be explicitly acknowledged. Removing the C10 columns, constraints, or write
authority trigger discards or weakens evidence generated after the upgrade.

## Decision

The downgrade remains available only for a controlled rollback. It first
restores the pre-C10 terminal-truth trigger, then removes only C10-owned
constraints, trigger/function, and columns. Every destructive SQL statement
carries `CI:DESTRUCTIVE_OK` and this ADR reference.

Operators must capture or explicitly accept loss of post-upgrade inference
provenance before invoking the downgrade. The normal production recovery path
is forward-only: deploy a corrective migration instead of downgrading after C10
fits have executed.

## Consequences

- Upgrade remains additive; historical rows retain null provenance and are
  treated as unavailable by the Trust read path rather than backfilled.
- Downgrade is schema-reversible but loses C10 policy and topology evidence.
- The pre-C10 terminal trigger is restored, avoiding a trigger function that
  references columns removed by the downgrade.
- No upgrade-path destructive DDL is authorized by this decision.
