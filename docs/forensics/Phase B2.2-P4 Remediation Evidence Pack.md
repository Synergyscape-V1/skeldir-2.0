# Phase B2.2-P4 Remediation Evidence Pack

Date: 2026-04-21  
Branch basis: `main` (local working state)  
Directive: Idempotent ACK semantics + webhook-orchestration side-effect isolation

## 1) Initial forensic findings on `main`

- Duplicate side-effect suppression was already functionally present for webhook success paths: downstream scheduling was gated by `result["is_duplicate"]`.
- The duplicate signal was still carried through private ORM-instance mutation (`_ingestion_duplicate`) in `event_service`, which is architecturally brittle and phase-opaque.
- ACK protocol behavior was already consistent with prior inventory: auth/tenant failures returned `401`, malformed authenticated payloads were DLQ-routed with `200` + `status: dlq_routed`, and duplicates returned idempotent `200` success.
- Stripe canonical and alias routes both existed, but P4 merge-protected adjudication for orchestration idempotency + ACK matrix was not yet wired as a dedicated gate.

## 2) Remediations implemented

- Replaced hidden duplicate signaling in `backend/app/ingestion/event_service.py`:
  - Added explicit typed contract surface `IngestionResultState` (`inserted`, `duplicate`) and `IngestionDecision`.
  - Added `ingest_event_with_decision(...)` to return event + explicit state.
  - Kept `ingest_event(...)` as backward-compatible wrapper returning the event only.
  - Updated `ingest_with_transaction(...)` to consume typed decision and return explicit `is_duplicate` plus `ingestion_state`.
  - Removed private `_ingestion_duplicate` marker usage from authoritative ingestion path.
- Added P4 governance + merge-blocking adjudication surface:
  - `contracts-internal/governance/b22_p4_idempotent_ack_orchestration.main.json`
  - `scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py`
  - `backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py`
  - CI wiring in `.github/workflows/ci.yml`.
- Added runtime P4 proof suite:
  - `backend/tests/test_b22_p4_idempotent_ack_orchestration.py`
  - Proves duplicate replay emits one durable row and one downstream schedule only.
  - Proves ACK matrix outcomes for success, duplicate, forged, malformed authenticated payload, oversized payload, missing/wrong tenant key, and unsupported family.
  - Proves stripe canonical and alias route ACK parity for success + forged outcomes.

## 3) Falsifiable proof outcomes (local run)

- `python scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py` -> **PASS**
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py -q` -> **5 passed**
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration.py -q` -> **4 skipped** (authoritative local DB lacks migrated `webhook_ingress_identities`; suite is configured to skip locally unless `SKELDIR_B22_P4_REQUIRE_DB_PROOFS=1`)

## 4) Exit gate adjudication snapshot

- Exit Gate 1 (Duplicate-Suppression Mechanism): **Addressed** with explicit typed decision contract replacing hidden private marker propagation.
- Exit Gate 2 (B0.4 Non-Regression): **Guarded** by backward-compatible `ingest_event(...)` wrapper + unchanged B0.4 call surface.
- Exit Gate 3 (ACK Protocol): **Guarded** by dedicated ACK matrix runtime proofs and CI enforcer.
- Exit Gate 4 (Merge-Blocking Adjudication): **Wired** via dedicated P4 enforcer + tests in CI workflow.

## 5) Protected-branch landing status

- Protected workflow PR: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/367`
- PR state: **MERGED** at `2026-04-21T18:00:23Z`
- Merge commit on `main`: `7a84738adc38de30a8b1c54e7c9204ec7a33aee0`
- Required-check adjudication for PR head passed prior to merge (authoritative `gh pr checks 367 --required` evidence captured).
- Post-merge `main` CI run: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24738191332`
- Post-merge `main` CI status: **completed / success** for merge commit `7a84738adc38de30a8b1c54e7c9204ec7a33aee0`.

## 6) Completion verdict

- Phase B2.2-P4 directive closure status: **COMPLETE**
- Falsifiable closure basis:
  - explicit duplicate-state orchestration contract replaces hidden private marker coupling,
  - merge-blocking P4 enforcement and runtime proofs are wired in CI,
  - protected-branch PR merge to `main` is complete,
  - and full `main` CI run for the merge commit completed green.
