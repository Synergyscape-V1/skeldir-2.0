# COMMAND CENTER BASELINE DELTA

**Audit date:** 2026-06-30  
**Route:** `http://127.0.0.1:5211/app` (session bootstrapped via `/dev/level10-specimens?fixture=command-center-loaded`)  
**Authority:** Executable source + local runtime = current state; directive target contract = target state.

---

## 1. Executive verdict

The executable `/app` Trust Command Center **exists and renders aggregate supervisory content**, but it **materially diverges** from the Deterministic Target Contract across shell chrome, token fidelity, page-header semantics, summary-card structure, chart/grid layout, channel-table presentation, and at least one **S0 raw-variable leak** in priority-queue copy. Context is sufficient to author a precise implementation directive; remediation scope is large and must be sequenced by severity.

**Implementation readiness:** YES (for writing a directive) — component ownership, runtime evidence, and severity-ranked deltas are mapped.

---

## 2. Current executable state summary

| Region | Present | Notes |
|--------|---------|-------|
| Route `/app` → `CommandCenterPage` | YES | `ShellRoutes.tsx` index route |
| App shell (sidebar, header, mobile nav) | YES | `AuthenticatedAppShell` |
| Page header (in-page H1) | YES | Separate from shell header title |
| Trust state summary row (4 cards) | YES | Order/labels/styling diverge |
| Priority queue | YES | Title/copy/variable leak diverge |
| Verified revenue trend | YES | Table + unavailable panel, not chart |
| Channel trust table | YES | 8 columns; bps-only discrepancy |
| Recent TrustEnvelopes | YES | Below chart/table grid |
| Audit activity strip | YES | Below chart/table grid |
| Loading / error / kill-switch states | PARTIAL | Logic exists; copy/skeleton fidelity gaps |

**Data plane:** `commandCenterClient.ts` aggregates claims, trust index, channels, exceptions, audit, and health clients — does not fabricate financial truth; composes from downstream ledgers.

---

## 3. Deterministic Target Contract summary

Target requires: 264px sidebar with ordered nav + brand anchor; 64px header with title / centered tenant selector / status pill + notification + user menu; page header with H1, subtitle, humanized timestamp, urgency copy, single conditional CTA; four styled summary cards with authority, trend, drill-down links; `Needs review` priority queue sorted by severity without raw variables; 30-day verified revenue **chart** or dignified empty state; 48–52% chart/table grid at ≥1280px; channel table with % discrepancy + status badges; consistent Bayesian/benchmark columns; recent envelopes + audit reconstruction; skeleton loading matrix; WCAG 2.2 AA with 44px targets and token-complete styling.

---

## 4. Hypothesis ledger results (summary)

| Status | Count |
|--------|------:|
| VALIDATED | 18 |
| PARTIALLY VALIDATED | 28 |
| REFUTED | 19 |
| NOT TESTABLE | 5 |

Full per-hypothesis falsification records: `command_center_baseline_context_inventory.md` § Hypothesis Ledger.

---

## 5. Shell / navigation delta

| Target | Current | Severity |
|--------|---------|----------|
| Brand anchor with shield/wordmark | Absent — no `data-brand` / logo slot | S1 |
| Nav order: Command Center first | Extra **App frame** link precedes Command Center | S1 |
| Active route = Command Center on `/app` | `resolveActiveNavId` returns `landing`; **App frame** nav item active | S1 |
| Semantic nav icons | Placeholder 20×20 muted boxes (`shellNav.module.css`) | S1 |
| Sidebar 264px @ desktop | **VALIDATED** 264px (`computed-styles-desktop.json`) | — |
| Sidebar padding 16px | **VALIDATED** | — |
| Nav item 44px / 8px radius | **VALIDATED** on active item | — |

**Implicated:** `AuthenticatedAppShell.tsx`, `SidebarNavigation.tsx`, `shell/navigation.ts`, `shellNav.module.css`

---

## 6. Global header delta

| Target | Current | Severity |
|--------|---------|----------|
| Left: page title | Shell title = `Skeldir` (`pageTitleDefault`), not route-specific Command Center title | S2 |
| Center: tenant selector | Tenant selector grouped **right** with status pill + user menu | S2 |
| Right: status pill, **notification bell**, user menu | **No notification control** | S1 |
| Header height 64px | `ResponsiveShell` header landmark 64px; inner `TopHeader` flex row ~44px content | S3 |
| Status pill label + success token + tooltip + `/audit?filter=system_health` | Label **VALIDATED**; tooltip via `title`; click navigates; pill computed height **20px** (below 44px target) | S2 |

**Implicated:** `TopHeader.tsx`, `GlobalSystemHealthStrip.tsx`, `SystemStatusPill.tsx`, `shell/copy.ts`

---

## 7. Page header delta

| Target | Current | Severity |
|--------|---------|----------|
| H1 `Trust Command Center` 32/40/700 | **VALIDATED** runtime computed | — |
| Subtitle with commas | Copy uses `?` separators (`copy.ts` `pageQuestion`) | S3 |
| Humanized relative timestamp | `toLocaleString()` — **seconds visible** at runtime | S2 |
| `{N} issues require review…` when N>0 | **Absent** | S1 |
| Primary CTA conditional labels | Logic in `resolvePrimaryAction`; third fallback `Continue onboarding` | S2 |
| CTA 44px target, 120ms hover, focus visible | Link height **21px**; no `shared.focusVisible`; no motion token on `.primaryButton` | S2 |

**Implicated:** `CommandCenterSubcomponents.tsx`, `commandCenter/copy.ts`, `commandCenterClient.ts`

---

## 8. Trust state summary delta

| Target | Current | Severity |
|--------|---------|----------|
| Four cards: Verified revenue, Claims reconciled, **Action authority**, **Open exceptions** | Order: verified → reconciled → **open exceptions** → **action authority** | S2 |
| Card surface: bg.card, border, 12px radius, 24px padding, elevation | CSS uses **undefined aliases** (`--color-bg-card`, `--spacing-24`, `--radius-card`) — runtime: padding 0, no shadow | S1 |
| Metric H2 minimum 24/32/700 | `.metricValue` uses `--font-size-h3` (undefined) → runtime **16px / 400** | S2 |
| Trend/delta indicator | **Absent** | S1 |
| Drill-down links per card | **Absent** | S1 |
| Authority badges | **Present** on all four cards | — |

**Implicated:** `TrustStateSummaryRow.tsx`, `CommandCenterSubcomponents.module.css`

---

## 9. Priority queue delta

| Target | Current | Severity |
|--------|---------|----------|
| Section title `Needs review` | `Priority queue` | S2 |
| No raw internal variables | Runtime: `Comparable_to_previous_value=false` in explanation (`commandCenterClient.ts:204`) | **S0** |
| Severity-sorted categories | Sort logic **VALIDATED** in `prioritySeverity.ts`; fixture showed one category | — |
| Status pill + separate action | **VALIDATED** | — |
| Empty: `No trust issues need review.` + `View all claims` | Message **VALIDATED**; **no View all claims link** | S2 |

**Implicated:** `PriorityQueue.tsx`, `commandCenterClient.ts`, `copy.ts`

---

## 10. Verified revenue trend delta

| Target | Current | Severity |
|--------|---------|----------|
| 30-day chart with axes/tooltip | **HTML table** of trend points, max 14 points | S1 |
| Verified commerce-backed data only | Client aggregates `verifiedRevenueMinor` from claims — semantics **VALIDATED** | — |
| Designed empty state with recovery path | `DataUnavailablePanel` with variant `sparse_data` title **"Insufficient data for this operation."** — forbidden raw copy | S1 |
| Card container styling | Broken token aliases — no card elevation at runtime | S2 |

**Implicated:** `VerifiedRevenueTrendCard.tsx`, `commandCenterClient.ts`, `DataUnavailablePanel.tsx`

---

## 11. Chart / table grid delta

| Target | Current | Severity |
|--------|---------|----------|
| Two-column 48–52% ratio @ ≥1280px | Runtime `gridTemplateColumns: 184px 768px` (~19% / 81%) | S2 |
| 24px gap | `gap: normal` (0) in computed grid | S3 |
| No horizontal overflow | **Desktop/wide: none**; **mobile + tablet: overflow** (channel table `min-width: 768px`) | S2 |

**Implicated:** `CommandCenterPage.module.css`, `CommandCenterSubcomponents.module.css` (`.channelTable`)

---

## 12. Channel trust table delta

| Target | Current | Severity |
|--------|---------|----------|
| All 8 columns | **VALIDATED** | — |
| Discrepancy % + status badge | **`{bps} bps` only** — no %, no Rejected/Flagged/Within tolerance | S2 |
| Claimed revenue authority metadata | Verified column has badge; **claimed column has no AuthorityBadge** | S0 |
| Bayesian / benchmark consistency | Plain text `Available`/`Unavailable` **plus** `AuthorityBadge` in same cell | S2 |
| Channel as link | `Link` to channel detail — default link styling | S2 |

**Implicated:** `ChannelTrustTableCard.tsx`, `commandCenterClient.ts`

---

## 13. Recent TrustEnvelopes delta

| Target | Current | Severity |
|--------|---------|----------|
| Section below chart/table | **VALIDATED** | — |
| Fields: id, subject, status, created, authority, audit ref | **VALIDATED** when fixture data present | — |
| Created time humanized | `toLocaleString()` — machine format | S3 |

**Implicated:** `RecentTrustEnvelopesCard.tsx`

---

## 14. Audit Activity delta

| Target | Current | Severity |
|--------|---------|----------|
| Section below chart/table | **VALIDATED** | — |
| event type, time, source label, artifact state, route | Has type, time, tier/result/artifact; **no explicit system/source label** | S2 |
| Routes to `/audit` | **VALIDATED** | — |

**Implicated:** `AuditActivityStrip.tsx`

---

## 15. Loading / error / empty / kill-switch delta

| State | Target | Current | Severity |
|-------|--------|---------|----------|
| Loading <2s | Skeleton cards + rows | Single `Skeleton` block | S2 |
| Loading >2s copy | `Still loading verified trust state…` | `Loading supervisory aggregate…` | S3 |
| Loading >8s retry | Present in `useCommandCenter` | **VALIDATED** in code/tests | — |
| Trust API error banner | Exact red copy | **VALIDATED** (`copy.ts`, tests) | — |
| Kill switch | Read-only UI preserved | **VALIDATED** (tests) | — |
| Empty tenant | Onboarding panel | **VALIDATED** | — |

**Implicated:** `CommandCenterPage.tsx`, `useCommandCenter.ts`, `copy.ts`

---

## 16. Responsive delta

| Viewport | Finding | Severity |
|----------|---------|----------|
| 375px mobile | Horizontal overflow; bottom nav present; sidebar hidden | S2 |
| 768px tablet | Horizontal overflow; sidebar forced 264px @1024+ but tablet rule sets 64px in `ResponsiveShell` | S2 |
| 1280px desktop | No page overflow; grid imbalance | S2 |
| 1440px wide | No page overflow | — |

**Evidence:** `overflow-by-viewport.json`, screenshots in `visual/`

---

## 17. Keyboard / accessibility delta

| Target | Current | Severity |
|--------|---------|----------|
| Tab reachability | Not exhaustively recorded in this audit | SX |
| Focus 2px #2563EB / 3px offset | `shared.focusVisible` on nav; **primary CTA lacks** `focusVisible` class | S2 |
| aria-live polite/assertive | Error banner assertive; health banner polite | PARTIAL |
| 44px interactive targets | Status pill ~20px; primary CTA ~21px height | S2 |
| Icon + label + tooltip for status | Status pill **VALIDATED** | — |

---

## 18. Design-token / style-system delta

**Critical defect:** `CommandCenterSubcomponents.module.css` and `CommandCenterPage.module.css` reference **shorthand CSS variables that are not defined anywhere in the repository**:

```text
--color-bg-card, --color-border-default, --spacing-24, --radius-card,
--font-size-h3, --font-size-small, --font-size-body, --target-size-min
```

Canonical tokens exist as `--sk-color-bg-card`, `--sk-space-6`, `--sk-radius-md`, `--sk-font-size-h2`, etc. in `tokens/tokens.css`.

**Runtime effect:** Summary cards, panels, and buttons lose intended padding, radius, background, elevation, and typography.

| Severity | Finding |
|----------|---------|
| S1 | Token alias breakage on all Command Center surfaces |
| S3 | No `box-shadow: var(--sk-elevation-card)` on summary/panel cards |
| S3 | Primary button uses `--color-trust-probabilistic` (undefined) for background |

---

## 19. Asset availability inventory

| Asset | Found | Path | Used by `/app` | Official vs placeholder | Risk |
|-------|------:|------|----------------|-------------------------|------|
| Skeldir shield logo | NO | — | NO | — | S1 brand gap |
| Wordmark lockup | NO | — | NO | — | S1 |
| Favicon | YES | `public/favicon.svg` | Indirect | Placeholder | Low |
| Nav icon library | NO | Placeholder boxes only | YES | Placeholder | S1 |
| Avatar / user image | NO | Text menu only | YES | N/A | Low |
| Chart library | NO | Table fallback | YES | N/A | S1 chart gap |
| Badge/icon primitives | YES | `StatusIcons.tsx`, `AuthorityBadge` | YES | Internal | — |
| Empty-state illustrations | NO | `DataUnavailablePanel` text only | YES | N/A | S2 |

---

## 20. Severity-ranked remediation backlog

### S0 — Semantic trust violations (block release)

1. Remove `Comparable_to_previous_value=false` from user-facing priority copy (`commandCenterClient.ts:204`).
2. Add authority metadata to **claimed revenue** column (or explicit non-trust labeling per spec).
3. Audit all Command Center surfaces for snake_case / debug copy leakage.

### S1 — Enterprise credibility failures

1. Fix undefined CSS token aliases across Command Center stylesheets.
2. Add brand anchor (or document approved placeholder contract).
3. Fix `/app` active nav — Command Center, not App frame.
4. Remove or relocate legacy **App frame** sidebar entry on Level 10+.
5. Add notification control or spec-approved omission record.
6. Add summary-card drill-down links, trend indicators, card elevation.
7. Replace trend table with chart or spec-approved unavailable state copy.
8. Add page-header urgency copy when N>0.
9. Add `View all claims` link in empty priority state.

### S2 — Operational scanability

1. Fix chart/table grid ratio and 24px gap.
2. Channel discrepancy: percentage + status badge.
3. Normalize Bayesian/benchmark column representation.
4. Humanize timestamps (relative, no seconds).
5. Reorder summary cards; fix metric typography to H2.
6. Contain channel table horizontal overflow on mobile/tablet.
7. Header layout: tenant selector placement per contract.
8. Rename priority section to `Needs review`.

### S3 — Polish

1. Subtitle punctuation; loading copy exact match.
2. Shell header title vs in-page H1 coordination.
3. Primary CTA hover transition token.
4. Grid gap token application.

---

## 21. Files / components implicated

```text
src/app/routes/ShellRoutes.tsx
src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx
src/components/shell/SidebarNavigation/SidebarNavigation.tsx
src/components/shell/TopHeader/TopHeader.tsx
src/components/shell/GlobalSystemHealthStrip/*
src/components/shell/MobileBottomNavigation/*
src/components/shell/shellNav.module.css
src/components/commandCenter/CommandCenterPage/CommandCenterPage.tsx
src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.tsx
src/components/commandCenter/CommandCenterPage/TrustStateSummaryRow.tsx
src/components/commandCenter/CommandCenterPage/PriorityQueue.tsx
src/components/commandCenter/CommandCenterPage/VerifiedRevenueTrendCard.tsx
src/components/commandCenter/CommandCenterPage/ChannelTrustTableCard.tsx
src/components/commandCenter/CommandCenterPage/RecentTrustEnvelopesCard.tsx
src/components/commandCenter/CommandCenterPage/AuditActivityStrip.tsx
src/components/commandCenter/CommandCenterPage/CommandCenterPage.module.css
src/components/commandCenter/CommandCenterPage/CommandCenterSubcomponents.module.css
src/commandCenter/commandCenterClient.ts
src/commandCenter/copy.ts
src/commandCenter/useCommandCenter.ts
src/commandCenter/prioritySeverity.ts
src/components/layout/ResponsiveShell/ResponsiveShell.module.css
src/tokens/tokens.css
```

---

## 22. Evidence index

| Artifact | Path |
|----------|------|
| Runtime screenshots (4 viewports) | `evidence/command_center_baseline/visual/app-loaded-*.png` |
| Screenshot manifest | `evidence/command_center_baseline/runtime-screenshots.json` |
| Computed styles (desktop) | `evidence/command_center_baseline/computed-styles-desktop.json` |
| Overflow audit | `evidence/command_center_baseline/overflow-by-viewport.json` |
| Level 10 harness tests | `src/test/level10.harness.test.tsx` |
| Level 10 prior visual | `evidence/Level_10/visual/` |

---

## 23. Remaining unknowns

1. Full keyboard traversal recording not captured in this audit pass (recommend Playwright trace in implementation phase).
2. Not all five priority-queue categories observed in single default fixture — sorting verified statically + partial runtime.
3. `auto_executable_within_policy` contradiction state not exercised on Command Center channel rows in default fixture.
4. Whether product owner will supply official brand assets or approve placeholder contract.

---

## 24. Implementation-readiness verdict

**YES** — Forensic inventory, hypothesis labeling, severity ranking, file ownership, and runtime corroboration are sufficient to author a binding CRHAID-style implementation directive for Command Center realignment.
