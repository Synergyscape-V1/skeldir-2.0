# Priority Queue CDO Remediation — Evidence Pack

**Final Verdict: COMPLETE**

**Authority:** CDO UI Design Audit 1 + Audit 2 (queue interaction + sequential triage)  
**Governance:** `memory-bank/skill/design-implementation-skill.md`  
**Evidence pack path:** `skeldir-ui/evidence/priority_queue_cdo_remediation/`  
**Harness:** `src/test/priorityQueueRemediation.harness.test.tsx`

---

## Phase 0 — Implementation brief

| Item | Resolution |
|------|------------|
| Terminal user goal | Clear all blockers so budget action is safe — not “open top queue item once” |
| Audit 1 mandate | Replace singular top-issue routing with `PriorityQueue` drawer + numbered list + real-time decrement + completion |
| Audit 2 mandate | `/budget/:simulationId` (and claim destinations) adapt when `source=command_center_queue` into Sequential Triage Nodes |
| Adjacent contracts | Command Center header CTA, PriorityQueue section, BudgetProposalFlow, ClaimDetailPage |
| Doc 1 alignment | UI Spec priority-queue row semantics retained; CDO audits supersede defective singular CTA interpretation |

### Negative scope (binding exclusions)

- No auto-execute / auto-optimize / guaranteed-lift affirmations
- No inventing financial truth in the queue
- No Command Center redesign outside queue/triage remediation
- No removal of standalone budget proposal flow (non-triage entry)

### Hypothesis responses

| Hypothesis | Implementation response |
|---|---|
| H-UI-Queue-Hidden | Numbered drawer list + page ranks; CTA opens drawer |
| H-UI-PostAction-Silent | Banner decrement via triage store; Approved ✓; toast |
| H-UI-Orphan-DeepLink | `source=command_center_queue` + issue index params on all queue hrefs |
| H-UI-Global-Desync | Shared `triageQueueStore` with stable snapshot + Command Center sync |
| H-UI-Terminal-Ambiguity | `PostActionSuccessOverlay` advance / all-clear modes |
| H-UI-Scale-Collapse | Drawer list scales with issue count (scrollable panel) |

---

## Exit gates

| Gate | Method | Actual output | Result |
|------|--------|---------------|--------|
| G-01 Banner copy | Mount `/app` → urgency text | `N issues blocking your budget` | **PASS** |
| G-02 Plural CTA opens drawer | Click `Review issues (3)` | `[data-priority-queue-drawer]` with 3 ranked rows | **PASS** |
| G-03 Triage hrefs | Inspect row `data-priority-action-href` | Includes `source=command_center_queue` | **PASS** |
| G-04 Decrement feedback | Resolve issue in store → remount `/app` | Banner shows 2; row `data-priority-resolved=true` | **PASS** |
| G-05 Completion | Resolve all → remount | All-clear copy + `go_to_budget` CTA | **PASS** |
| G-06 Triage header | Budget with triage params | `TriageContextHeader` + Approve & Advance | **PASS** |
| G-07 Standalone preserved | `/app/budget/sim_0001` | Submit proposal; no triage chrome | **PASS** |
| G-08 Auto-advance | Approve & Advance → 1.5s | Navigates to next claim triage href | **PASS** |
| G-09 Claim triage | Claim with triage params | Mark reviewed & Advance control | **PASS** |
| G-10 Fail-closed malformed | Broken triage query | No triage chrome | **PASS** |
| G-11 Negative singular CTA | Query Review top issue | Absent as primary CTA | **PASS** |

### Empirical harness runs

```text
npm test -- --run src/test/priorityQueueRemediation.harness.test.tsx
→ 11 tests passed

npm test -- --run src/test/level9.harness.test.tsx
→ scope scan PASS (forbidden-copy clean)

npm test -- --run src/test/level10.harness.test.tsx
→ priority/primary-action remediation assertions PASS
→ known pre-existing FAIL: channel table `[data-evidence-class-badge]` (documented in channel_detail_cdo_remediation evidence; out of scope)
```

---

## Architecture delivered

| Layer | Path |
|-------|------|
| Triage URL contract | `src/commandCenter/triageHref.ts` |
| Queue session store | `src/commandCenter/triageQueueStore.ts`, `useTriageQueue.ts` |
| Advance / overlay hook | `src/commandCenter/useTriageAdvance.tsx` |
| PriorityQueue modal | `src/components/commandCenter/PriorityQueueModal/` |
| Header CTA + banner | `CommandCenterSubcomponents.tsx`, `copy.ts`, `resolvePrimaryAction` |
| Page queue ranks | `PriorityQueue.tsx` |
| Triage chrome | `components/triage/TriageContextHeader/`, `PostActionSuccessOverlay/` |
| Budget sequential node | `BudgetSimulationDetailPage.tsx`, `BudgetProposalFlow.tsx` |
| Claim sequential node | `ClaimDetailPage.tsx` |

---

## Disposition matrix (queue × triage)

| State | Behavior |
|-------|----------|
| Issues > 0, none resolved | Banner N; CTA `review_issues`; drawer lists all |
| Issue resolved mid-queue | Banner N-1; row Approved ✓; next highlighted in drawer |
| All resolved (session) | All-clear banner; CTA Go to Budget Simulation |
| Entry without triage source | Standalone detail chrome + Submit proposal |
| Entry `source=command_center_queue` | TriageContextHeader + Approve & Advance / Mark reviewed |
| Malformed triage params | Fail closed → standalone (no triage chrome) |
| Post-success with remaining | Overlay 1.5s → auto-navigate next triage href |
| Post-success queue empty | All Blockers Cleared + Return to Dashboard |

---

## Anti-gaming notes

- Primary CTA is a **button that opens the queue**, not a deep-link to `queue.top()` — letter-without-intent of UI Spec priority sort is rejected per CDO Audit 1.
- Harness includes negative control: singular “Review top issue” must not be the supervisory primary CTA.
- Snapshot for `useSyncExternalStore` is identity-stable between emits (prevents update-depth theater).
