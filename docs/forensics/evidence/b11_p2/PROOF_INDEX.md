# B1.1-P2 Proof Index

## Exit Gate 1 - Single Choke Point Enforced (Static)
- Static scan artifact: `docs/forensics/evidence/b11_p2/chokepoint_callsite_scan.txt`
- Non-vacuous bypass guard log: `docs/forensics/evidence/b11_p2/ci_non_vacuous_bypass_test_log.txt`
- CI context: `b11-p2-secret-chokepoint-gate` (workflow: `b11-p2-secret-readiness-adjudication`)

## Exit Gate 2 - Boot/Readiness Hard-Fail Proven (Runtime)
- Missing JWT readiness probe: `docs/forensics/evidence/b11_p2/runtime_probe_ready_missing_jwt.txt`
- Missing secret negative-control log: `docs/forensics/evidence/b11_p2/ci_non_vacuous_missing_secret_test_log.txt`
- CI context: `b11-p2-readiness-gate` (workflow: `b11-p2-secret-readiness-adjudication`)

## Exit Gate 3 - Worker + API Topology Coverage
- API proof under missing JWT: `docs/forensics/evidence/b11_p2/runtime_probe_ready_missing_jwt.txt`
- Worker proof under missing DB secret: `docs/forensics/evidence/b11_p2/runtime_probe_worker_startup_missing_db.txt`

## Exit Gate 4 - Non-Vacuous CI Adjudication
- Bypass canary failure proof: `docs/forensics/evidence/b11_p2/ci_non_vacuous_bypass_test_log.txt`
- Missing-secret canary failure proof: `docs/forensics/evidence/b11_p2/ci_non_vacuous_missing_secret_test_log.txt`
- Required-check contract: `contracts-internal/governance/b03_phase2_required_status_checks.main.json`

## Exit Gate 5 - Evidence Pack Published
- This index: `docs/forensics/evidence/b11_p2/PROOF_INDEX.md`
- Required artifacts are present in `docs/forensics/evidence/b11_p2/`.
