# B11_P6 Findings And Remediations

Date: 2026-02-25
Phase: B1.1-P6 End-to-End Integration Testing & Operational Readiness Closure Pack
Branch: main
Status: PASS

## Hypothesis Adjudication (Current Request)

| Hypothesis | Verdict | Empirical Evidence |
|---|---|---|
| H01: P6 S3 block resolved (`skeldir-ci-deploy` has required write) | TRUE | IAM simulation for `arn:aws:iam::326730685463:role/skeldir-ci-deploy` on `s3:PutObject` to `arn:aws:s3:::skeldir-b11-p1-tfstate-326730685463-us-east-2/security/b11_p6/...` returned `Decision=allowed`, `Boundary=true`. Authoritative run `22408597678` passed durable publication. |
| H02: backend-agent has self-service remediation access via runbook workflow | TRUE | Caller identity resolved to `arn:aws:iam::326730685463:user/skeldir-backend-agent`. Simulations returned `allowed` for `iam:PutRolePolicy`, `iam:CreatePolicyVersion`, `iam:SetDefaultPolicyVersion`, `iam:DeletePolicyVersion`, `lambda:InvokeFunction`, and `cloudtrail:LookupEvents`. |

## Authoritative CI Runs (main)

- Run 1: `22408375127` (workflow_dispatch, `refs/heads/main`) -> SUCCESS
- Run 2: `22408597678` (workflow_dispatch, `refs/heads/main`) -> SUCCESS
- Commit under adjudication: `9e524c6c9576511ef478f7f6e79a56889712fc6c`

Determinism validation:
- `manifest_digest` from run `22408375127`: `8860e5c129023a49e6634dea9ebd8b53b4573c1b5f25be473b8e6d8117c320b2`
- `manifest_digest` from run `22408597678`: `8860e5c129023a49e6634dea9ebd8b53b4573c1b5f25be473b8e6d8117c320b2`
- Result: deterministic canonical manifest digest confirmed across two consecutive `main` runs.

## Durable Evidence Chain

From authoritative run `22408597678`:
- GitHub artifact id: `5658594089`
- GitHub artifact digest: `sha256:1568efd5ae61c27ac06f7bdc5c8de08ab6fa79e6d94e2c195511beb7344cd5ed`
- Durable S3 bundle URI: `s3://skeldir-b11-p1-tfstate-326730685463-us-east-2/security/b11_p6/9e524c6c9576511ef478f7f6e79a56889712fc6c/run-22408597678/b11-p6-closure-pack-evidence.zip`
- S3 version id: `si5Mqqw2hcs8p9jvCJUL5lGXwEsL08w6`
- Zip sha256 (`sha256SUMS.txt`): `18c2a9b338ed25e5c1505db0bb0696c8c4dcb3a63dd2136ff1f768b9ebb1d3cd`
- Manifest digest: `8860e5c129023a49e6634dea9ebd8b53b4573c1b5f25be473b8e6d8117c320b2`

Independent verifier execution:
- `python scripts/security/verify_b11_p6_evidence.py --evidence-dir docs/forensics/evidence/b11_p6`
- Result: `b11_p6_evidence_verification=PASS`

## Exit Gate Closure

- Gate 6.1 Rotation drill: PASS
  - `rotation_drill_jwt_envelope.txt` sha256 `c35b3d4304efa56dc208afb63594feb783f6646fa2435c95c7fe0d179bb8a35d`
- Gate 6.2 No-secrets-anywhere: PASS
  - `no_secrets_repo_scan.json` sha256 `1aca7532bf2b4ed24b6f7867c358e754864adf22f41126e120339638191917a7`
  - `workflow_plaintext_scan.txt` sha256 `f8e18b7b9fe4553f38a27581ecb5788610904c9fb36720c824cffdc3e0f40de4`
  - `db_no_plaintext_webhook_secrets.txt` sha256 `0d99819e0af7bfa246d36c16ff0d6a56e0c0bfde3d19e90f5b92d4a6f7ab8593`
- Gate 6.3 Readiness fail-closed: PASS
  - `readiness_fail_closed_test.txt` sha256 `1172dc4ba68f320a52f9364c9780bf9b3c93f5638eb2486a32f1845aa42e860b`
- Gate 6.4 CI audited retrieval + stage run-causal tether: PASS
  - `ci_oidc_assume_role_log.txt` sha256 `0c43285b8fa67ee0d4dc7d45fefa589174f7b37f6e2b76444e9319761e2ee29b`
  - `cloudtrail_ci_reads.txt` sha256 `fa0e2e1090fc105ac056e509dbd2d1571f72f736d56a854208d084c58e607acb`
  - `cloudtrail_stage_run_causal.txt` sha256 `2d1de10b0e034215ab465b4773f152e625fb8229a2543ad0601fa7fa7364540e`
- Gate 6.5 Webhook E2E + no plaintext at rest: PASS
  - `webhook_e2e_valid_invalid.txt` sha256 `f4ccda5031f7f12c3689c06bf10a4e1b42df18c607e23e8db685903fdf392584`
- Gate 6.6 Redaction integrity: PASS
  - `log_redaction_integrity.txt` sha256 `cd51168d995ceb92012457e42d489d05f022c36e2e7382d2fd61ddd5c937105c`
- Gate 6.7 Evidence pack + proof index: PASS
  - `PROOF_INDEX.md`, `MANIFEST.json`, `sha256SUMS.txt`, `evidence_bundle_pointer.txt` now populated with immutable mapping and digests.

## Conclusion

B1.1-P6 corrective action is complete and empirically closed for commit `9e524c6c9576511ef478f7f6e79a56889712fc6c` with two consecutive green `main` runs and durable, independently verifiable evidence.
