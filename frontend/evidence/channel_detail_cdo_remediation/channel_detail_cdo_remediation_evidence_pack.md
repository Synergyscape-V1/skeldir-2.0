# Channel Detail CDO Remediation — Evidence Pack

**Final Verdict: COMPLETE**

**CRHAID:** CRHAID 2 — CDO Audit 1 + Audit 2 remediation  
**Evidence pack path:** `skeldir-ui/evidence/channel_detail_cdo_remediation/`  
**Harness:** `src/test/channelDetailRemediation.harness.test.tsx`, Level 8 channel block, L9/L11 trust-surface rehome

---

## Phase 0 — Implementation brief

| Item | Resolution |
|------|------------|
| Terminal user goal | Marketing Executive defends channel ROI to CFO and reallocates spend without adjudicating attribution models |
| Topology (Audit 1 vs 2) | **Audit 2 wins IA:** no full-page `/channels/:channelId` destination. **Audit 1 content floor** lives in Overview inline expansion (delta, trend, top campaigns, related claims) |
| Doc 1 conflict | UI Spec still lists Channel Detail 8-section route; **CDO audits + CRHAID 2 supersede** for this surface |
| Adjacent contracts | Overview table, Command Center channel links, claim attribution links → expand deep-links |

### Negative scope (binding exclusions)

- Attribution model comparison table
- Bayesian / confidence interval visualization
- Related TrustEnvelopes / TrustEnvelope expansion on channels
- Defensive “deterministic heuristics” copy
- Full-page Channel Detail destination (route retained only as redirect)

---

## Exit gates

| Gate | Method | Actual output | Result |
|------|--------|---------------|--------|
| G-01 Detail page deleted | Static absence of `ChannelDetailPage.tsx` | Files removed | **PASS** |
| G-02 Legacy path redirects | Mount `/app/channels/:id` → `/app/channels?expand=` | remediation + L8 harness | **PASS** |
| G-03 Inline expansion executive core | Revenue delta, reliability, trend, campaigns, claims, actions | positive control | **PASS** |
| G-04 No model comparison | `[data-channel-model-table]` null | negative control | **PASS** |
| G-05 No TrustEnvelope channel surface | expansion/toggle markers null | negative control | **PASS** |
| G-06 Expand toggle collapse | Hide collapses panel | meta-negative control | **PASS** |
| G-07 Money integer-safe | Minor-unit titles + `formatBpsAsPercentOneDecimal` | helper + render | **PASS** |
| G-08 Policy before action | Hold spend disabled when blocked | Paid Social fixture | **PASS** |

### Empirical harness runs

```text
npm test -- --run src/test/channelDetailRemediation.harness.test.tsx \
  src/test/level8.harness.test.tsx src/test/level9.harness.test.tsx \
  src/test/level11.harness.test.tsx src/test/channelsOverview.harness.test.tsx
→ 5 files / 231 tests passed
```

---

## Architecture delivered

| Layer | Path |
|-------|------|
| Expand URL | `src/channels/channelExpandHref.ts` |
| Copy / display / fixtures | `channelInlineCopy.ts`, `channelInlineDisplay.ts`, `channelInlineFixtures.ts` |
| Expansion UI | `src/components/channels/ChannelInlineExpansion/` |
| Overview wiring | `ChannelsOverviewPage`, `ChannelsOverviewTable`, cells, summary drilldowns |
| Route | `LedgerRoutes` — `channels/:channelId` → expand redirect |
| Table substrate | `Table` optional `expandedRowKey` + `renderExpandedRow` |

---

## Disposition (expansion)

| State | Behavior |
|-------|----------|
| Collapsed | Overview row only |
| Expanded (trusted row) | Executive panel |
| Legacy detail URL | Redirect + expand |
| Policy blocked | Hold spend disabled + reason |
| Confidence unavailable | Reliability = Estimated (fail closed, never Verified) |

---

## Adjacent note

Level 10 includes a pre-existing Command Center assertion on `[data-evidence-class-badge]` unrelated to this remediation’s expand-href change; not in CRHAID 2 scope.
