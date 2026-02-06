# B0.7-P2 Remediation Evidence (Runtime Proof + Redaction + Fail-Fast)

Date: 2026-02-06
Branch: main
Status: PASS for B0.7-P2 exit gates (artifact-backed)

## Scope
Move B0.7-P2 from hypothesis to falsified-proof using only:
1. `main` diff
2. push-triggered Actions run evidence
3. deterministic test output
4. uploaded artifact contents

## Remediation Changes on main
Commit: `ac1405bf82788636df430078bc9a983027c40abe`
Title: `ci: harden b07 p2 fail-fast and redaction gates`

Changed files:
1. `.github/workflows/ci.yml`
2. `backend/tests/test_b07_p2_provider_enablement.py`

Implemented controls:
1. Provider gate env explicitly sets `LLM_PROVIDER_API_KEY` blank for non-vacuous missing-key execution.
2. Provider gate now proves both falsifiers:
   - enabled + missing key fails
   - disabled + missing key passes
3. Added deterministic redaction/artifact scan step in CI:
   - requires expected files
   - fails if canary appears in artifact tree
   - fails on non-redacted `LLM_PROVIDER_API_KEY=` and `Authorization: Bearer `
   - requires positive redaction markers in worker log

## Push-Triggered Proof (H-P2-01/H-P2-03)
Workflow run metadata:
1. Run ID: `21760827869`
2. URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/21760827869`
3. Event: `push`
4. Branch: `main`
5. Head SHA: `ac1405bf82788636df430078bc9a983027c40abe`
6. Created (UTC): `2026-02-06T18:07:08Z`

P2 job execution:
1. Job name: `B0.7 P2 Runtime Proof (LLM + Redaction)`
2. Job ID: `62783711300`
3. Conclusion: `success`
4. Passed steps:
   - `Run B0.7 P2 provider enablement unit gate`
   - `Run B0.7 P2 runtime chain proof`
   - `Verify B0.7 P2 artifact and log redaction hygiene`
   - `Upload B0.7 P2 artifacts`

Note: overall workflow conclusion was `failure` due unrelated job `Phase Gates (B0.6)`. B0.7-P2 required job passed.

## Artifact Proof (H-P2-04/H-P2-06)
Artifact metadata:
1. Name: `b07-p2-runtime-proof`
2. Artifact ID: `5410089070`
3. Size: `2586` bytes
4. Digest: `sha256:7818b4013d00b14521d77273f6aa2c4058480c30b0aeb7a1c3554ee38a014e96`
5. Created (UTC): `2026-02-06T18:08:34Z`
6. Expires (UTC): `2026-02-20T18:08:34Z`

Artifact manifest (`.tmp_ci_artifacts_push_proof_21760827869`):
1. `pytest.log` (686 bytes, sha256 `9195484f47e5da94aac3baf6a8dd06ed8059c8209c6162926495ed1df3a9c310`)
2. `worker.log` (6277 bytes, sha256 `33f38600adac30954226d4402d0702ad2024327bc7c9f679b458cfff85c19314`)
3. `runtime_db_probe.json` (244 bytes, sha256 `a7c354795af4978766ec146e240e7b58b307bb90a976198e72ea3891609b78f5`)
4. `redaction_probe.json` (96 bytes, sha256 `ddfd58c31bac23b77e2fdfe9dbf0ad7d65b7b96d6d75569b5ffd81c0d7281431`)

## Runtime Consume Evidence (H-P2-01/H-P2-02)
`runtime_db_probe.json` captured:
1. `tenant_id`: `03a51b13-3bbe-479a-a6e7-735dc2f8537d`
2. `user_id`: `77e8f540-4999-420d-9b92-3d4a5a2c8991`
3. `request_id`: `b07-p2-03a51b13`
4. `endpoint`: `app.tasks.llm.explanation`
5. `provider`: `stub`
6. `distillation_eligible`: `false`

`pytest.log` confirms runtime test executed and passed:
1. `backend/tests/integration/test_b07_p2_runtime_chain_e2e.py::test_b07_p2_runtime_llm_chain_with_redaction PASSED [100%]`

## Fail-Fast Secrets Evidence (H-P2-02/RC-P2-04)
Unit test source:
1. `backend/tests/test_b07_p2_provider_enablement.py` now contains both cases.

CI log proof from P2 provider step:
1. `LLM_PROVIDER_API_KEY:` is empty in step environment.
2. `test_provider_enabled_requires_api_key PASSED`
3. `test_provider_disabled_without_api_key_is_allowed PASSED`
4. `2 passed in 0.23s`

## No-Leak Redaction Evidence (H-P2-04/RC-P2-05)
Artifact probe output (`redaction_probe.json`):
1. `canary_present: false`
2. `redacted_key_present: true`
3. `redacted_bearer_present: true`

Worker log positive controls:
1. `LLM_PROVIDER_API_KEY=***`
2. `Authorization: Bearer ***`
3. `llm_explanation_stubbed`

CI log proof of deterministic scanner:
1. Step `Verify B0.7 P2 artifact and log redaction hygiene` passed.
2. Output: `B0.7 P2 redaction hygiene scan passed`
3. Scan is fail-fast on canary and non-redacted patterns.

## Governance Enforcement (RC-P2-03)
Branch protection was absent before remediation (`main` returned `Branch not protected`).

Applied protection on `main` (admin token):
1. `required_status_checks.strict = true`
2. Required check: `B0.7 P2 Runtime Proof (LLM + Redaction)`
3. `enforce_admins.enabled = true`
4. Verified via `GET /repos/Muk223/skeldir-2.0/branches/main/protection`

## Exit Gates
1. EG-P2-1 Continuous Mainline Governance Gate: PASS
   - Push-triggered run on `main` (`21760827869`) executed P2 job automatically and passed.
   - Branch protection now requires P2 check on `main`.
2. EG-P2-2 Runtime Consume Gate: PASS
   - Runtime integration test passed and `runtime_db_probe.json` shows consumed task write row.
3. EG-P2-3 No-Leak Redaction Gate: PASS
   - Canary absent; redaction markers present; CI artifact/log scanner passed.
4. EG-P2-4 Fail-Fast Secrets Gate: PASS
   - Enabled-without-key fails and disabled-without-key passes in CI with blank key env.
5. EG-P2-5 Artifact Audit Gate: PASS
   - Artifact uploaded with ID/digest, required 4-file manifest present, scanner pass logged.

## Residual Note
This evidence package proves B0.7-P2 controls on `main` for run `21760827869`. It does not claim global CI health beyond this scope.
