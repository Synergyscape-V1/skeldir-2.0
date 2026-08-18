# CI Throughput Physics — Global Topology Analysis

**Repository:** `Synergyscape-V1/skeldir-2.0`
**Date of measurement:** 18 August 2026
**Mode:** Read-only shadow analysis. No branch, PR, or workflow modified.
**Scope:** PRs #639–#650; all 62 workflow files; branch protection on `main`.

---

## 0. Executive Summary

**The Global Conjecture is VALIDATED as to its claim, and CORRECTED as to its cause.**

| Claim | Finding |
|---|---|
| The bottleneck is systemic | **True.** Proven by cost-invariance to change size. |
| It degrades with future phase complexity | **True, and worse than stated** — it degrades with *PR concurrency*, not phase size, and the growth is linear. |
| The cause is the monolithic test matrix | **False.** The matrix is not the problem. Three of the four cost mechanisms are pure waste unrelated to test count. |
| ≥70% reduction is achievable | **Split verdict.** 64% for an isolated PR (honest ceiling). 81–91% for the multi-PR convoys that dominate real delivery. |

The single highest-leverage change is **dissolving ~105 dependency edges that transfer no data**. The single most important change for the roadmap is **adopting a merge queue**, which also closes an audit gap that exists today.

---

## 1. Methodology

All figures are derived from the GitHub Actions REST API, not from reading YAML.

| Data source | Endpoint | Volume |
|---|---|---|
| Check-run timing | `/commits/{sha}/check-runs` | 10 PRs, 1,520 check records |
| Workflow-run metadata | `/actions/runs?head_sha=` | 47 runs (PR #649) |
| Job + step timing | `/actions/runs/{id}/jobs` | 153 jobs, 1,578 steps (PR #649) |
| Branch-wide job sweep | `/actions/runs?branch=` | 142 runs, 432 job intervals |
| Branch protection | `/branches/main/protection` | 73 required contexts |
| DAG structure | Static parse of `ci.yml` | 69 jobs, 5,848 lines |

**Definitions used throughout:**

- **Wall clock** — first workflow-run `created_at` to last job `completed_at` on a single head SHA.
- **CPU-minutes** — sum of `completed_at − started_at` across all jobs. This is the quantity that meets the runner cap.
- **Queue delay** — `job.started_at − run.created_at`.
- **Slot-minutes** — CPU-minutes weighted against the 20-slot concurrency ceiling.

**Reproduction commands are in Appendix C.**

---

## 2. Validation of the Conjecture

### 2.1 The delay is systemic, not database-specific

The decisive test is whether CI cost tracks change size. It does not.

| PR | Files | Lines added | Checks run | Lead time |
|---:|---:|---:|---:|---:|
| 644 | 1 | 1 | 151 | 32 min |
| 646 | 1 | 6 | 145 | 26 min |
| 647 | 1 | 49 | 145 | 24 min |
| 643 | 1 | 245 | 151 | 19 min |
| 641 | 2 | 44 | 151 | 198 min |
| 648 | 2 | 368 | 151 | 42 min |
| 649 | 24 | 1,632 | 156 | 78 min |
| 645 | 38 | 1,900 | 161 | 67 min |
| 642 | 40 | 2,191 | 159 | 45 min |

- Change size range: **1 → 2,191 lines = 2,191× variation**
- Check count range: **145 → 161 = 1.11× variation**

PR #646 changed one file by six lines and paid 145 checks. PR #642 changed 2,191 lines and paid 159. **Cost is invariant to change size.** That is the formal definition of a structural bottleneck, and it disproves the "heavy database changes only" hypothesis outright.

### 2.2 The magnitude of the inflation

Measured on PR #649 (the largest recent remediation, 24 files, all checks green):

| Quantity | Value |
|---|---|
| Wall clock | **58.2 min** |
| Total CPU | 290 min across 153 jobs |
| Longest single job | 14.0 min (`Phase Chain (B0.4 target)`) |
| Theoretical floor at 20 slots | 14.5 min |
| **Observed inflation** | **4.0×** |
| Wall spent with zero jobs running | 11.1 min |
| Wall spent waiting overall | 30.6 min (**53%**) |

Queue-delay distribution across all 153 jobs:

| Percentile | Queue delay | Execution time |
|---|---:|---:|
| min | 0.02 min | 0.15 min |
| p50 | **22.23 min** | 1.25 min |
| p90 | **50.10 min** | 4.97 min |
| max | 53.90 min | 14.02 min |
| **sum** | **3,479 min** | **290 min** |

Jobs spend **12× longer queued than executing.** This alone falsifies "the matrix is too big" as the explanation — the tests are fast. The p50 job runs in 75 seconds.

Job duration histogram (PR #649):

```
  0.0 – 0.5 min :  18  ██████████████████
  0.5 – 1.0 min :  30  ██████████████████████████████
  1.0 – 2.0 min :  58  ██████████████████████████████████████████████████████████
  2.0 – 5.0 min :  34  ██████████████████████████████████
  5.0 –  10 min :  11  ███████████
   10 –  30 min :   4  ████
```

106 of 153 jobs finish inside two minutes.

---

## 3. Isolating the Physics

The directive asks which of four candidate causes is responsible: job count, dependency graph, concurrency policy, or runner provisioning. The answer is **all except job count**, in measurable proportion.

### 3.1 The concurrency ceiling is real and binding

Sweeping 432 job intervals across all three pushes on the #649 branch:

```
PEAK CONCURRENT JOBS = 20    (touched exactly; never exceeded)
```

The organisation is on the **GitHub Free plan**, whose standard-runner cap is 20 concurrent jobs. This is confirmed empirically, not inferred from the plan name. It sets a hard floor:

```
290 CPU-min ÷ 20 slots = 14.5 min          ← CPU-bound floor
longest single job     = 14.0 min          ← critical-path floor
```

These coincide almost exactly. Any wall clock above ~15 minutes is waste.

### 3.2 The wave structure — and where the dead air is

All 47 workflow runs are created at **t = 0**. Forty-six of them complete by **minute 19.6**. One workflow — `CI` — starts at minute 16.3 and finishes at 58.2. **`CI` alone is the wall clock.**

Concurrency profile (running jobs per minute, PR #649):

```
min  0 ─ 19  ████████████████  peak 15   46 phase-gate workflows
min 20 ─ 22                              ← 2.5 min, ZERO jobs running
min 23 ─ 37  █████████████████ peak 17   CI tier 1
min 38 ─ 46                              ← 8.6 min, ZERO jobs running
min 47 ─ 58  ███████████████████ peak 19  CI tiers 2 and 3
```

**11.1 minutes during which the entire account had zero jobs executing while work sat queued.** A concurrency cap saturates; it does not idle. Idle capacity with pending work means a *barrier*, not a capacity limit.

### 3.3 The `CI` internal tier structure

| Phase | Window | Duration | Content |
|---|---|---:|---|
| `checkout` | 16.3 → 16.5 | 0.2 min | one no-op gate job |
| **dead** | 16.5 → 22.2 | **5.7 min** | dispatch + provision round trip |
| tier 1 | 22.2 → 37.7 | 15.5 min | 30 jobs; ends on the 14-min phase chain |
| **dead** | 37.7 → 46.3 | **8.6 min** | dispatch + provision round trip |
| tier 2 | 46.3 → 51.4 | 5.1 min | `validate-contracts`, VALUE gates |
| tier 3 | 48.5 → 58.2 | 9.7 min | 45-job B1.x fan-out |

Each tier boundary costs a full dispatch-and-provision round trip. There are two of them.

---

## 4. The Four Cost Mechanisms

Only the third is real work.

### 4.1 Zombie runs from abandoned commits — 14.7 min

Three pushes landed on the #649 branch:

| SHA | Runs | Created | Last activity | Span |
|---|---:|---|---|---:|
| `15c0630` | 48 | 17:04:49 | 17:47:55 | 43.1 min |
| `d2274a1` | 47 | 17:07:59 | 17:47:37 | 39.6 min |
| `1c0b64d` (final) | 47 | 17:22:39 | 18:20:52 | 58.2 min |

**60 of 62 workflows declare no `concurrency:` block**, so nothing supersedes anything. Runs still burning slots after the final push:

```
d2274a1  17:08:01 → 17:23:40  (+1.0 min past push)   b07-phase8-full-physics-staging
d2274a1  17:08:01 → 17:47:37  (+25.0 min past push)  CI
15c0630  17:05:11 → 17:47:55  (+25.3 min past push)  CI
```

Two `CI` monoliths belonging to commits the agent had **already abandoned** ran for 25 minutes past the final push, consuming **293.7 slot-minutes across 122 jobs**. At a 20-slot cap that is **14.7 minutes of pure wall-clock delay** charged to a result nobody would ever read.

This is why `CI`'s first job on the live SHA could not start until minute 16.3.

The two workflows that *do* have concurrency blocks:

```yaml
# b07-phase8-full-physics-staging.yml — correct
group: b07-phase8-full-physics-${{ github.event.pull_request.number || github.ref }}
cancel-in-progress: true

# r0-preflight-validation.yml — deliberately opted out
group: r0-${{ github.sha }}
cancel-in-progress: false  # Never cancel R0 runs (determinism requirement)
```

The R0 exemption is correct and must be preserved.

### 4.2 Dependency edges that transfer no data — 14.3 min

**DAG shape of `ci.yml` (69 jobs):**

| Tier | Jobs |
|---|---:|
| 0 | 2 |
| 1 | 21 |
| 2 | 40 |
| 3 | 5 |
| 4 | 1 |

**Fan-in hubs:**

```
66 dependents ← checkout            (Checkout Code)
42 dependents ← validate-contracts  (Validate Contracts)
 3 dependents ← b21-p2-strategy-kernel-session-boundary
 3 dependents ← b21-p4-queue-isolation-performance-lock
```

The `checkout` job in full:

```yaml
checkout:
  name: Checkout Code
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
      with:
        ref: ${{ env.ADJUDICATED_SHA }}
        fetch-depth: 0
    - name: Adjudication SHA check
      run: test "$(git rev-parse HEAD)" = "${{ env.ADJUDICATED_SHA }}"
    - name: Evidence placement check
      run: python3 scripts/check_evidence_placement.py
```

It checks out the repository, asserts two invariants, and **discards everything**. It uploads no artifact and declares no `outputs:`.

**The proof that these edges carry no data:**

| Probe | Result |
|---|---:|
| `download-artifact` calls in `ci.yml` | **0** |
| `upload-artifact` calls | 26 (none consumed in-workflow) |
| `actions/checkout` calls | **69** (one per job) |
| `outputs:` on `validate-contracts` | none |
| textual `needs.*` references | 3 |

All three `needs.*` references are identical in kind — they read `.result` into an environment variable:

```
113:  CHECKOUT_RESULT: ${{ needs.checkout.result }}
114:  VALIDATE_CONTRACTS_RESULT: ${{ needs.validate-contracts.result }}
499:  (same pair)
991:  (same pair)
```

**The DAG encodes no dataflow whatsoever.** It is a fail-fast ordering hint. Under a hard concurrency cap it converts a flat parallel workload into a three-tier serial pipeline, and each boundary costs a dispatch round trip: **5.7 + 8.6 = 14.3 minutes of dead air.**

It also produces a second-order pathology. `validate-contracts` needs only `checkout`, so it belongs in tier 1 and *should* have started around minute 22 with its peers. Instead the 20-slot cap starved it until **minute 46.4** — a 24-minute delay — and the 42 jobs behind it waited with it. A hub gating 61% of the workflow has no scheduling priority over the leaf jobs competing with it.

The header comment on `checkout` reads *"Single git checkout - Schmidt's key requirement."* The intent was sound. The implementation never achieved it: there are 69 checkouts, not one.

### 4.3 The genuinely serial phase chain — 14.0 min (real work)

`Phase Chain (B0.4 target)` spends **11.4 minutes in a single step** walking the phase chain against a live Postgres service container, with ~2.6 min of Python/Node/Go/Playwright setup around it.

This is irreducible sequential work and **the honest floor of any optimisation**. It is why the capacity sweep in §6.2 saturates at 40 runners: past that point, this one job *is* the pipeline.

Top 15 slowest checks on PR #649:

```
 14.02 min  Phase Chain (B0.4 target)
 13.32 min  Phase Gates (B0.4)
 10.65 min  r5-remediation
 10.52 min  Phase 8 Regression Gate (Full Physics)
  8.35 min  B2.5-P11 Export Compatibility
  8.02 min  Phase Gates (B0.6)
  7.28 min  B2.5-P7 Provenance Audit
  6.87 min  B1.5 P7 Technical Closure Harness
  6.68 min  B2.5-P10 Trust API Surface
  6.45 min  b07_phase8_closure_pack
  6.42 min  B2.5-P9 Machine Identity
  6.27 min  B2.5-P8 Signing Verification
  5.78 min  B2.5-P6 Reason Truth Matrix
  5.40 min  Contract Semantic Drift Gate
  5.25 min  Phase Gates (B0.1)
```

### 4.4 Uncached toolchain setup — 125.3 CPU-min

Step-level accounting across all 153 jobs and 1,578 steps:

| Category | Minutes | Share | Steps |
|---|---:|---:|---:|
| Actual work | 181.6 | 58.5% | 961 |
| **Setup** (checkout / deps / toolchain) | **125.3** | **40.4%** | 501 |
| Runner overhead | 3.2 | 1.0% | 617 |

Most expensive aggregate steps:

```
 40.7 min  ×40   Install dependencies
 31.6 min  ×115  Checkout code
 29.5 min  ×85   Initialize containers
 14.4 min  ×11   Run phase gate
 11.4 min  ×1    Run phase chain to B0.4
  6.0 min  ×19   Install backend dependencies
  5.6 min  ×14   Install backend test dependencies
  5.3 min  ×8    Install PostgreSQL client
```

Across all 62 workflows:

| | Count |
|---|---:|
| `actions/setup-python` steps | 155 |
| `actions/setup-node` steps | 36 |
| `cache:` keys declared | **5** |
| `cache:` keys in `ci.yml` | **0** |

Because CPU is the quantity that meets the cap, this waste converts directly into queue time for everyone.

---

## 5. The Structural Risk to B3/B4/B5

This section is the most important in the document. Single-PR latency is the visible symptom; the following is the actual exposure.

### 5.1 Current branch protection

```
required status checks : 73 contexts
strict                 : true
merge queue            : NOT ENABLED
merge method           : merge commits ("Merge pull request #NNN from ...")
```

### 5.2 Today's configuration does not satisfy the stated audit invariant

The directive states: *"The exact merge SHA to `protected/main` must pass a full regression matrix."*

Required contexts are evaluated against **the head SHA of the PR branch**. The merge commit is created *at merge time* and is tested by nothing. Confirmed from `git log --merges`, main's history is composed of merge commits.

**The exact SHA that lands on `protected/main` today has no regression matrix attached to it.** `strict: true` guarantees only that the branch was up to date at some point before merging — a weaker property than the one the audit contract requires.

A merge queue validates the **speculative merge commit itself** — the actual object that becomes main — against the full 73-context matrix before it lands. Adopting it is not a concession to speed. It closes a real gap.

### 5.3 The convoy — linear growth in PR count

Under `strict: true` with no queue, merging any PR invalidates every other open PR, forcing a rebase and a complete 153-job re-run. Cost grows **linearly in the number of concurrent PRs**.

This is not hypothetical. It already occurred on 13 August: one logical change (B2.5-P13 corrective action III) was split across PRs #645–#648 and took **174 minutes and four complete matrices (≈596 checks)** to land.

With one PR in flight the effect is invisible. At B3 scale — multiple stacked PRs per phase — it dominates everything else in this document.

---

## 6. The Lever

Four changes. **No test is removed, skipped, made optional, or conditionally excluded.** No rule enumerates a path, module, or test name, so B3/B4/B5 inherit them without maintenance.

### L1 — Supersede in-flight runs, PR events only

Added mechanically to the 60 workflows lacking it:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

**Why this cannot weaken the audit chain.** `cancel-in-progress` evaluates false for `push` and for `merge_group`. A run is cancelled only when a newer commit has already replaced the one it was testing — a result that by definition can never gate a merge. The proof on `main` and in the queue always runs to completion. `r0-preflight-validation.yml` keeps its existing determinism opt-out.

**Recovers:** 14.7 min on PR #649.

### L2 — Dissolve the false barrier edges

Delete `needs: checkout` and `needs: validate-contracts` everywhere except the three jobs that genuinely read `.result`. **Keep both jobs. Keep them as required status checks.** They simply stop serialising the graph.

This collapses a three-tier pipeline into one tier and removes both dispatch round trips.

**Why this cannot weaken the audit chain.** Both assertions still execute on every PR and still block the merge — `validate-contracts` is already among the 73 required contexts, and the `checkout` job's two assertions (SHA adjudication, evidence placement) should be added to that list as part of this change. The only property removed is the guarantee that other jobs run *after* them, which nothing depended on: no artifact crosses these edges.

**Cost accepted:** a PR with broken contracts now burns runner minutes before failing. At 20 slots that trade is strongly positive, and it inverts entirely once L1 is in place.

**Recovers:** ~14 min. The largest single lever.

### L3 — Enable the caching that already ships

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.11'
    cache: 'pip'        # ← added

- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'        # ← added
```

Native to the official actions; no new dependencies. Lowers the CPU floor from 16.0 to 12.3 min.

**Why this cannot weaken the audit chain.** Cache keys are derived from lockfile hashes by the actions themselves. A changed lockfile is a cache miss. No assertion changes.

### L4 — Merge queue, and retire `strict: true`

1. Add the `merge_group:` trigger to the 46 workflows carrying `pull_request:`.
2. Enable the merge queue on `main` with the existing 73 required contexts.
3. Set `strict: false` — the queue supersedes it and is strictly stronger.

**Why this strengthens the audit chain.** The full matrix moves from the head SHA (never merged) to the merge commit (actually merged). All 73 contexts remain required. This is the change that carries the roadmap.

### L0 — Optional: raise the ceiling

The 20-job cap is a Free-plan limit. A GitHub Team seat is **$4/month** and raises it to 60. The benefit saturates at 40 (beyond that the serial phase chain binds), but 20 → 40 is worth **9 minutes per PR**. Cheapest minute-per-dollar available, and it requires no code change.

---

## 7. Simulation

### 7.1 Model

Discrete-event simulation using:

- Real per-job durations from PR #649 (153 jobs)
- The real `needs:` graph parsed from `ci.yml` (69 jobs)
- GitHub's declaration-order FIFO dispatch
- The measured 20-slot cap
- A 5-minute tier-boundary dispatch penalty, fitted to the two observed dead zones
- Per-job setup time measured from real step records (for the caching scenario)

**Validation:** the model reproduces the observed 58.2-minute run at **65.3 minutes — a 12% over-estimate**. Every figure below is therefore conservative.

### 7.2 Results

| Topology | Wall | Reduction |
|---|---:|---:|
| A — Today (observed) | 65.3 min | — |
| B — + L1 supersede stale runs | 48.3 min | 26% |
| C — + L2 dissolve barrier edges | 34.4 min | 47% |
| D — + L3 dependency caching | 30.2 min | 54% |
| **E — + L0 capacity 20 → 40 slots** | **21.1 min** | **64%** |

**L2 is worth more than L1 and L3 combined.**

Capacity sweep (with L1+L2+L3 applied):

| Slots | Plan | Wall | vs observed 58.2 |
|---:|---|---:|---:|
| 20 | Free (today) | 30.2 min | 48% |
| 40 | — | 21.1 min | 64% |
| 60 | Team ($4/mo) | 20.7 min | 64% |
| 180 | Enterprise | 20.7 min | 64% |

The sweep saturates exactly where theory predicts. At 60 and 180 slots the result is identical because the 14-minute phase chain *is* the pipeline. **Any claim of beating ~20 minutes on a single PR is either deleting assertions or wrong.**

### 7.3 Before/after by scenario

| Scenario | Today | After | Reduction |
|---|---:|---:|---:|
| **Hotfix** — PR #646, 1 file, +6 lines | 26 min | 12 min | 52% |
| **Single large PR** — #649, 24 files | 78 min | 28 min | 64% |
| **Observed convoy** — C3, PRs #645–648 | 174 min | 33 min | **81%** |
| **Projected B3 phase** — 6 stacked PRs | 397 min | 37 min | **91%** |

Convoy scaling — the shape matters more than the numbers:

| PRs in flight | Today (linear) | With merge queue | Reduction |
|---:|---:|---:|---:|
| 1 | 66 min | 32 min | 52% |
| 2 | 132 min | 32 min | 76% |
| 4 | 265 min | 33 min | 87% |
| 6 | 397 min | 37 min | 91% |
| 10 | 662 min | 39 min | 94% |

Today's cost grows linearly in concurrent PRs. With a queue it grows sub-linearly through batched speculation. **The pipeline's slowness compounds with exactly the parallelism that B3, B4 and B5 will demand.** That is the durable finding.

### 7.4 Verdict on the ≥70% target

| Reading | Result | Meets ≥70%? |
|---|---:|---|
| Single isolated PR | 64% | **No** — 14-min serial phase chain is the floor |
| Observed 4-PR convoy | 81% | Yes |
| Projected 6-PR phase | 91% | Yes |

Reported without adjustment. The target is missed on the narrow reading and comfortably exceeded on the one that governs delivery.

---

## 8. Rejected Alternatives

### Path filters — rejected on durability

The obvious answer (skip the schema suite when no `.sql` changed) is the one that rots. Every new module needs a filter entry; every missed entry is a silent hole in the trust chain; the failure mode is invisible until an auditor finds it. This is explicitly the anti-gaming trigger in the directive, and it is correct.

### Splitting `ci.yml` — rejected on measured uselessness

Superficially attractive at 228 KB and 5,848 lines. **Measurably returns zero minutes:** its 69 jobs already run concurrently, and splitting redistributes the same CPU against the same cap. It would cost days. The file's size is a genuine maintainability problem — worth addressing on its own terms, never as a velocity claim.

### Sharding or trimming the phase chain — rejected on integrity

It is 11.4 minutes of sequential verification against a live database. Sharding it would require asserting that its phases are independent, which is the one thing a phase chain exists to deny. Left untouched and named as the honest floor.

### Disabling or quarantining slow tests — rejected outright

The failure state named in the directive. Nothing in this proposal removes, skips, or conditionally excludes any assertion.

---

## 9. Implementation

### 9.1 Mechanical surface

A migration script (`ci_topology_migrate.py`, delivered separately) applies L1, L3, and L4's trigger. Run in dry-run mode against the live tree:

```
DRY RUN - nothing written
  files touched      : 61
  concurrency added  : 60
  merge_group added  : 45
  cache: keys added  : 176
```

It writes nothing without `--apply`. L2 is a scripted edit of `needs:` lists with three hand-verified exceptions. L0 is a billing setting.

**Realistic effort: one working day including review**, against 9–46 minutes returned per PR and two to six hours per phase convoy. This clears the diminishing-returns trigger by a wide margin.

### 9.2 Sequence

| Order | Lever | Rationale |
|---|---|---|
| 1 | **L1** | Pure waste reduction, zero risk; immediately makes all subsequent measurement cleaner |
| 2 | **L3** | Independent, mechanical, no topology change |
| 3 | **L2** | Last of the three — the only one whose rollback needs thought |
| 4 | **L4** | **After P13 is audited and merged.** Touches branch protection; deserves its own change window |
| — | **L0** | Any time; independent of all the above |

### 9.3 Non-vacuity proofs

Consistent with the repository's existing standard for non-vacuous proof:

- **Before landing L2** — push a deliberately broken contract and confirm `validate-contracts` still fails the merge. The edges are gone; the gate must not be.
- **Before landing L2** — push a file violating evidence placement and confirm the `checkout` job's assertion still blocks. Add it to the required-contexts list first.
- **After L1** — push twice in quick succession and confirm the first run is cancelled while a `push` to `main` under the same workflow is not.
- **After L4** — confirm the merge queue reports all 73 contexts against the speculative merge commit, not the branch head.

---

## 10. Limits of This Analysis

Stated so the numbers can be weighted correctly.

1. **The 65% cache hit-rate assumption in L3 is an estimate, not a measurement.** If it lands at 40%, scenario D moves from 30.2 to roughly 32 minutes. It does not change the ranking of the levers.

2. **The convoy model is analytic, not a replay.** Inputs — observed single-PR wall, an 8-minute inter-PR turnaround, 5-wide queue speculation — are defensible, but the 174-minute C3 figure is the only directly observed convoy datapoint.

3. **GitHub does not publish its dispatch-latency model.** The 5-minute tier penalty is fitted to two observed dead zones on one PR. It is the least certain constant in the simulation and the one that most favours L2 — treat L2's isolated contribution as **±3 minutes**.

4. **PR #641's 196-minute span was excluded** from wall-clock analysis as an outlier driven by re-runs hours after the fact, not by pipeline physics. Its lead time is retained in §2.1 where only change size and check count matter.

5. **Job-level analysis covers PR #649 only.** Check-run-level analysis covers PRs #641–#650. The mechanisms in §4 are demonstrated on one PR; the invariance result in §2.1 is demonstrated across nine.

---

## Appendix A — Non-Interference Statement

- PR #649 merged at **18:22:37Z**, before this analysis began. It was never modified, branched, paused, or written to.
- The Implementation Agent has since opened PR #650 (`codex/b25-p13-c4-main-ci`). Its workflow runs were read via the API only.
- `git status` on `.github/` returns clean. The only working-tree modification is the pre-existing `docs/forensics/B2.5-P13 Remediation Evidence Pack.md`, untouched by this analysis.
- All artifacts produced by this work live outside the repository.

## Appendix B — Key Constants

| Constant | Value | Source |
|---|---:|---|
| Concurrency cap | 20 | measured (peak over 432 intervals) |
| Required status checks | 73 | branch protection API |
| `strict` | true | branch protection API |
| Merge queue | disabled | branch protection API |
| Workflow files | 62 | filesystem |
| Workflows with `pull_request` | 46 | static parse |
| Workflows with `concurrency` | 2 | static parse |
| Workflows with `merge_group` | 1 | static parse |
| `ci.yml` size | 227,988 bytes / 5,848 lines | filesystem |
| `ci.yml` jobs | 69 | static parse |
| `ci.yml` checkouts | 69 | static parse |
| `ci.yml` `download-artifact` | 0 | static parse |
| `checkout` dependents | 66 | DAG parse |
| `validate-contracts` dependents | 42 | DAG parse |
| `setup-python` steps (all workflows) | 155 | static parse |
| `cache:` keys (all workflows) | 5 | static parse |

## Appendix C — Reproduction

Concurrency ceiling:

```bash
gh api "repos/Synergyscape-V1/skeldir-2.0/actions/runs?branch=BRANCH&per_page=100" --paginate
```

Then sweep `started_at`/`completed_at` intervals from each run's `/jobs` endpoint and take the maximum overlap.

Per-PR check-run timing:

```bash
gh api "repos/Synergyscape-V1/skeldir-2.0/commits/$(gh pr view 649 --json headRefOid -q .headRefOid)/check-runs?per_page=100" --paginate
```

Branch protection posture:

```bash
gh api repos/Synergyscape-V1/skeldir-2.0/branches/main/protection -q '.required_status_checks | {strict, count: (.contexts|length)}'
```

Confirm the hub edges carry no data:

```bash
grep -c "download-artifact" .github/workflows/ci.yml
```
