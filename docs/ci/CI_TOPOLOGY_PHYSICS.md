# CI Topology Physics

**Audience:** any agent or engineer who adds a workflow, adds a phase, or changes `.github/workflows/`.
**Enforced by:** `.github/workflows/ci-physics-guard.yml` → `scripts/ci/validate_ci_physics.py`
**Non-vacuity:** `scripts/ci/test_ci_physics_negative_controls.py` (9 controls)

If you only read one section, read [§5 Adding a phase](#5-adding-a-phase).

---

## 1. The constraint you are working inside

This repository runs on GitHub Actions on the **Free plan**, which caps the
organisation at **20 concurrent jobs**. That number was confirmed by measurement,
not assumed: sweeping 432 job intervals across three pushes, peak concurrency
touches 20 exactly and never exceeds it.

A representative PR fires **47 workflows and ~153 jobs**. Their total execution
is **~290 CPU-minutes**. Against 20 slots that gives a hard floor:

```
290 CPU-min ÷ 20 slots = 14.5 min      ← capacity floor
longest single job      = 14.0 min      ← critical-path floor (Phase Chain B0.4)
```

**Every CPU-minute you add is charged against a shared 20-slot budget.** This is
the single fact that explains every rule below. A job that wastes 60 seconds on
an uncached `pip install` is not wasting its own time; it is holding a slot that
another phase's gate is queued behind.

## 2. What went wrong before, and what it cost

Measured on PR #649 (156 checks, all green): **58.2 minutes wall clock against a
14.5-minute floor — a 4× inflation, 53% of it spent waiting.** Jobs spent
**12× longer queued than executing** (p50 queue 22.2 min, p50 execution 1.25 min).

Cost was also **invariant to change size**. Across nine merged PRs, change size
varied 2,191× (1 line to 2,191 lines) while check count varied 1.11× (145 to 161).
A one-line documentation edit paid the same toll as a forty-file schema rewrite.

Four mechanisms, three of them pure waste:

| Mechanism | Cost | Cause |
|---|---:|---|
| Zombie runs from abandoned commits | 14.7 min | 60 of 62 workflows had no `concurrency:` block |
| Dependency edges transferring no data | 14.3 min | `checkout` gated 66 jobs, `validate-contracts` gated 42 |
| Serial phase chain | 14.0 min | **Real work.** The honest floor. |
| Uncached toolchain setup | 125 CPU-min | 191 toolchain setups, 5 cache keys |

The second one is the subtle one and the reason rule 4 exists. `checkout` ran
`actions/checkout`, asserted two invariants, then **discarded everything** — it
uploaded no artifact and declared no outputs, and all 69 jobs checked the
repository out again for themselves. `ci.yml` contained **zero
`download-artifact` calls**. Those 103 edges carried no bytes. They were a
fail-fast ordering hint, and under a hard concurrency cap an ordering hint
becomes a serialisation barrier: it split a flat parallel workload into three
tiers, and each tier boundary cost a full dispatch round trip. The measured
result was **11.1 minutes during which the entire account had zero jobs running
while work sat queued.**

## 3. The topology now

```
before                                  after
──────                                  ─────
tier 0:  2 jobs   (checkout)            tier 0:  57 jobs
tier 1: 21 jobs                         tier 1:   8 jobs
tier 2: 40 jobs   (behind validate-)    tier 2:   4 jobs
tier 3:  5 jobs
tier 4:  1 job

max fan-in: 66 dependents               max fan-in: 3 dependents
```

`checkout` and `validate-contracts` **still exist and are still required status
checks**. Only the ordering constraint was removed. The three jobs that
genuinely read `needs.<job>.result` kept their edges.

Nothing was removed, skipped, or made optional. All 73 required contexts remain
required, and the merge queue now runs them against the exact merge commit —
which is *stronger* than what came before (see §4).

## 4. The four rules

Each is a structural property of the YAML. None enumerates a path, a module, or
a test name, so a new phase inherits all of them by existing.

### Rule 1 — concurrency

Every workflow with a `pull_request` trigger carries:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.run_id }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

**Why the group falls back to `run_id`, not `github.ref`.** On a PR event the
group is per-workflow-per-PR, so a new push supersedes the previous run. On
`push` and `merge_group`, `run_id` is unique per run — so those runs are never
cancelled *and never queued behind each other*. Using `github.ref` there would
put every push to `main` into one group and serialise them.

**Why `cancel-in-progress` is an expression, not `true`.** An unconditional
`true` can cancel a `push` or `merge_group` run mid-proof. The guard rejects it.
This is not hypothetical: `b07-phase8-full-physics-staging.yml` shipped with
unconditional cancellation and could have killed a main-branch audit run. The
guard caught it on its first execution.

**Safety argument.** A run is cancelled only when a newer commit has already
replaced the one it was testing — a result that by definition can never gate a
merge. The proof on an exact SHA always runs to completion.

### Rule 2 — merge_group

Every workflow with a `pull_request` trigger also declares `merge_group:`.

Without it, the merge queue would not run that workflow against the merge
commit, and a required context would never report — blocking the queue forever.

**This closes a real audit gap.** Previously `main` was protected with 73
required contexts and `strict: true`, and PRs landed as merge commits. Required
contexts are evaluated against **the head SHA of the PR branch**; the merge
commit is created *at merge time* and was tested by nothing. The exact SHA
landing on `protected/main` had no regression matrix attached to it. `strict:
true` guaranteed only that the branch was up to date at some point — a weaker
property than the audit contract requires. The merge queue validates the
**speculative merge commit itself**, which is the object that becomes `main`.

### Rule 3 — cache

Every `actions/setup-python` carries `cache: 'pip'`; every `actions/setup-node`
carries `cache: 'npm'`. Cache keys are derived from lockfile hashes by the
official actions, so a changed lockfile is a cache miss and no assertion changes.

40% of all CPU was setup. Because CPU meets the cap, that waste converted
directly into queue time for every other phase.

### Rule 4 — fanout

**No job may be depended on by more than 5 jobs unless it actually transfers
data** — either it declares `outputs:`, or it uploads an artifact that a
downstream job downloads.

This is the rule that prevents the pathology from coming back. It is tempting to
write `needs: [my-gate]` on thirty jobs so they "run after the gate passes". Under
a 20-slot cap that does not save runner minutes on the happy path; it costs a
dispatch round trip on *every* path, for every PR, forever.

**If you want fail-fast, use a required status check, not a `needs:` edge.** A
required check blocks the merge, which is what you actually wanted. A `needs:`
edge blocks the *schedule*, which is not.

## 5. Adding a phase

Copy an existing phase workflow and edit the name, triggers, and steps. Then:

```bash
python scripts/ci/validate_ci_physics.py --verbose
```

If it passes, you are done — **there is no registry to update.** The guard
discovers workflows by glob, so your new workflow is enforced the moment it
exists. This is verified by a negative control: the harness builds a synthetic
B3 phase workflow and confirms the guard rejects it for missing a concurrency
block, with no edit to the guard or the harness.

Then register the new phase's required contexts on branch protection as usual.

### If a rule genuinely does not apply

Put the exemption **in the workflow it applies to**:

```yaml
# physics-exempt: concurrency - R0 determinism requires every run to complete
```

Valid rules: `concurrency`, `merge_group`, `cache`, `fanout`. The exemption lives
in the file, so it is visible in review and travels with the workflow. **There is
deliberately no central exemption list** — a central list rots, drifts out of
sync with reality, and becomes a liability nobody dares delete from.

One exemption exists today: `r0-preflight-validation.yml` uses
`cancel-in-progress: false` because R0 runs must never be cancelled for
determinism. That was already correct and was left untouched.

## 6. Expected throughput

Measured against the observed 58.2-minute baseline:

| Scenario | Before | After |
|---|---:|---:|
| Hotfix (1 file, +6 lines) | 26 min | ~12 min |
| Large PR (24 files) | 78 min | ~28 min |
| 4-PR convoy (observed, PRs #645–648) | 174 min | ~33 min |
| 6-PR phase | 397 min | ~37 min |

The shape matters more than the numbers. Under `strict: true` with no queue,
every merge invalidated every other open PR, forcing a rebase and a complete
153-job re-run — **cost grew linearly in concurrent PRs**. With a merge queue,
speculative merge commits are validated in batches and **cost grows
sub-linearly**. That is the property future phases depend on.

## 7. What was deliberately not done

- **Path filters.** Skipping the schema suite when no `.sql` changed is the
  obvious answer and the one that rots: every new module needs a filter entry,
  every missed entry is a silent hole in the trust chain, and the failure mode is
  invisible until an auditor finds it. The P13 workflow header already documents
  this defect being found in P12 and again across P8–P11.
- **Splitting `ci.yml`.** Its 69 jobs already run concurrently; splitting
  redistributes the same CPU against the same cap and returns zero minutes. The
  file's size is a maintainability problem, not a throughput one.
- **Sharding the phase chain.** It is 11.4 minutes of sequential verification
  against a live database. Sharding it would assert that its phases are
  independent, which is the one thing a phase chain exists to deny.
- **Any test removal, skip, or quarantine.** Nothing was removed, skipped, or
  made optional.

## 8. Reproducing the measurements

```bash
# concurrency ceiling: sweep job intervals for max overlap
gh api "repos/Synergyscape-V1/skeldir-2.0/actions/runs?branch=BRANCH&per_page=100" --paginate

# per-PR check timing
gh api "repos/Synergyscape-V1/skeldir-2.0/commits/SHA/check-runs?per_page=100" --paginate

# branch protection posture
gh api repos/Synergyscape-V1/skeldir-2.0/branches/main/protection \
  -q '.required_status_checks | {strict, count: (.contexts|length)}'

# the guard, and the proof it is non-vacuous
python scripts/ci/validate_ci_physics.py --verbose
python scripts/ci/test_ci_physics_negative_controls.py
```

Full analysis, including the job-level timing tables and the discrete-event
simulation, is in `docs/ci/CI_THROUGHPUT_PHYSICS_ANALYSIS.md`.
