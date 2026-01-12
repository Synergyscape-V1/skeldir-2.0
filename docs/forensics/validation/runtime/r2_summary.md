# R2 Data-Truth Hardening Validation Summary (Truth Anchor)

## Status

R2 = **COMPLETE** as of:

- **Candidate SHA:** `ddda11a51d378e6220b6c33fa8f87b67d51ace22`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20543553804

## Mission (Non-Negotiable)

Prove, in a single CI run bound to the candidate SHA, both:

1. **DB prevents violations** (RLS + triggers + privileges)
2. **Application/worker fabric is innocent**
   - **AUTHORITATIVE:** Postgres `docker logs` statement capture over a **window + per-scenario** delimited runtime suite
   - **MANDATORY secondary:** ORM capture cross-check (same window IDs/scenario IDs)
   - **CO-PRIMARY:** static behavioral innocence + canary integrity (latent paths + anti-theater)

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R2-FIX-1 | Scenario suite hard gate | PASS |
| EG-R2-FIX-2 | DB capture enablement proof (`log_statement=all`, `logging_collector=off`) | PASS |
| EG-R2-FIX-3 | DB window binding + per-scenario DB activity | PASS |
| EG-R2-FIX-4 | DB runtime innocence (AUTHORITATIVE) | PASS |
| EG-R2-FIX-5 | ORM runtime innocence (MANDATORY secondary) | PASS |
| EG-R2-FIX-6 | Instrument consistency (DB vs ORM) | PASS |
| EG-R2-FIX-7 | Static behavioral innocence | PASS |
| EG-R2-FIX-8 | Canary integrity (DB parser + static detector) | PASS |
| EG-R2-ENFORCEMENT | DB prevents violations (RLS + triggers + privileges) | PASS |

## Evidence (Key Verdict Values)

### EG-R2-FIX-1 — Scenario Suite Hard Gate

- `SCENARIOS_EXECUTED=6`
- `SCENARIOS_PASSED=6`

### EG-R2-FIX-3/4 — DB Runtime Innocence (AUTHORITATIVE, windowed)

- `TOTAL_DB_STATEMENTS_CAPTURED_IN_WINDOW=72`
- Per-scenario non-marker DB statements:
  - `S1=7`, `S2=11`, `S3=7`, `S4=6`, `S5=7`, `S6=6`
- `DB_FORBIDDEN_MATCH_COUNT=0` (immutable tables × destructive verbs)

### EG-R2-FIX-5 — ORM Cross-Check (Mandatory secondary)

- `TOTAL_ORM_STATEMENTS_CAPTURED_IN_WINDOW=32`
- Per-scenario non-marker ORM statements:
  - `S1=3`, `S2=5`, `S3=3`, `S4=2`, `S5=3`, `S6=2`
- `ORM_FORBIDDEN_MATCH_COUNT=0`

### EG-R2-FIX-7/8 — Static + Canary

- Static scope: `SCOPE_FILES_COUNT=108`
- `STATIC_FORBIDDEN_MATCH_COUNT=0`
- Canary: DB parser fails with destructive matches; static detector fails with canary file and passes after removal

## Where the Evidence Lives

- Workflow: `.github/workflows/r2-data-truth-hardening.yml`
- Runtime suite: `scripts/r2/runtime_scenario_suite.py`
- DB window audit (authoritative): `scripts/r2/db_log_window_audit.py`
- ORM gate: `scripts/r2/orm_window_audit.py`
- Instrument consistency: `scripts/r2/instrument_consistency_gate.py`
- Static audit: `scripts/r2/static_behavioral_audit.py`

