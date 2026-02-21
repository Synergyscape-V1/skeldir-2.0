# B1.1-P3 Proof Index

## Scope
- Phase: `B1.1-P3 - Migrate Core Cryptographic Secrets to Secrets Manager + Rotation-Safe Semantics`
- Primary workflow: `.github/workflows/b11-p3-crypto-rotation-adjudication.yml`
- Local verification date: `2026-02-21`

## Exit Gate 1 - Secrets Manager Source-of-Truth + Audit Tether
- Stage runtime/source-of-truth probe log: `docs/forensics/evidence/b11_p3/stage_boot_trace.txt`
- CloudTrail proof artifact: `docs/forensics/evidence/b11_p3/cloudtrail_getsecretvalue_proof.txt`
- Code enforcement reference: `backend/app/core/secrets.py`

## Exit Gate 2 - Bounded-Staleness Cache Safety
- Cache refresh + fail-closed mint log: `docs/forensics/evidence/b11_p3/cache_refresh_bound_test_log.txt`
- Unknown `kid` forced refresh + graceful degradation log: `docs/forensics/evidence/b11_p3/jwt_unknown_kid_refresh_drill_log.txt`
- Test source: `backend/tests/test_b11_p3_jwt_rotation_semantics.py`

## Exit Gate 3 - JWT Rotation Overlap Drill (Non-Vacuous)
- Overlap drill log: `docs/forensics/evidence/b11_p3/jwt_rotation_overlap_drill_log.txt`
- Missing-kid negative-control and bounded-key-ring tests: `backend/tests/test_b11_p3_jwt_rotation_semantics.py`

## Exit Gate 4 - Envelope Key-ID Addressed Decryption (Performance-Safe)
- Multi-decrypt static guard proof: `docs/forensics/evidence/b11_p3/no_multi_decrypt_guard.txt`
- Decrypt-once runtime assertion: `docs/forensics/evidence/b11_p3/envelope_rotation_backward_compat_log.txt`
- Guard implementation: `scripts/security/b11_p3_no_multi_decrypt_guard.py`

## Exit Gate 5 - Backward-Compat Decrypt After Rotation
- Rotation backward-compat proof log: `docs/forensics/evidence/b11_p3/envelope_rotation_backward_compat_log.txt`
- Test source: `backend/tests/test_b11_p3_platform_keyring_semantics.py`

## Exit Gate 6 - Evidence Pack Published
- Index: `docs/forensics/evidence/b11_p3/PROOF_INDEX.md`
- Required files present:
  - `docs/forensics/evidence/b11_p3/stage_boot_trace.txt`
  - `docs/forensics/evidence/b11_p3/cloudtrail_getsecretvalue_proof.txt`
  - `docs/forensics/evidence/b11_p3/jwt_rotation_overlap_drill_log.txt`
  - `docs/forensics/evidence/b11_p3/cache_refresh_bound_test_log.txt`
  - `docs/forensics/evidence/b11_p3/jwt_unknown_kid_refresh_drill_log.txt`
  - `docs/forensics/evidence/b11_p3/envelope_rotation_backward_compat_log.txt`
  - `docs/forensics/evidence/b11_p3/no_multi_decrypt_guard.txt`
  - `docs/forensics/evidence/b11_p3/schema_key_id_migration_proof.txt`

## CI Run Mapping
- `RUN_ID=PENDING` until first execution of `b11-p3-crypto-rotation-adjudication`.
- On first passing run, replace `PENDING` with run URL and immutable artifact IDs.
