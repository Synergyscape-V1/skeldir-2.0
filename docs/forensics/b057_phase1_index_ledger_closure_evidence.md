# B0.5.7-P1 - INDEX Ledger Closure Evidence

Objective: resolve the adjudicated P1 blocker by proving the forensics ledger (`docs/forensics/INDEX.md`) is an auditable root of truth for B0.5.7-P1 evidence packs, with CI run links bound to a specific PR head SHA.

PR: https://github.com/Muk223/skeldir-2.0/pull/24

---

## Ground truth (PR head at investigation start)

Commands:

```powershell
git rev-parse HEAD
git status --porcelain=v1
```

Output:

```text
4634611c4d8111f35224662439b88dcd9c52785b
# git status --porcelain=v1: (no output; working tree clean)
```

Note: this evidence pack is committed after the ledger update, but the anchor SHA above is the PR head used for CI/run binding evidence in this pack.

---

## Hypotheses (BLOCK-INDEX) adjudication

- H-BLOCK-INDEX-1 (P1 evidence packs exist but are not indexed): FALSE (evidence packs exist and INDEX contains rows; see excerpts below).
- H-BLOCK-INDEX-2 (wrong INDEX file edited / stale ledger): TRUE (INDEX rows existed but were stale to a prior SHA/CI run; remediated by updating the two B0.5.7-P1 rows to bind to the PR head SHA above and its green CI runs).
- H-BLOCK-INDEX-3 (INDEX schema mismatch prevents ledgering): FALSE (same 5-column schema; only row values updated; table renders).
- H-BLOCK-INDEX-4 (CI links exist but not bound to INDEX): TRUE prior to remediation; FALSE after remediation (INDEX now includes CI runs bound to the PR head SHA).

---

## Evidence packs existence (repo truth)

Commands:

```powershell
Test-Path docs/forensics/b057_phase1_canonical_e2e_bringup_remediation_evidence.md
Test-Path docs/forensics/b057_phase1_ci_topology_validation_closure_evidence.md
(Get-Item docs/forensics/b057_phase1_canonical_e2e_bringup_remediation_evidence.md).Length
(Get-Item docs/forensics/b057_phase1_ci_topology_validation_closure_evidence.md).Length
```

Output:

```text
True
True
10665
5462
```

---

## CI binding (run URLs are for the PR head SHA)

Commands:

```powershell
gh run view 21190374590 --json headSha,conclusion,workflowName,url
gh run view 21190374599 --json headSha,conclusion,workflowName,url
gh run view 21190374609 --json headSha,conclusion,workflowName,url
```

Output:

```json
{"conclusion":"success","headSha":"4634611c4d8111f35224662439b88dcd9c52785b","url":"https://github.com/Muk223/skeldir-2.0/actions/runs/21190374590","workflowName":"B0.5.7-P1 — Compose E2E Topology (Canonical)"}
{"conclusion":"success","headSha":"4634611c4d8111f35224662439b88dcd9c52785b","url":"https://github.com/Muk223/skeldir-2.0/actions/runs/21190374599","workflowName":"CI"}
{"conclusion":"success","headSha":"4634611c4d8111f35224662439b88dcd9c52785b","url":"https://github.com/Muk223/skeldir-2.0/actions/runs/21190374609","workflowName":"Empirical Validation - Directive Compliance"}
```

---

## INDEX before/after excerpts (no truncation)

### Before (as of PR head `4634611c4d8111f35224662439b88dcd9c52785b`, prior to this remediation)

`docs/forensics/INDEX.md` rows:

```text
| B0.5.7 Phase 1 | docs/forensics/b057_phase1_canonical_e2e_bringup_remediation_evidence.md | Canonical E2E bring-up: repo-native one-command topology (db+api+worker+exporter) + truthful scrape targets + local regression proof | PR #24 / 3354d14 | https://github.com/Muk223/skeldir-2.0/actions/runs/21189960721 |
| B0.5.7 Phase 1 CI closure | docs/forensics/b057_phase1_ci_topology_validation_closure_evidence.md | CI proof that `docker-compose.e2e.yml` boots and anti split-brain assertions executed; plus governance gate closures | PR #24 / 3354d14 | https://github.com/Muk223/skeldir-2.0/actions/runs/21189960732 |
```

### After (this remediation)

`docs/forensics/INDEX.md` rows:

```text
| B0.5.7 Phase 1 | docs/forensics/b057_phase1_canonical_e2e_bringup_remediation_evidence.md | Canonical E2E bring-up: repo-native one-command topology (db+api+worker+exporter) + truthful scrape targets + local regression proof | PR #24 / 4634611 | compose: https://github.com/Muk223/skeldir-2.0/actions/runs/21190374590 ; main: https://github.com/Muk223/skeldir-2.0/actions/runs/21190374599 |
| B0.5.7 Phase 1 CI closure | docs/forensics/b057_phase1_ci_topology_validation_closure_evidence.md | CI proof that `docker-compose.e2e.yml` boots and anti split-brain assertions executed; plus governance gate closures | PR #24 / 4634611 | compose: https://github.com/Muk223/skeldir-2.0/actions/runs/21190374590 ; empirical: https://github.com/Muk223/skeldir-2.0/actions/runs/21190374609 |
```

---

## Closure checklist (EG-P1-L*)

- EG-P1-L1 (ledger presence): PASS (INDEX contains the two B0.5.7-P1 rows with correct evidence pack paths).
- EG-P1-L2 (CI-link binding): PASS (each referenced CI run shows `headSha == 4634611c4d8111f35224662439b88dcd9c52785b`).
- EG-P1-L3 (table integrity): PASS (no schema changes; 5-column table; rows are pipe-aligned).
- EG-P1-L4 (governance validators): Verified via CI for the PR head SHA above; see runs linked in INDEX rows and CI binding output.
- EG-P1-L5 (functional non-regression): Verified via compose topology workflow run above (includes anti split-brain assertions in job logs).
- EG-P1-L6 (commit/push): satisfied by this remediation commit (see git history).
