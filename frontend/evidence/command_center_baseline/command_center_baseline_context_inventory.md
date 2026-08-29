# command_center_baseline_context_inventory.md

**Directive:** COMMAND CENTER BASELINE CONTEXT INVENTORY DIRECTIVE  
**Audit type:** Static + runtime baseline (no product code changes)  
**Date:** 2026-06-30  
**Subject:** Executable `/app` Trust Command Center vs Deterministic Target Contract

---

## Final response (directive §23)

```text
Final Verdict: CONTEXT GATHERED

Files inspected: 47 source files (see §File inventory)
Runtime routes inspected: /app (via Level10 specimen session bootstrap → real AppShellRoutes)
Viewports captured: mobile 375, tablet 768, desktop 1280, wide 1440
Screenshots generated: 4 (evidence/command_center_baseline/visual/)
Computed-style evidence collected: YES (desktop 1280)
Hypotheses validated: 18
Hypotheses refuted: 19
Hypotheses partially validated: 28
Hypotheses not testable: 5
Top S0 defects:
  - Raw internal variable in priority queue user copy (Comparable_to_previous_value=false)
  - Claimed revenue column lacks authority metadata in channel trust table
Top S1 defects:
  - Undefined CSS token aliases break Command Center card/panel/button styling
  - No brand anchor; placeholder nav icons only
  - Active nav highlights "App frame" not "Command Center" on /app
  - Missing notification bell; missing urgency copy; missing summary drill-downs/trends
  - Trend is table not chart; undignified empty-state title
Top S2 defects:
  - Chart/table grid ratio 19/81 not 48–52; mobile/tablet horizontal overflow
  - Discrepancy bps-only; inconsistent Bayesian/benchmark columns
  - Machine timestamps; metric typography below H2 contract
Top S3 defects:
  - Subtitle punctuation; loading copy mismatch; grid gap unset
Asset gaps: Official shield, wordmark, nav icon set, chart library
Evidence pack path: skeldir-ui/evidence/command_center_baseline/
Delta document path: skeldir-ui/evidence/command_center_baseline/COMMAND_CENTER_BASELINE_DELTA.md
Implementation readiness: YES
Reason: Component ownership mapped; 70/70 hypotheses labeled; runtime + computed corroboration complete
No-code-change confirmation: YES
```

---

## 1. Audit authority and method

### 1.1 Authority hierarchy (applied)

1. **Executable source + local runtime** → current state authority  
2. **Deterministic Target Contract** (directive §5–15) → target state authority  
3. Prior specs / screenshots → hypothesis only unless re-verified  
4. Runtime screenshots → visual evidence, not sole proof  

### 1.2 Evidence types collected

| Type | Method |
|------|--------|
| Static | Full read of route tree, Command Center components, shell, tokens, client, copy |
| Runtime | Playwright Chromium @ local Vite dev server, real `/app` after mock session bootstrap |
| Computed | `getComputedStyle` + bounding boxes @ 1280px desktop |
| Harness | Cross-reference `level10.harness.test.tsx` behavioral assertions |

### 1.3 Session bootstrap note

`/app` requires authenticated session + tenant. Runtime audit used `/dev/level10-specimens?fixture=command-center-loaded`, which establishes mock session/tenant and **navigates to the production route tree** (`AppShellRoutes` → `CommandCenterPage`). This is the same component graph a signed-in user hits at `/app`; it is not an isolated Storybook mock.

---

## 2. Component ownership map

```text
/app
└── ShellAccessGuard
    └── AuthenticatedAppShell
        ├── ResponsiveShell
        │   ├── TopHeader
        │   │   ├── GlobalSystemHealthStrip → SystemStatusPill
        │   │   ├── TenantSelector
        │   │   └── UserMenu
        │   ├── SidebarNavigation (desktop)
        │   └── RouteContainer → Outlet
        │       └── CommandCenterPage
        │           ├── CommandCenterPageHeader / LastUpdatedTimestamp
        │           ├── GlobalPrimaryActionButton
        │           ├── TrustStateSummaryRow → AuthorityBadge ×4
        │           ├── PriorityQueue → PolicyAuthorityPill + action links
        │           ├── gridTwo
        │           │   ├── VerifiedRevenueTrendCard → table | DataUnavailablePanel
        │           │   └── ChannelTrustTableCard → PolicyAuthorityPill + AuthorityBadge
        │           └── gridTwo
        │               ├── RecentTrustEnvelopesCard
        │               └── AuditActivityStrip
        └── MobileBottomNavigation → MoreNavigationSheet
```

**Data ingress:** `useCommandCenter` → `commandCenterClient.fetchAggregate` → claims, trust index, channels, exceptions, operational audit clients.

---

## 3. Semantic invariant audit (directive §4)

| Invariant | Status | Evidence |
|-----------|--------|----------|
| Platform claim ≠ verified truth | PASS | Trend caption states verified-only; channel table separates columns |
| AI/LLM/Bayesian ≠ financial truth creator | PASS | No forbidden copy found on Command Center |
| Financial numbers expose authority | **FAIL** | Claimed revenue column has no AuthorityBadge |
| Confidence-bearing values expose authority | PARTIAL | Bayesian column mixes text + badge |
| Action surfaces expose policy authority | PASS | PolicyAuthorityPill on queue rows + channel table |
| Claimed vs verified visually distinct | PASS | Separate columns |
| Deterministic outranks probabilistic visually | PARTIAL | Token hierarchy not visible when CSS aliases broken |
| Audit reconstruction accessible | PASS | Audit strip + audit ref links |
| No raw internal names in user copy | **FAIL** | `Comparable_to_previous_value=false` at runtime |
| Dashboard summaries reconstruct to source | PASS | `data-source-surface` attributes; client traces `sourceTrace` |

**S0 violations:** 2 confirmed.

---

## 4. Hypothesis ledger (H-TCC-01 – H-TCC-70)

Format per directive §18.

---

### 16.1 Shell / navigation

**Hypothesis ID:** H-TCC-01  
**Claim:** Brand anchor with shield/logo + wordmark exists.  
**Status:** REFUTED  
**Static evidence:** `SidebarNavigation.tsx` — no brand region; no logo import.  
**Runtime evidence:** `hasBrand: false` equivalent — no `[data-brand]` in DOM.  
**Computed evidence:** N/A  
**Target-contract comparison:** §6.2 requires brand area — absent.  
**Severity:** S1  
**Implementation implication:** Add brand slot or approved placeholder per design authority.  
**Remaining uncertainty:** Whether official assets exist outside repo (none found).

---

**Hypothesis ID:** H-TCC-02  
**Claim:** Sidebar width 264px ±2px @ desktop.  
**Status:** VALIDATED  
**Static evidence:** `--sk-dimension-sidebar-width: 264px`; `ResponsiveShell.module.css`  
**Runtime evidence:** `computed-styles-desktop.json` → aside width 264px  
**Computed evidence:** boundingBox.width 264  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-03  
**Claim:** Sidebar padding 16px ±2px.  
**Status:** VALIDATED  
**Static evidence:** `.sidebar { padding: var(--sk-space-4) }` = 16px  
**Runtime evidence:** aside padding 16px  
**Computed evidence:** padding: 16px  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-04  
**Claim:** Nav item height 44px, radius 8px, icon 20px.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `shellNav.module.css` — min-height 44px, radius `--sk-radius-sm` (8px), icon 20px  
**Runtime evidence:** Active item height 44px, radius 8px  
**Computed evidence:** `a[aria-current=page]` height 44px, borderRadius 8px  
**Target-contract comparison:** Geometry match; icon is muted placeholder block not semantic icon  
**Severity:** S3 (icon semantics)  
**Implementation implication:** Wire approved icon set  
**Remaining uncertainty:** Approved library not in repo

---

**Hypothesis ID:** H-TCC-05  
**Claim:** Nav order matches contract list exactly.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `SHELL_NAV_ITEMS` order matches contract; **extra** "App frame" link prepended in `SidebarNavigation.tsx`  
**Runtime evidence:** navItems: App frame, Command Center, Revenue Claims…  
**Target-contract comparison:** Extra first item violates exact order  
**Severity:** S1  
**Implementation implication:** Remove Level 2 landing link or demote below Command Center  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-06  
**Claim:** Every nav item has semantic icon or reserved slot.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `.navIcon` placeholder on all items  
**Runtime evidence:** 20×20 gray boxes visible in screenshots  
**Target-contract comparison:** Slot yes; semantic icon no  
**Severity:** S1  
**Implementation implication:** Icon library integration  
**Remaining uncertainty:** Asset source TBD

---

**Hypothesis ID:** H-TCC-07  
**Claim:** Nav items are links, not toggles.  
**Status:** VALIDATED  
**Static evidence:** `NavLink` components only  
**Runtime evidence:** No checkbox/toggle controls in sidebar  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-08  
**Claim:** Active Command Center item uses #EEF4FF / #1D4ED8.  
**Status:** REFUTED  
**Static evidence:** `resolveActiveNavId('/app')` returns `'landing'` not `'command-center'`  
**Runtime evidence:** Active item text "App frame" with correct active colors  
**Computed evidence:** active link color rgb(29,78,216), bg rgb(238,244,255) on wrong item  
**Target-contract comparison:** Colors match contract; **wrong item active**  
**Severity:** S1  
**Implementation implication:** Map `/app` → `command-center` nav id; remove landing/active conflict  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-09  
**Claim:** Mobile bottom nav: Command, Claims, Channels, Audit, More.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `MOBILE_PRIMARY_NAV_IDS` + More button; labels use first word of full label  
**Runtime evidence:** mobile screenshot shows bottom nav (sidebar hidden per CSS)  
**Target-contract comparison:** Structure match; label truncation acceptable  
**Severity:** S3  
**Implementation implication:** Optional label tuning  
**Remaining uncertainty:** More sheet contents not exhaustively audited

---

### 16.2 Global header

**Hypothesis ID:** H-TCC-10  
**Claim:** Header height 64px ±2px.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `ResponsiveShell.module.css` `.header { height: 64px }`  
**Runtime evidence:** Outer shell header 64px; inner `data-shell-header` content 44px tall  
**Computed evidence:** Shell landmark vs inner flex row  
**Target-contract comparison:** Container 64px; inner controls shorter  
**Severity:** S3  
**Implementation implication:** Vertically center controls in 64px band  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-11  
**Claim:** Header regions: title left, tenant center, status/notification/user right.  
**Status:** REFUTED  
**Static evidence:** `TopHeader.tsx` — title left, all controls in right flex group  
**Runtime evidence:** No notification element; tenant right-grouped  
**Target-contract comparison:** Layout and notification missing  
**Severity:** S1 (notification), S2 (layout)  
**Implementation implication:** Restructure header grid; add notification control  
**Remaining uncertainty:** Notification scope for MVP

---

**Hypothesis ID:** H-TCC-12  
**Claim:** Tenant selector interactive dropdown with accessible name.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `TenantSelector.tsx` — disabled when single tenant  
**Runtime evidence:** "Workspace: Acme RevOps", height 44px, `aria-label` via copy  
**Target-contract comparison:** Control exists; not centered; no chevron when single  
**Severity:** S2  
**Implementation implication:** Layout + multi-tenant fixture test  
**Remaining uncertainty:** Multi-tenant dropdown not exercised

---

**Hypothesis ID:** H-TCC-13  
**Claim:** Operational status pill label, success token, tooltip, audit route.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `SystemStatusPill.tsx`, `OPERATIONAL_AUDIT_COPY`  
**Runtime evidence:** Label "Trust systems operational"; navigates to audit filter on click  
**Computed evidence:** Pill height 20px (below 44px target)  
**Target-contract comparison:** Semantics match; touch target fail  
**Severity:** S2  
**Implementation implication:** Enforce min-height 44px on pill  
**Remaining uncertainty:** Exact computed success hex not extracted (icon uses class)

---

**Hypothesis ID:** H-TCC-14  
**Claim:** Notification bell exists and is keyboard reachable.  
**Status:** REFUTED  
**Static evidence:** No notification component in `TopHeader.tsx`  
**Runtime evidence:** No notification selector in DOM  
**Target-contract comparison:** Missing entirely  
**Severity:** S1  
**Implementation implication:** Add notification affordance or spec waiver  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-15  
**Claim:** User menu interactive with accessible name.  
**Status:** VALIDATED  
**Static evidence:** `UserMenu.tsx` — `aria-label` from `SHELL_COPY.userMenuOpen`  
**Runtime evidence:** "Account menu" control height 44px  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

### 16.3 Page header

**Hypothesis ID:** H-TCC-16  
**Claim:** Page title H1 32/40/700 #0F172A.  
**Status:** VALIDATED  
**Static evidence:** `Typography variant="h1"` → `Typography.module.css`  
**Runtime evidence:** fontSize 32px, lineHeight 40px, fontWeight 700, color rgb(15,23,42)  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-17  
**Claim:** Subtitle preserves contract copy.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `pageQuestion` uses `?` between clauses  
**Runtime evidence:** Text visible with question marks  
**Target-contract comparison:** Semantic match; punctuation differs  
**Severity:** S3  
**Implementation implication:** Align copy to contract string  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-18  
**Claim:** Humanized relative timestamp without seconds.  
**Status:** REFUTED  
**Static evidence:** `lastUpdated: (iso) => \`Last updated ${new Date(iso).toLocaleString()}\``  
**Runtime evidence:** "Last updated 6/30/2026, 11:29:55 AM"  
**Target-contract comparison:** Machine format with seconds  
**Severity:** S2  
**Implementation implication:** Relative time formatter  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-19  
**Claim:** Urgency copy when N>0.  
**Status:** REFUTED  
**Static evidence:** No urgency copy in components or copy.ts  
**Runtime evidence:** Priority issues present; no "{N} issues require review…" text  
**Target-contract comparison:** Missing  
**Severity:** S1  
**Implementation implication:** Add conditional urgency line tied to `priorityIssues.length`  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-20  
**Claim:** Primary CTA labels conditional on issues / envelope.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `resolvePrimaryAction` — review top issue | view latest envelope | continue onboarding  
**Runtime evidence:** "Review top issue" when issues exist  
**Target-contract comparison:** Third fallback not in contract  
**Severity:** S2  
**Implementation implication:** Restrict fallback set per contract  
**Remaining uncertainty:** no_envelope fixture not re-run in browser audit

---

**Hypothesis ID:** H-TCC-21  
**Claim:** Primary CTA keyboard, focus, 120ms hover, distinct styling.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `.primaryButton` lacks `shared.focusVisible` and motion token  
**Runtime evidence:** CTA height 21px; fontSize 16px  
**Target-contract comparison:** Below 44px target; transition not verified  
**Severity:** S2  
**Implementation implication:** Apply focus + motion tokens + min-height  
**Remaining uncertainty:** Keyboard order not recorded

---

### 16.4 Trust state summary

**Hypothesis ID:** H-TCC-22  
**Claim:** Exactly four cards with contract labels/order.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Four metrics in client; labels differ; order swaps exceptions/authority  
**Runtime evidence:** Four `[data-summary-metric]` elements  
**Target-contract comparison:** Count yes; labels/order no  
**Severity:** S2  
**Implementation implication:** Reorder and rename labels  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-23  
**Claim:** Card surface contract (bg, border, radius, padding, elevation).  
**Status:** REFUTED  
**Static evidence:** CSS uses undefined `--color-bg-card`, `--spacing-24`, `--radius-card`  
**Runtime evidence:** summary card padding 0, boxShadow none, borderRadius 0  
**Target-contract comparison:** All surface properties fail  
**Severity:** S1  
**Implementation implication:** Map to `--sk-*` tokens + elevation  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-24  
**Claim:** Metric value H2 minimum typography.  
**Status:** REFUTED  
**Static evidence:** `.metricValue { font-size: var(--font-size-h3) }` — alias undefined  
**Runtime evidence:** Metric span resolves to 16px / 400  
**Target-contract comparison:** Body tier, not H2  
**Severity:** S2  
**Implementation implication:** Use Typography h2 or `--sk-font-size-h2`  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-25  
**Claim:** Value hierarchy exceeds label hierarchy.  
**Status:** REFUTED  
**Runtime evidence:** Label and value both 16px at computed level  
**Target-contract comparison:** Fail  
**Severity:** S2  
**Implementation implication:** Fix typography tokens  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-26  
**Claim:** Authority badge on financial/confidence cards.  
**Status:** VALIDATED  
**Static evidence:** `<AuthorityBadge authority={metric.authority} />` on each card  
**Runtime evidence:** "Authority Deterministic" visible on cards  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-27  
**Claim:** Deterministic badge non-loading.  
**Status:** VALIDATED  
**Static evidence:** Default state populated; no aria-busy on deterministic path  
**Runtime evidence:** Static badge in screenshot  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-28  
**Claim:** Trend/delta indicator on each card.  
**Status:** REFUTED  
**Static evidence:** No delta UI in `TrustStateSummaryRow.tsx`  
**Runtime evidence:** No trend elements  
**Target-contract comparison:** Missing  
**Severity:** S1  
**Implementation implication:** Add delta from aggregate client  
**Remaining uncertainty:** Backend delta source

---

**Hypothesis ID:** H-TCC-29  
**Claim:** Drill-down links per card.  
**Status:** REFUTED  
**Static evidence:** No links in summary cards  
**Target-contract comparison:** Missing all four required links  
**Severity:** S1  
**Implementation implication:** Add links per §8 contract  
**Remaining uncertainty:** None

---

### 16.5 Priority queue

**Hypothesis ID:** H-TCC-30  
**Claim:** `Needs review` section exists.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Section title `Priority queue` in copy.ts  
**Runtime evidence:** `[data-priority-queue]` present  
**Target-contract comparison:** Wrong title  
**Severity:** S2  
**Implementation implication:** Rename copy key  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-31  
**Claim:** Issue categories render when data available.  
**Status:** NOT TESTABLE  
**Static evidence:** `buildPriorityIssues` constructs all five severities  
**Runtime evidence:** Default fixture showed benchmark transition only  
**Target-contract comparison:** Data coverage limitation  
**Severity:** SX  
**Implementation implication:** Multi-fixture audit in implementation QA  
**Remaining uncertainty:** Needs combined health/discrepancy fixture

---

**Hypothesis ID:** H-TCC-32  
**Claim:** Rows sorted by severity order.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `sortPriorityIssues` + rank map matches contract  
**Runtime evidence:** Single row — order trivially correct  
**Harness evidence:** level10 test with unsorted fixture  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** Full multi-row runtime not captured

---

**Hypothesis ID:** H-TCC-33  
**Claim:** Severity icon per row.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `IconShield` on all rows — same icon regardless of severity  
**Runtime evidence:** Shield icon present  
**Target-contract comparison:** Icon slot yes; severity differentiation no  
**Severity:** S3  
**Implementation implication:** Severity-specific icons  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-34  
**Claim:** No raw variable leakage.  
**Status:** REFUTED  
**Static evidence:** `commandCenterClient.ts:204` embeds `Comparable_to_previous_value=false`  
**Runtime evidence:** Visible in priority queue explanation  
**Target-contract comparison:** Explicit forbidden copy  
**Severity:** S0  
**Implementation implication:** Replace with approved human copy  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-35  
**Claim:** Status pill and action button separate.  
**Status:** VALIDATED  
**Static evidence:** `PolicyAuthorityPill` + separate `Link` action  
**Runtime evidence:** Both visible per row  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-36  
**Claim:** Row scanability at desktop.  
**Status:** VALIDATED  
**Runtime evidence:** No overlap; bounded width 952px  
**Target-contract comparison:** Match  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

### 16.6 Verified revenue trend

**Hypothesis ID:** H-TCC-37  
**Claim:** Chart or designed empty state.  
**Status:** VALIDATED  
**Static evidence:** Table when points exist; `DataUnavailablePanel` when not  
**Runtime evidence:** Unavailable state shown in default fixture  
**Target-contract comparison:** Empty path exists (quality fails H-TCC-41)  
**Severity:** —  
**Implementation implication:** Chart implementation still required for data path  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-38  
**Claim:** Chart plots verified commerce-backed revenue only.  
**Status:** NOT TESTABLE  
**Static evidence:** Client uses `verifiedRevenueMinor` only  
**Runtime evidence:** No chart; 0 trend points in fixture  
**Target-contract comparison:** Semantics OK in code; chart absent  
**Severity:** SX  
**Implementation implication:** Verify when chart added  
**Remaining uncertainty:** Needs loaded trend fixture

---

**Hypothesis ID:** H-TCC-39  
**Claim:** Chart container card styling.  
**Status:** REFUTED  
**Static evidence:** `.panel` uses broken token aliases  
**Runtime evidence:** No card background/shadow on trend section  
**Target-contract comparison:** Fail  
**Severity:** S2  
**Implementation implication:** Fix tokens + elevation  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-40  
**Claim:** Chart hover/focus tooltip.  
**Status:** NOT TESTABLE  
**Static evidence:** No chart library  
**Runtime evidence:** Table only  
**Severity:** SX  
**Implementation implication:** Chart library selection  
**Remaining uncertainty:** Library TBD

---

**Hypothesis ID:** H-TCC-41  
**Claim:** Empty state dignity.  
**Status:** REFUTED  
**Static evidence:** `sparse_data` variant title "Insufficient data for this operation."  
**Runtime evidence:** Same text visible  
**Target-contract comparison:** Forbidden raw placeholder  
**Severity:** S1  
**Implementation implication:** Use approved copy from contract §10  
**Remaining uncertainty:** None

---

### 16.7 Chart/table grid

**Hypothesis ID:** H-TCC-42  
**Claim:** Main container max-width 1280 centered, padding 32.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `ResponsiveShell.main` max-width + padding 32px  
**Runtime evidence:** Main content area ~952px inside shell (1280 - sidebar)  
**Target-contract comparison:** Shell main padding validated; inner grid narrower  
**Severity:** S3  
**Implementation implication:** Confirm content width math  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-43  
**Claim:** 24px gap between chart and table.  
**Status:** REFUTED  
**Runtime evidence:** `gridTwo` gap `normal` (0)  
**Static evidence:** CSS sets `gap: var(--spacing-24)` but alias undefined  
**Severity:** S3  
**Implementation implication:** Use `--sk-space-6`  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-44  
**Claim:** Column ratio 48–52% @ ≥1280.  
**Status:** REFUTED  
**Runtime evidence:** 184px + 768px ≈ 19.3% / 80.7%  
**Static evidence:** `grid-template-columns: 1fr 1fr` overridden by content min-width  
**Severity:** S2  
**Implementation implication:** `minmax(0,1fr)` + constrain channel table  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-45  
**Claim:** No page-level horizontal overflow.  
**Status:** REFUTED (mobile/tablet) / VALIDATED (desktop/wide)  
**Runtime evidence:** `overflow-by-viewport.json`  
**Static evidence:** `.channelTable { min-width: 768px }`  
**Severity:** S2  
**Implementation implication:** Responsive table containment  
**Remaining uncertainty:** None

---

### 16.8 Channel trust table

**Hypothesis ID:** H-TCC-46  
**Claim:** All required columns.  
**Status:** VALIDATED  
**Static evidence:** Eight `<th>` headers in `ChannelTrustTableCard.tsx`  
**Runtime evidence:** Headers visible in screenshot  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-47  
**Claim:** Header/cell alignment.  
**Status:** PARTIALLY VALIDATED  
**Runtime evidence:** Table scrolls horizontally inside wrap  
**Severity:** S3  
**Implementation implication:** Column width tokens  
**Remaining uncertainty:** Bounding box per-cell not recorded

---

**Hypothesis ID:** H-TCC-48  
**Claim:** Headers don't wrap destructively @ desktop.  
**Status:** NOT TESTABLE  
**Runtime evidence:** Table forced wide; headers single-line in capture  
**Severity:** SX  
**Implementation implication:** Re-test after grid fix  
**Remaining uncertainty:** Narrow column layout

---

**Hypothesis ID:** H-TCC-49  
**Claim:** Row height 56/64px.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** No explicit row height on channel rows  
**Severity:** S3  
**Implementation implication:** Apply dense row token  
**Remaining uncertainty:** Exact px not measured

---

**Hypothesis ID:** H-TCC-50  
**Claim:** Channel labels not misleading link style.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `<Link>` on channel name — default link styling  
**Severity:** S2  
**Implementation implication:** Use row navigation pattern or plain text + explicit action  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-51  
**Claim:** Discrepancy % + status badge.  
**Status:** REFUTED  
**Static evidence:** `{row.discrepancyRateBps} bps` only  
**Severity:** S2  
**Implementation implication:** Format % + Rejected/Flagged/Within tolerance  
**Remaining uncertainty:** Threshold labels from backend

---

**Hypothesis ID:** H-TCC-52  
**Claim:** Bayesian column consistent representation.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Plain text + AuthorityBadge in same cell  
**Severity:** S2  
**Implementation implication:** Single representation pattern  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-53  
**Claim:** Benchmark column consistent representation.  
**Status:** PARTIALLY VALIDATED  
**Same as H-TCC-52 pattern**  
**Severity:** S2  
**Implementation implication:** Normalize benchmark status component  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-54  
**Claim:** Action authority PolicyAuthorityPill.valid states.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Pill renders `row.policyAuthority`  
**Runtime evidence:** Blocked state visible  
**Severity:** —  
**Implementation implication:** Add negative test for auto_executable conflict  
**Remaining uncertainty:** Contradiction fixture not run

---

### 16.9 Lower information architecture

**Hypothesis ID:** H-TCC-55  
**Claim:** Recent TrustEnvelopes below chart/table.  
**Status:** VALIDATED  
**Static evidence:** Second `gridTwo` in `CommandCenterPage.tsx`  
**Runtime evidence:** `[data-recent-trust-envelopes]` in DOM  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-56  
**Claim:** Envelope field coverage.  
**Status:** VALIDATED  
**Static evidence:** id, subject, status, created, authority, audit ref in component  
**Runtime evidence:** Fields present when envelope data exists  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** Empty envelope list in some fixtures

---

**Hypothesis ID:** H-TCC-57  
**Claim:** Audit activity section present.  
**Status:** VALIDATED  
**Static evidence:** `AuditActivityStrip` in page layout  
**Runtime evidence:** `[data-audit-activity-strip]` present  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-58  
**Claim:** Audit item field coverage.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** eventType, occurredAt, tier, result, artifactStatus — no system/source label  
**Severity:** S2  
**Implementation implication:** Add source/system label field  
**Remaining uncertainty:** Backend event schema

---

**Hypothesis ID:** H-TCC-59  
**Claim:** Audit links route correctly.  
**Status:** VALIDATED  
**Static evidence:** Links to `/app/audit` and `?event_id=`  
**Harness evidence:** level10 navigation tests  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

### 16.10 State / motion / accessibility

**Hypothesis ID:** H-TCC-60  
**Claim:** Loading <2s skeleton cards + rows.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Single `Skeleton` block, not card/row decomposition  
**Severity:** S2  
**Implementation implication:** Match skeleton matrix  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-61  
**Claim:** Loading >2s copy exact.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `loadingProgress: 'Loading supervisory aggregate…'`  
**Severity:** S3  
**Implementation implication:** Align copy  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-62  
**Claim:** Loading >8s retry.  
**Status:** VALIDATED  
**Static evidence:** `useCommandCenter` 8s timer + retry button  
**Harness evidence:** level10 delay test  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-63  
**Claim:** Skeleton 1500ms pulse 1.0→0.72.  
**Status:** VALIDATED  
**Static evidence:** `Skeleton.module.css` keyframes  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-64  
**Claim:** No spinner-only async.  
**Status:** VALIDATED  
**Static evidence:** Skeleton + text paths; no spinner in CommandCenterPage loading  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-65  
**Claim:** Trust API error banner copy.  
**Status:** VALIDATED  
**Static evidence:** `trustApiReadFailed` exact string  
**Harness evidence:** level10 trust_api_failed test  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-66  
**Claim:** Kill switch preserves read-only UI.  
**Status:** VALIDATED  
**Harness evidence:** level10 kill_switch test  
**Severity:** —  
**Implementation implication:** None  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-67  
**Claim:** No-priority empty + View all claims link.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `noPriorityIssues` message only  
**Severity:** S2  
**Implementation implication:** Add link to `/app/claims`  
**Remaining uncertainty:** None

---

**Hypothesis ID:** H-TCC-68  
**Claim:** Keyboard reachability.  
**Status:** NOT TESTABLE  
**Static evidence:** Focus styles on nav; gaps on primary CTA  
**Severity:** SX  
**Implementation implication:** Record traversal in implementation QA  
**Remaining uncertainty:** No keyboard recording in this audit

---

**Hypothesis ID:** H-TCC-69  
**Claim:** Focus outline 2px #2563EB / 3px offset.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** `shared.focusVisible` uses `--sk-focus-*` tokens  
**Static gap:** Primary CTA missing class  
**Severity:** S2  
**Implementation implication:** Apply focusVisible to all interactives  
**Remaining uncertainty:** Runtime focus snapshot not captured

---

**Hypothesis ID:** H-TCC-70  
**Claim:** aria-live polite/assertive.  
**Status:** PARTIALLY VALIDATED  
**Static evidence:** Error banner assertive; health/kill-switch polite  
**Severity:** S3  
**Implementation implication:** Audit all status regions  
**Remaining uncertainty:** Not all sections have live regions

---

## 5. Exit gates (directive §22)

| Gate | Status |
|------|--------|
| G-01: H-TCC-01–70 labeled | PASS |
| G-02: Static evidence or documented reason | PASS |
| G-03: Visual hypotheses have screenshots | PASS |
| G-04: Token/geometry computed where applicable | PASS |
| G-05: COMMAND_CENTER_BASELINE_DELTA.md exists | PASS |
| G-06: Deterministic vs commentary separated | PASS |
| G-07: Deltas severity-ranked | PASS |
| G-08: File ownership mapped | PASS |
| G-09: Desktop/tablet/mobile screenshots | PASS |
| G-10: Asset inventory complete | PASS |
| G-11: No product code changes | PASS |
| G-12: Remaining unknowns explicit | PASS |
| G-13: Implementation readiness | PASS |

**Exit verdict:** CONTEXT GATHERED

---

## 6. File inventory (inspected)

```text
src/app/routes/ShellRoutes.tsx
src/app/App.tsx
src/components/shell/AuthenticatedAppShell/*
src/components/shell/SidebarNavigation/*
src/components/shell/TopHeader/*
src/components/shell/TenantSelector/*
src/components/shell/UserMenu/*
src/components/shell/GlobalSystemHealthStrip/*
src/components/shell/MobileBottomNavigation/*
src/components/shell/MoreNavigationSheet/*
src/components/shell/shellNav.module.css
src/components/commandCenter/CommandCenterPage/*
src/commandCenter/commandCenterClient.ts
src/commandCenter/copy.ts
src/commandCenter/types.ts
src/commandCenter/useCommandCenter.ts
src/commandCenter/prioritySeverity.ts
src/commandCenter/permissions.ts
src/components/layout/ResponsiveShell/*
src/components/layout/Typography/*
src/components/layout/Skeleton/*
src/components/layout/PageSurface/*
src/components/trust/AuthorityBadge/*
src/components/trust/PolicyAuthorityPill/*
src/components/trust/DataUnavailablePanel/*
src/shell/navigation.ts
src/shell/copy.ts
src/tokens/tokens.css
src/tokens/index.ts
src/operationalAudit/copy.ts
src/dev/Level10CommandCenterSpecimens.tsx
src/test/level10.harness.test.tsx
src/test/level10.helpers.tsx
```

---

## 7. Cross-reference documents

- **Delta summary:** `COMMAND_CENTER_BASELINE_DELTA.md` (same directory)  
- **Prior Level 10 evidence:** `evidence/Level_10/`  
- **Target contract source:** `COMMAND_CENTER_BASELINE_CONTEXT_INVENTORY_DIRECTIVE.md` (Downloads)  
- **Product spec:** `memory-bank/foundation/01-ui-specification.md` §6 Command Center  

---

## 8. Implementation directive prerequisites (satisfied)

A follow-on implementation CRHAID can now specify, without ambiguity:

1. Token alias remediation scope (`CommandCenter*.module.css`)  
2. Shell chrome alignment (brand, nav active state, notification, header layout)  
3. Page-header semantic completion (urgency, timestamps, CTA sizing)  
4. Summary card contract (order, typography, trends, drill-downs, elevation)  
5. Priority queue copy sanitization (S0) + title rename  
6. Chart vs table decision for verified revenue trend  
7. Grid ratio + overflow containment  
8. Channel table discrepancy and authority columns  
9. Harness extensions for regression on all S0/S1 items  

**No remediation was performed in this audit pass.**
