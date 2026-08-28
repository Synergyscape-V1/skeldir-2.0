# CRHAID 3 — Vault Log Readability Remediation — Evidence Pack

**Final Verdict: PASS**

**Authority:** Operator CRHAID 3 + skill/memory-bank optimal approach (chain-of-custody on Overview)  
**Directive ID:** DIR-20260713-VAULT-LOG-READABILITY

**Density / clip correction:** Dedicated 8% Open column + `min-width: 44px` clipped under `overflow: hidden` / `table-layout: fixed`. Open now lives in the Target cell flex row (`flex: 0 0 auto`); ellipsis applies to the ref span only; target `td` uses `overflow: visible`.

---

## Optimal approach (skill + foundation)

| Lens | Choice |
|------|--------|
| Terminal goal | Supervisor can read full actor / action / target on Overview without leave-to-discover |
| Path minimization | Native `title` tooltips (peer ledger pattern) + visible **Open** deep link |
| Affordance fidelity | Row remains clickable; Open is no longer sr-only |
| Truth / custody | Full strings remain in DOM; CSS ellipsis is presentation-only — no `truncateTargetRef` rewrite |
| Negative scope | No Audit Ledger redesign; no expand-row accordion; no Vault log schema changes |

---

## Phase 2 Implementation Directive (executed)

### PILLAR 1 — Negative-Scope Mandate
- No Command Center layout redesign beyond Vault log strip columns
- No new Audit Ledger screens or drawers on Overview
- No expand-row / modal for vault entries (tooltip + Open is sufficient)
- No Tier A noise reinstated on the strip

### PILLAR 2 — Tripartite Intent
- **Technical:** Full-value titles; visible Open → `/app/audit/events/:eventId`
- **Architectural:** Compose with existing strip + forensic display helpers (`formatAuditActorTitle`)
- **Operational:** Fail-closed scan against DOM truncation / sr-only Open / client-id-only actor title

### PILLAR 3 — Hypothesis Ledger
| ID | Hypothesis | Resolution |
|----|------------|------------|
| H-UI-01 | Truncation is CSS + target string rewrite | **Confirmed** — rewrite removed; CSS ellipsis retained |
| H-UI-02 | Actor title was client-id only (wrong primary) | **Confirmed** — title is `display · clientId` |
| H-UI-03 | Open link existed but was sr-only | **Confirmed** — visible Open column |
| H-UI-04 | Peer cells use `title={full}` | **Confirmed** — Claims/Exceptions pattern |

### PILLAR 4 — Disposition Matrix
| Field | Visible (may ellipsis) | Hover title | Navigate |
|-------|------------------------|-------------|----------|
| Actor | Full `actorDisplay` in DOM | display · clientId | row / Open |
| Action | Full forensic label in DOM | full label | row / Open |
| Target | Full `targetRef` in DOM | full ref | row / Open |
| Open | Visible “Open” | aria full purpose | event detail |

### PILLAR 5 — Concurrent Enforcement Harness
- **Positive:** titles + full DOM strings + Open href + navigation
- **Negative:** sabotage detects truncated target, missing titles, sr-only Open, client-id-only title
- **Meta-negative:** sabotage fails while live scan empty

### PILLAR 6 — Exit Gates

| Gate | Method | Output | Verdict |
|------|--------|--------|---------|
| G-01 Full actor in DOM + title | Query markers | title contains display | **PASS** |
| G-02 Full action in DOM + title | Query markers | title === text | **PASS** |
| G-03 Full target in DOM + title | Query markers | no ellipsis rewrite | **PASS** |
| G-04 Visible Open link | `data-audit-entry-open` | href `/app/audit/events/…` | **PASS** |
| G-05 Navigation | userEvent click | lands on event path | **PASS** |
| G-06 Negative-scope | Diff | strip-only | **PASS** |
| G-07 Harness non-vacuity | Sabotage | violations > 0 | **PASS** |
| G-08 Final | All | — | **PASS** |

---

## Code delta

| File | Change |
|------|--------|
| `AuditActivityStrip.tsx` | Titles, full target, visible Open column |
| `auditActivityDisplay.ts` | `formatAuditActorTitle`; remove target truncate usage |
| `CommandCenterSubcomponents.module.css` | Open column + link styles; rebalanced widths |
| `copy.ts` | `openAuditEntry` / aria |
| `vaultLogReadabilityScan.ts` | Integrity + sabotage |
| `vaultLogReadability.harness.test.tsx` | Pos/neg/meta-neg |

---

## Harness run

```
npx vitest run src/test/vaultLogReadability.harness.test.tsx src/test/auditActivityStrip.harness.test.tsx
→ Test Files  2 passed (2)
→ Tests      13 passed (13)
```
