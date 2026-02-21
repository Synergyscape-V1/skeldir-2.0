# B1.1-P3 Findings and Remediations

## Findings Validated
- `H01` validated pre-remediation: crypto key material was process-static with no bounded refresh.
- `H03/H04` validated pre-remediation: JWT verification path was singleton secret/JWKS with no `kid`-bounded ring fallback.
- `H05` partially already satisfied: `platform_credentials.key_id` existed, but decrypt path still depended on singleton key resolution.
- `H07` validated pre-remediation: no P3 non-vacuous rotation drills existed.

## Remediations Implemented
- Added rotation-safe key-ring semantics and bounded staleness caching in `backend/app/core/secrets.py`:
  - JWT key-ring parsing from source-of-truth secret payload.
  - Platform envelope key-ring parsing from source-of-truth secret payload.
  - Bounded cache staleness controls:
    - `SKELDIR_JWT_KEY_RING_MAX_STALENESS_SECONDS`
    - `SKELDIR_PLATFORM_KEY_RING_MAX_STALENESS_SECONDS`
  - Fail-closed mint behavior when refresh fails.
  - Stage/prod source-of-truth enforcement via control-plane checks.
- Added JWT `kid`-addressed verification + bounded fallback and rotation-safe minting in `backend/app/security/auth.py`.
- Refactored platform token decrypt flow in `backend/app/services/platform_credentials.py`:
  - Select ciphertext + `key_id`.
  - Resolve one key by `key_id`.
  - Decrypt each ciphertext once.
- Added static anti-pattern guard `scripts/security/b11_p3_no_multi_decrypt_guard.py`.
- Added non-vacuous P3 tests:
  - `backend/tests/test_b11_p3_jwt_rotation_semantics.py`
  - `backend/tests/test_b11_p3_platform_keyring_semantics.py`
  - `backend/tests/test_b11_p3_source_of_truth.py`
- Added CI adjudication workflow:
  - `.github/workflows/b11-p3-crypto-rotation-adjudication.yml`

## Residual External Dependency
- Stage CloudTrail GetSecretValue tether evidence requires stage-account credentials and cannot be completed from local-only context.
