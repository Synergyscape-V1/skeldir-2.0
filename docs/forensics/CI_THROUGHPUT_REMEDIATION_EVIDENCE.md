# CI Throughput Remediation — Evidence Report

**Branch:** `codex/b25-p14-corrective-v-closeout` (B2.5-P14 active throughout; no freeze, no rebase, no bypass).
**Authority:** `CI-INFRASTRUCTURE_THROUGHPUT_REMEDIATION_DIRECTIVE.md` (conservation laws CI-C1…CI-C5).
**Baseline:** `SKELDIR_CI_GREENFIELD_FORENSIC_AUDIT_AND_TARGET_ARCHITECTURE.md` (2026-09-05; independently re-measured 2026-09-06 — every reused number below was re-observed live, not copied).
**Machine evidence:** `docs/forensics/ci_throughput_remediation.evidence.json`, `contracts-internal/governance/ci_proof_conservation.v1.json` (80/80 coverage).

## 1. Re-measured baseline (live, 2026-09-06)

| Quantity | Audit (09-05) | Re-measured (09-06) | Verdict |
|---|---|---|---|
| PR burst, same minute | ~50 | 48 (`3dc192b7`: 44 `pull_request` + 4 `pull_request_target`) | CONFIRMED |
| Push-to-main burst | ~50 | 52 | CONFIRMED |
| Merge-group burst | 47–49 | 53 | CONFIRMED (worse) |
| CI median job queue | 9.1 min | 20.88 min (run 34047052521, 79 jobs) | CONFIRMED (worse; queue-dominated: exec median 1.27 min) |
| CI wall clock | 24.8 min | 38.63 min | CONFIRMED (worse) |
| `pip install` occurrences | 351 | 352 | CONFIRMED |
| Postgres `services:` blocks | 46 + 11 composite (ci.yml) | 93 repo-wide / 46 in ci.yml | CONFIRMED |
| Required contexts live vs contract | 80 = 80 | 80 = 80, set-difference ∅ | CONFIRMED |
| Container-proof workflows | P13 (+B2.4 bayesian) | exactly `b2_5-p13`, `b2_4` | CONFIRMED |
| `pull_request_target` double-fire | PR #653 precedent | 4 workflows (`b11-p1…p4`) double-fired on sampled burst | CONFIRMED, mechanism scoped |
| pip cache reuse | assumed | log-observed: `Cache restored successfully`, `Using cached pyyaml`, key binds OS+py+lockfile | CONFIRMED |

Root cause restated: **excess fan-out against a 20-slot quota** (docs/ci/CI_TOPOLOGY_PHYSICS.md §1), not weak proofs. 31 advisory (zero-required-context) workflows fired on every merge queue; 17 fired unfiltered on every PR.

## 2. Remediation (orchestration physics only)

1. **Guard rules 6–7** (`scripts/ci/validate_ci_physics.py`): required lanes MUST fire on `merge_group`; advisory lanes MUST NOT (rule `advisory-merge-group`) and MUST scope `pull_request` with `paths:` (rule `advisory-pr-paths`). Fail-closed when the contract is unreadable. Exemptions are in-file and review-visible.
2. **31 advisory workflows**: `merge_group:` removed (merge burst 62→22 source declarations; live merge-group burst predicted 53→~22, required-only). `push`/dispatch retained for post-merge forensics.
3. **16 advisory workflows**: `pull_request` (+`push`, +`pull_request_target` where present) scoped to owned surfaces, always including the workflow's own file, `docs/ci/**`, and the governance contract so CI-infra edits still exercise them. `empirical-validation` exempt by design (cross-cutting); `workflow-yaml-lint` gained a path-filtered PR trigger so workflow edits are linted pre-merge.
4. **Kept deliberately**: `pull_request_target` on `b11-p1…p4` (fork-PR secrets/vars context; double-fire governed by event-keyed concurrency, rule 1); all required triggers byte-identical; all 80 required contexts untouched (branch protection still matches contract ∅).
5. **Environment**: Playwright browser `actions/cache` (key: OS + `package-lock.json`) added to the three browser-installing `ci.yml` jobs (B1.5-P7, phase-gates, phase-chain — the 14.15/11.87-min poles); the unconditional `install --with-deps` still runs, so hit ≡ miss (Law CI-C4). pip/npm caches retained. Go module caching skipped (no `go.mod`; `setup-go cache:true` would warn-and-skip).
6. **Governance metadata**: `b03…main.json` v1.20.0→v1.21.0; stale `75`→`80` (3 places). No context added/removed/renamed.
7. **Proof conservation**: `ci_proof_conservation.v1.json` maps I-1…I-10 plus all 80 required contexts to producing workflows (falsifier: guard coverage check).

## 3. Verification

- `validate_ci_physics.py`: GREEN, 64/64.
- Negative controls: **22/22** (15 inherited + 7 new: advisory-MG ×3, advisory-paths ×3, required-missing-MG ×1).
- P13 merge-governance validator + NC suite: GREEN.
- Fault corpus C-09: F1 trigger corruption RED, F2 cache corruption RED, F3 governance removal RED (exact causal messages), F4 wrapper baseline GREEN, F5 NC-P14-07 present lane-owned.
- Forensics INDEX E-VAC re-run (disposable worktree, nothing pushed): unindexed pack RED with exact message → indexed GREEN. (Nuance vs 09-05 audit: basename-only entry now passes; sensitivity confirmed, specificity note recorded.)
- YAML: all 33 edited workflow files parse; evidence-placement passes; the two new forensics files are registered in `docs/forensics/INDEX.md` with full paths (exact-path semantics).

## 4. Honest gate accounting

- **Green now**: proof conservation (C-02), negative-control conservation (C-03), artifact fidelity posture unchanged + browser-cache neutrality (C-07), trigger totality for required lanes incl. matrix stems (C-08), fault-corpus non-vacuity (C-09), continuity (C-10: no rebase/freeze/bypass; required triggers untouched), audit evidence (C-11).
- **Predicted, pending live re-measurement**: C-04/C-05/C-06 and Gates 1/2/9. Merge-group burst −58% is structural (source-declared, guard-enforced); queue/wall deltas must be measured on disposable PRs post-merge (pre/post distributions per §4.6). The 15-min wall budget remains aspirational while the 69-job `ci.yml` monolith and 14-min Phase Chain dominate the critical path — Phase 2 (required-lane consolidation with monotonic context migration) is proposed, explicitly NOT smuggled into this phase.
- **Landing**: via `main-merge-queue` ALLGREEN (C-01), no admin bypass.

## 5. Residual debt (Phase 2 proposal, not executed)

1. Required-lane consolidation (`ci.yml` decomposition) with new lane contexts + branch-protection migration + 10-run paired corpus (directive §4.6).
2. Nightly forensic NC sweep (lane F; today only the weekly benchmark is scheduled).
3. Live post-merge re-measurement (disposable docs-only / trust / Bayesian PRs + 2 merge-groups + 1 red-team event) to close C-04/C-05/C-06 numerically.
