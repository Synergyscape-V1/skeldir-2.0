# Probabilistic Authority Marker Remediation — Evidence Pack

**Final Verdict: PASS**

**Authority:** Validated hypothesis (interval without inline Probabilistic markers) + Design Implementation Skill + UI Spec § AuthorityBadge invariant  
**Directive ID:** DIR-20260716-PROBABILISTIC-AUTHORITY-INLINE  
**Commercial polish definition (cycle):** Epistemic authority must be glanceable at skim speed. Available confidence intervals never share the deterministic success/green register. Every available posterior carries an inline `AuthorityBadge authority="probabilistic"` without hover.

---

## Phase 0 — Implementation brief

| Lens | Resolution |
|------|------------|
| Terminal goal | Supervisor never skims a Bayesian interval as verified/deterministic fact |
| Adjacent surfaces | Trust Index confidence cell (text AuthorityBadge); Budget Detail confidence chip; Claims CRHAID 4 disposition column |
| Hard constraints | No DataUnavailablePanel in ledger column; no Exact·/Wide· prefixes; no BayesianStatusBadge collapse; text-only AuthorityBadge in dense ledger; fill reserved `fieldValueWithChip` on TrustEnvelope Detail |
| Hypotheses | H-UI-INTERVAL-01 (ledger): confirmed → remediate; H-UI-INTERVAL-02 (detail empty chip slot): confirmed → remediate; H-UI-INTERVAL-03 (detail skim-as-deterministic): refuted by label — still fill chip for substrate coherence |
| Negative scope | No Claim Detail redesign; no Benchmark panel chips; no Trust Index interval reintroduction; no Exact/Wide prefix revival |

### Disposition matrix (available intervals)

| Surface | State | Visible value | Authority marker | Tone |
|---------|-------|---------------|------------------|------|
| Claims Ledger | available_exact / stable / wide | `82–94%` (primary interval text) | table `AuthorityBadge` TrustChip (“Probabilistic”) — same substrate as ExecutiveReliabilityBadge Discrepancy chip | probabilistic (metadata) |
| Trust Index | available / unavailable | AuthorityBadge only | TrustChip Probabilistic / Unavailable (system chrome) | chip |
| Any surface | `AuthorityBadge authority="probabilistic"` | — | **Forced TrustChip early-return** in substrate — no text/size escape | chip |
| Claims Ledger | cold_start / worker / … | cause short label | none (cause label is not a fact-number) | info/error/… |
| TrustEnvelope Detail | available | `[0.82, 0.94]` + posterior % | chip `AuthorityBadge` Probabilistic in reserved slot | chip tone |
| TrustEnvelope Detail | unavailable / delayed | DataUnavailablePanel / delayed copy | no fabricated interval | — |

---

## Phase 2 — What changed

| File | Change |
|------|--------|
| `claims/confidenceLedgerDisplay.ts` | available_* tones → `probabilistic` (never success green) |
| `ClaimsLedgerTableCells.tsx` | stacked interval + text AuthorityBadge on available rows |
| `ClaimsLedgerTableCells.module.css` | `.confidenceCell` stack layout |
| `TrustEnvelopeDetailConfidencePanel.tsx` | fill `fieldValueWithChip` with Probabilistic AuthorityBadge |
| `audit/claimsConfidenceLedgerScan.ts` | enforce inline authority + probabilistic tone |
| `audit/trustEnvelopeConfidenceAuthorityScan.ts` | new concurrent scan |
| harnesses | positive / negative / meta-negative updated |

---

## Phase 3 — Exit gates

| Gate | Method | Output | Verdict |
|------|--------|--------|---------|
| G1 Claims harness | `vitest run src/test/claimsConfidenceLedger.harness.test.tsx` | 9/9 pass | **PASS** |
| G2 TrustEnvelope harness | `vitest run src/test/trustEnvelopeConfidenceAuthority.harness.test.tsx` | 5/5 pass | **PASS** |
| G3 Ledger architecture | `vitest run src/test/claimsLedgerTable.test.tsx` | 6/6 pass | **PASS** |
| G4 Static claims scan | `scanClaimsConfidenceLedger()` | `[]` | **PASS** |
| G5 Static TE scan | `scanTrustEnvelopeConfidenceAuthority()` | `[]` | **PASS** |
| G6 Meta-negative | sabotage fixtures fail while live passes | non-vacuous | **PASS** |
| G7 Level 8 confidence probe | `confidence-probabilistic-chips` | ok: true | **PASS** |

**Out of scope (observed, not introduced):** Level 8 `claim-executive-summary` / `claim-no-authority-badge` and claim-detail route fixtures fail independently of this remediation.

---

## Spirit-anchor check

- Letter of prior CRHAID 4 (text-only, no chip chrome) preserved via `appearance="text"`.
- Intent of Spec § AuthorityBadge on confidence numbers served: markers are inline and skim-visible.
- Empty `fieldValueWithChip` slots no longer theater — chips are wired.
