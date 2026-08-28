# Enterprise Compact Density — Remediation Evidence Pack

**Final Verdict: COMPLETE**

**Path:** `skeldir-ui/evidence/enterprise_compact_density/`

---

## 1. Failure point

Global UX defect: interface rendered at low information density (oversized rows, 24px padding stacks, 64px table rows, 32px page titles) inconsistent with B2B enterprise SaaS norms.

**Root cause (empirical):** Spec-mandated **dimension + spacing tokens**, not browser zoom or base `font-size`.

---

## 2. Remediation strategy (skill-aligned)

| Principle | Decision |
|-----------|----------|
| Design-at-scale | Single token substrate override, not per-page CSS hunts |
| Tripartite intent | Works (attribute wiring), fits (token layer), safe (onboarding stays comfortable) |
| Harness-concurrent | `densityAudit.ts` + `density.harness.test.tsx` |
| Fail-closed | Onboarding explicitly `data-density="comfortable"` |

**Mechanism:** `data-density="enterprise-compact"` on `AuthenticatedAppShell` redefines layout/typography CSS variables in `tokens/density.css`. All components consuming `--sk-*` tokens inherit automatically.

---

## 3. Token deltas (comfortable → compact)

| Token | Comfortable | Compact |
|-------|-------------|---------|
| `--sk-font-size-body` | 14px | **13px** |
| `--sk-font-size-h1` | 32px | **24px** |
| `--sk-font-size-h2` | 24px | **20px** |
| `--sk-space-6` / `--spacing-24` | 24px | **16px** |
| `--sk-dimension-table-row-standard` | 64px | **44px** |
| `--sk-dimension-table-row-dense` | 56px | **40px** |
| `--sk-dimension-header-height` | 64px | **56px** |
| `--sk-dimension-nav-item-height` | 44px | **36px** |
| `--sk-dimension-main-padding-*` | 24px | **16px** |
| Supervisory row min-height | 440px | **340px** |
| Chart height | 280px | **220px** |

**Table cell padding** now uses `--sk-dimension-table-cell-padding-*` (8×12 in compact vs 12×16 comfortable).

**Alias fix:** `--spacing-20` → `--sk-space-5` (20px) for Channels table header padding.

---

## 4. Files changed

- `src/tokens/density.css` — compact profile
- `src/tokens/tokens.css` — table cell padding tokens, `--sk-space-5`, `--spacing-20`
- `src/main.tsx` — import density.css
- `src/index.css` — global body typography baseline
- `src/components/layout/Table/Table.module.css` — cell padding tokens
- `src/components/shell/AuthenticatedAppShell/AuthenticatedAppShell.tsx` — density attribute
- `src/audit/densityAudit.ts` — static enforcement
- `src/test/density.harness.test.tsx` — concurrent harness
- `src/test/setup.ts` — load density.css in tests

---

## 5. Empirical validation

```bash
npx vitest run src/test/density.harness.test.tsx \
  src/test/benchmarks.harness.test.tsx \
  src/test/level5.harness.test.tsx \
  src/test/level7.harness.test.tsx \
  src/test/level10.harness.test.tsx
```

| Result | Value |
|--------|-------|
| Test files | 5 passed |
| Tests | **190 passed** |
| Exit code | 0 |

**Harness coverage:**
- Static token audit (14+ checks, meta-negative: compact must not retain 64px rows)
- Shell `data-density="enterprise-compact"` on operational routes
- Onboarding remains `comfortable`
- Table row class wiring under compact shell
- ≥31% theoretical row-height reduction (64→44px)

---

## 6. Exit gates

| Gate | Verdict |
|------|---------|
| Root cause addressed at token layer | **PASS** |
| Product-wide inheritance (no page-by-page patch) | **PASS** |
| Onboarding exception preserved | **PASS** |
| Concurrent falsifiable harness | **PASS** |
| Regression suites green | **PASS** |
