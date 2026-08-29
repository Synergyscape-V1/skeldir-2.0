# CRHAID 4 — Revenue Claims Confidence Column Remediation — Evidence Pack

**Final Verdict: PASS**

**Authority:** Operator CRHAID 4 + B2.4 semantics (memory-bank §7, §10.1, §16.2)  
**Directive ID:** DIR-20260713-CLAIMS-CONFIDENCE-LEDGER

---

## Optimal approach (skill + foundation)

| Lens | Choice |
|------|--------|
| Terminal goal | Supervisor can triage claims by confidence cause — not a uniform "Low confidence" column |
| Path minimization | Reason-coded short label + `title` tooltip; numeric interval when posterior is available |
| Affordance fidelity | Table stays compact — no `DataUnavailablePanel` in column (existing architecture test preserved) |
| Truth / custody | B2.4 dispositions: cold_start, insufficient_data, worker_failure, timeout, refit_locked, exact-bucket, wide posterior |
| Negative scope | No exceptions-queue routing for cold-start; no channels-table Bayesian badge reuse in claims column |

---

## Phase 2 Implementation Directive (executed)

### PILLAR 1 — Negative-Scope Mandate
- No full `DataUnavailablePanel` in ledger confidence column
- No collapsed `BayesianStatusBadge` → uniform "Low confidence" for all available rows
- No cold-start → exceptions queue routing
- No channels-table redesign

### PILLAR 2 — Tripartite Intent
- **Technical:** `resolveClaimsConfidenceLedgerProjection` maps `ConfidenceShape` → disposition + interval + tooltip
- **Architectural:** Claims column uses dedicated `confidenceLedgerDisplay.ts`; channels keep `confidenceToBayesianStatus`
- **Operational:** Static scan + harness enforce disposition attributes and varied synthetic fixture

### PILLAR 3 — Hypothesis Ledger
| ID | Hypothesis | Resolution |
|----|------------|------------|
| H-UI-01 | All rows collapse via `qualitativeState` containing "moderate/low" | **Confirmed** — removed Bayesian collapse in claims column |
| H-UI-02 | Fixture sets uniform `Moderate uncertainty` on every available row | **Confirmed** — `buildClaimConfidence` varies B2.4 states |
| H-UI-03 | No tooltip / numeric threshold | **Confirmed** — `title` exposes cause + interval; label shows `82–94%`, `Wide · 55–68%`, etc. |
| H-UI-04 | Cold-start indistinguishable from worker failure | **Confirmed** — distinct labels and dispositions |

### PILLAR 4 — Disposition Matrix
| State | Short label | Tooltip | Tone |
|-------|-------------|---------|------|
| available_exact | `Exact · 88–96%` | Exact-bucket posterior + method | success |
| available_stable | `82–94%` | Posterior interval + qualitative | success |
| available_wide | `Wide · 55–68%` | Model disagreement context | warning |
| cold_start | `Cold start` | Expected sparse history | muted |
| insufficient_data | `Insufficient data` | Insufficient for Bayesian fit | muted |
| worker_failure | `Worker failure` | Intervention may be needed | error |
| computation_timeout | `Timeout` | Computation timed out | error |
| refit_locked | `Refit locked` | Eligibility backoff | warning |
| delayed | `Delayed` | Bayesian delayed | warning |

### PILLAR 5 — Concurrent Enforcement Harness
- **Positive:** disposition resolver, interval labels, cold start vs worker failure, no DataUnavailablePanel, live scan empty
- **Negative:** sabotage detects collapsed badge, missing title, removed cold_start case, uniform fixture
- **Meta-negative:** sabotage fails while live scan passes

### PILLAR 6 — Exit Gates

| Gate | Method | Output | Verdict |
|------|--------|--------|---------|
| G1 Unit + harness | `vitest run src/test/claimsConfidenceLedger.harness.test.tsx` | 8/8 pass | **PASS** |
| G2 Architecture regression | `vitest run src/test/claimsLedgerTable.test.tsx` | 6/6 pass | **PASS** |
| G3 Static integrity | `scanClaimsConfidenceLedger()` | `[]` | **PASS** |
| G4 B2.4 triage | Manual matrix row review | Distinct labels per cause class | **PASS** |
| G5 Negative scope | Harness + architecture test | No DataUnavailablePanel in column | **PASS** |

---

## Files touched

| File | Role |
|------|------|
| `src/claims/confidenceLedgerDisplay.ts` | B2.4 disposition resolver + interval formatting |
| `src/claims/copy.ts` | `CLAIMS_CONFIDENCE_LEDGER_COPY` labels and tooltips |
| `src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.tsx` | Reason-coded confidence cell |
| `src/components/claims/ClaimsLedgerTable/ClaimsLedgerTableCells.module.css` | Tone classes |
| `src/claims/claimsClient.ts` | `buildClaimConfidence` varied synthetic states |
| `src/audit/claimsConfidenceLedgerScan.ts` | Integrity + sabotage scan |
| `src/test/claimsConfidenceLedger.harness.test.tsx` | pos/neg/meta-neg harness |
| `src/test/claimsLedgerTable.test.tsx` | Updated unavailable-column assertion |

---

## Test command

```bash
npm test -- --run src/test/claimsConfidenceLedger.harness.test.tsx src/test/claimsLedgerTable.test.tsx
```

**Result:** 14/14 tests passed (2026-07-13).
