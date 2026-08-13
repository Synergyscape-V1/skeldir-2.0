# ADR-016: B2.5-P13 Confidence Truth Downgrade

Status: accepted  
Date: 2026-08-13

## Context

Revision `202608131200` adds nullable, producer-owned confidence-classification context to `bayesian_model_fits` and an index over append-only `b24_dirty_events`. Historical rows are intentionally not backfilled because they were not classified from the frozen B2.4 source context.

The repository migration policy requires every destructive downgrade statement to be explicitly acknowledged. Removing the new columns during a downgrade discards classifications produced after this revision; that loss cannot be reconstructed faithfully from live revenue or request-time inference.

## Decision

The downgrade remains available for controlled rollback and removes only objects introduced by revision `202608131200`. Each destructive SQL line carries `CI:DESTRUCTIVE_OK` and this ADR reference. Operators must treat the downgrade as data-destructive and capture or accept loss of post-upgrade confidence classifications before executing it.

The normal production recovery path is forward-only: deploy a corrective migration rather than downgrade after new fits have been classified. No upgrade-path destructive DDL is authorized by this decision.

## Consequences

- Upgrade remains additive and preserves all existing rows.
- Historical rows remain honestly unclassified (`NULL`) rather than inferred.
- Downgrade is mechanically reversible at the schema level but intentionally loses newly persisted confidence context.
- Canonical schema authority continues to be generated from the migration head.
