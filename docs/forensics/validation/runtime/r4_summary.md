# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **COMPLETE**.

- **Candidate SHA:** `4d8b261bf88d6bea554195c251a8b3d06363631b`
- **CI run:** https://github.com/Muk223/skeldir-2.0/actions/runs/20561344485
- **Last updated:** `2025-12-29`

## Exit Gates (R4-FIX)

- **EG-R4-FIX-1 (Postgres-only fabric is browser-provable):** PASS
- **EG-R4-FIX-2 (Explicit cross-tenant RLS bypass attempt):** PASS

## Evidence Policy

No artifact-only proofs. If the proof is not visible in the GitHub Actions run logs, it is inadmissible.

## Evidence (Browser-Verifiable Logs)

Log step: `Run R4 harness` in `.github/workflows/r4-worker-failure-semantics.yml`.

Proof lines observed in the CI logs for the run URL above:

- `R4_BROKER_SCHEME=sqla+postgresql`
- `R4_BACKEND_SCHEME=db+postgresql`
- `R4_BROKER_DSN_SHA256=480be02d7e3400fa415405d1b343d56165f2d4596ebe25615c46354a0511001b`
- `R4_BACKEND_DSN_SHA256=cbb79a35e3044b55f29ea5154480336d5bfdec42af1a05de8e088bc60c6e31d3`
- `R4_S3_TENANT_A=ec53a3c4-e905-5a47-95cd-3bb307107f42 R4_S3_TENANT_B=da393c8c-dfc8-5f4d-943f-f8b2ca3cc0bb R4_S3_TARGET_ROW_ID=f43a890c-de1c-4777-99be-f4dd16ca6624`
- `R4_S3_RESULT_ROWS=0`
