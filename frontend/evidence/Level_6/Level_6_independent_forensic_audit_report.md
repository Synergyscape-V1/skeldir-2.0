# Independent Audit Report — Level 6 First Trust Object Generation Iteration II

**Audit type:** Adversarial forensic independent audit — Level 6 Pass II (corrective-action re-audit)  
**Repository:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Audit date:** 2026-06-28  
**Directive:** Context-Robust Hypothesis-Anchored Independent Audit Directive — Level 6 Iteration II Corrective-Action Re-Audit  
**Auditor posture:** Implementation evidence pack treated as unverified hypotheses; all claims independently reproduced or refuted  

---

## 1. Final Verdict

**ACCEPT**

```
PHASE STATUS:  COMPLETE
ADVANCEMENT:   PERMITTED to Level 7 planning
```

---

## 2. Verdict Rationale

All six Pass I blockers (F-L6-BLOCKER-01 through F-L6-BLOCKER-06) are independently remediated with physical behavioral evidence. `npm run audit:level6` exits **0** on a clean tree. Composite harness **187/187** (L1–L6); Level 6 harness **38/38**. Level 6 scope scan **21 files / 0 violations**. Secret scan **286 files / 0 violations** including `evidence/Level_6/`. Visual capture **52 PNGs** (13 specimens × 4 viewports). Integrity sabotage probes **21/21 PASS** on clean tree.

Runtime summary transport boundary is enforced in `firstTrustEnvelopeClient.ts` via `validateSummaryTransportBoundary` **before** React state hydration. `MAX_SUMMARY_PAYLOAD_BYTES = 8192` with serialized measurement; oversized, forbidden-field, schema-invalid, and naked-scalar confidence payloads fail closed with distinct UI phases. `FirstTrustEnvelopeSummary` encodes seven `data-authority-tier` regions with h2 primary / h3 subordinate heading hierarchy. `ConfidenceRegion` renders interval, uncertainty, method/context — and rejects naked scalars. Step 5/6 keyboard interaction tests cover progress rail, mobile accordion, retry, and live-region assertive behavior. Levels 0–5 remain green. All 12 Pass II exit gates pass. Conditional acceptance is forbidden; none is warranted.

---

## 3. Local Environment

| Field | Value |
|-------|-------|
| Repo path | `c:\Users\ayewhy\Frontend_4\skeldir-ui` |
| Node | v22.22.0 |
| npm | 11.6.2 |
| OS | Windows 10.0.26200 |
| Router | `react-router-dom` v7 |

### Commands executed

| Command | Exit | Result |
|---------|------|--------|
| `npm run audit:level6` (full composite) | **0** | Build + L0–L5 regression + L6 scope + **187/187** tests + **52** PNG capture |
| `npx vitest run src/test/level6.harness.test.tsx` | 0 | **38/38** pass |
| `npx vitest run` (L1–L6 harness files) | 0 | **187/187** pass |
| `runLevel6NegativeScopeScan()` (independent) | — | **21** files, **0** violations |
| `runSecretScan()` (independent) | — | **286** files, **0** violations |
| `runLevel6IntegritySabotageProbes()` (independent) | — | **21/21** pass |
| PNG count on disk | — | **52** in `evidence/Level_6/visual/` |

---

## 4. Corrective Blocker Review

### F-L6-BLOCKER-01 — No summary payload-size budget

| Field | Value |
|-------|-------|
| **Prior blocker** | No `MAX_SUMMARY_PAYLOAD_BYTES`, no serialized-size validation, no oversized outcome |
| **Claimed remediation** | `summaryValidation.ts` with 8192-byte budget; client validates before hydration; `generation_payload_oversized` phase |
| **Independent result** | **Remediated.** `MAX_SUMMARY_PAYLOAD_BYTES = 8192` in `summaryValidation.ts`. `measureSerializedPayloadBytes` + `createOversizedSummaryFixture` exceed budget. Harness test `rejects oversized summary payload fail-closed` confirms `payload_oversized` → `generation_payload_oversized`. Integration test maps oversized transport response to UI phase. Integrity probe `oversized-payload-rejected` passes. Client `validateOutcomeEnvelope` calls `validateSummaryTransportBoundary` before returning summary to hook. |

### F-L6-BLOCKER-02 — Probabilistic confidence shape absent

| Field | Value |
|-------|-------|
| **Prior blocker** | No interval/uncertainty fields; available confidence rendered as bare status string |
| **Claimed remediation** | `hasProbabilisticConfidenceShape`, `isNakedScalarConfidence`, `ConfidenceRegion`, extended summary type fields |
| **Independent result** | **Remediated.** Type and validator include `intervalLower/Upper`, `credibleInterval`, `uncertaintyBand`, `qualitativeProbabilisticState`, `confidenceMethodOrContext`, `sampleOrSourceContext`. Transport boundary rejects naked scalar (`naked_scalar_confidence`). `ConfidenceRegion` renders interval/uncertainty/method when shaped; `ErrorBanner` when not. Harness tests accept shaped confidence and reject naked scalar. Visual test confirms interval text renders and bare `available` status does not. Sabotage detects `Confidence: 94%`. |

### F-L6-BLOCKER-03 — Structural truth hierarchy unproven

| Field | Value |
|-------|-------|
| **Prior blocker** | Uniform `.row` styling; no authority-tier regions; no DOM-order tests |
| **Claimed remediation** | `data-authority-tier` on seven regions; h2/h3 heading hierarchy; CSS region classes |
| **Independent result** | **Remediated.** DOM assertion confirms tier order: `deterministic-primary` → `model-output` → `probabilistic-subordinate` → `benchmark-subordinate` → `policy-governance` → `audit-reference` → `metadata-subordinate`. Heading test: first heading is H2 (verified revenue), all subsequent are H3. Integrity probes `summary-has-authority-tiers` and `summary-no-uniform-row-only` pass. Collapse sabotage (`className={styles.row}` without tiers) fails as expected. |

### F-L6-BLOCKER-04 — Schema/payload failure states incomplete

| Field | Value |
|-------|-------|
| **Prior blocker** | `schema_invalid` collapsed to `unknown_error`; `payload_oversized` absent |
| **Claimed remediation** | Distinct outcomes and UI phases for schema_invalid, payload_oversized, payload_rejected |
| **Independent result** | **Remediated.** `mapGenerationOutcomeToPhase` maps `first_envelope_schema_invalid` → `generation_schema_invalid`, `first_envelope_payload_oversized` → `generation_payload_oversized`, `first_envelope_forbidden_payload_fields` → `generation_payload_rejected`. `mapValidationFailureToPhase` bridges transport validation failures. Harness integration tests assert all three phases on generate click. `step5Complete` remains false on schema_invalid. Alert role present on oversized rejection. |

### F-L6-BLOCKER-05 — Secret scan excludes Level 6 evidence

| Field | Value |
|-------|-------|
| **Prior blocker** | `SCAN_ROOTS` lacked `evidence/Level_6/` |
| **Claimed remediation** | Added `join(ROOT, 'evidence', 'Level_6')` to `SCAN_ROOTS` |
| **Independent result** | **Remediated.** `secretScan.ts` line 10 includes `evidence/Level_6`. Independent scan: **286** files (up from Pass I **284**), **0** violations. Harness test `includes evidence/Level_6 in secret scan roots` passes. |

### F-L6-BLOCKER-06 — L6 interaction accessibility incomplete

| Field | Value |
|-------|-------|
| **Prior blocker** | No progress-rail, accordion, retry keyboard, or live-region behavioral tests |
| **Claimed remediation** | Keyboard tests for progress rail, mobile accordion, retry, live-region |
| **Independent result** | **Remediated.** Harness tests: progress rail Step 5 button focusable + Enter; mobile accordion `aria-expanded` toggle via keyboard + region exposure; retry after network error via keyboard Enter; generation status `[data-generation-status]` has `aria-live="assertive"` and `role="alert"` on error. Region labeling via h2/h3 heading hierarchy (primary h2, subordinate h3 per tier). |

---

## 5. Gate Results

| Gate | Result | Evidence | Failure reason |
|------|--------|----------|----------------|
| 01 — Composite Reproduction | **PASS** | `audit:level6` exit 0; all stages including visual capture | — |
| 02 — Summary-Only Transport Boundary | **PASS** | `validateSummaryTransportBoundary` in client before hook hydration; forbidden/oversized/schema tests | — |
| 03 — Explicit Payload and Schema Failure States | **PASS** | Distinct phases + integration tests for schema_invalid, payload_oversized, payload_rejected | — |
| 04 — Probabilistic Confidence Shape | **PASS** | Shape validator, `ConfidenceRegion`, naked-scalar rejection, visual interval test | — |
| 05 — Structural Truth Hierarchy | **PASS** | Seven `data-authority-tier` regions; h2/h3 hierarchy; collapse sabotage | — |
| 06 — Step 5/6 Existing Substrate Preservation | **PASS** | Step 5/6 routes, prerequisites, idempotency, audit link, governance tests all pass | — |
| 07 — Evidence Scan Boundary | **PASS** | `evidence/Level_6` in SCAN_ROOTS; 286 files / 0 violations | — |
| 08 — Interaction Accessibility | **PASS** | Progress rail, accordion, retry keyboard tests; live-region assertive test | — |
| 09 — No Level 7+ Surface Leakage | **PASS** | L6 scope 21/0; redirect guard; sabotage route probes | — |
| 10 — Prior Phase Regression Safety | **PASS** | L0–L5 green in composite audit | — |
| 11 — Non-Vacuous Harness | **PASS** | 21 integrity probes; expanded string sabotage (payload, scalar, hierarchy) | — |
| 12 — Evidence Pack Reproducibility | **PASS** | 187/187, 38/38, 21 scope, 286 secret, 52 PNG all reproduce | — |

**Gate tally:** 12 PASS · 0 FAIL · 0 INCONCLUSIVE — BLOCKING

---

## 6. Hypothesis Results

| Hypothesis | Result | Evidence | Risk |
|------------|--------|----------|------|
| H-AUDIT-L6-II-01 — Composite proof reproduces green | **Confirmed** | `audit:level6` exit 0; 187/187; 52 PNGs | False completion |
| H-AUDIT-L6-II-02 — Steps 5 and 6 active and ordered | **Confirmed** | OnboardingWizard routes; `canAccessStep(6)` requires envelope | Cosmetic steps |
| H-AUDIT-L6-II-03 — Step 5 prerequisites enforced | **Confirmed** | State machine unit tests for all six prerequisites | Prerequisite bypass |
| H-AUDIT-L6-II-04 — Summary transport boundary runtime-enforced | **Confirmed** | `validateSummaryTransportBoundary` in client wrapper before UI state | Full payload in React state |
| H-AUDIT-L6-II-05 — Payload-size budget real | **Confirmed** | 8192-byte constant; oversized fixture; phase mapping test | 5MB envelope acceptance |
| H-AUDIT-L6-II-06 — Forbidden full-payload fields rejected | **Confirmed** | 16-field denylist; pre-hydration rejection; `generation_payload_rejected` | Strip-after-hydrate |
| H-AUDIT-L6-II-07 — Failure-state machine explicit | **Confirmed** | All required phases in `step5StateMachine.ts`; integration tests | Generic unknown fallthrough |
| H-AUDIT-L6-II-08 — Idempotency intact | **Confirmed** | Double-click counter ≤1; submit lock; retry keyboard test | Duplicate generation |
| H-AUDIT-L6-II-09 — Probabilistic confidence shape enforced | **Confirmed** | Shape validator + `ConfidenceRegion` + naked-scalar rejection | Scalar-as-truth |
| H-AUDIT-L6-II-10 — Structural truth hierarchy encoded | **Confirmed** | `data-authority-tier` DOM order test; h2/h3 hierarchy | Copy-only hierarchy |
| H-AUDIT-L6-II-11 — Summary semantics correct | **Confirmed** | Required fields rendered; no JSON viewer/export | Detail-view leakage |
| H-AUDIT-L6-II-12 — Audit reference reconstructable | **Confirmed** | Link to `/app/audit?eventId=`; missing audit blocks summary | Decorative audit |
| H-AUDIT-L6-II-13 — Step 6 governance preserved | **Confirmed** | Team/agent links; viewer/billing_only fail closed | L4 bypass |
| H-AUDIT-L6-II-14 — Secret/evidence scan includes current evidence | **Confirmed** | `evidence/Level_6` in SCAN_ROOTS; 286/0 | Evidence exclusion |
| H-AUDIT-L6-II-15 — No Level 7+ leakage | **Confirmed** | Scope scan clean; redirect guard blocks L7+ routes | Premature surfaces |
| H-AUDIT-L6-II-16 — Interaction accessibility behaviorally proven | **Confirmed** | Keyboard tests for rail, accordion, retry; live-region test | Source-only a11y |
| H-AUDIT-L6-II-17 — Harness non-vacuous | **Confirmed** | Integrity + string sabotage cover payload/scalar/hierarchy/L7+ | Vacuous harness |
| H-AUDIT-L6-II-18 — Levels 0–5 remain green | **Confirmed** | Composite audit L0–L5 stages all pass | Prior regression |

---

## 7. Summary Transport Boundary Evidence

| Field | Finding |
|-------|---------|
| DTO shape | `FirstTrustEnvelopeSummary` — bounded summary fields only; `ALLOWED_SUMMARY_KEYS` whitelist enforced |
| Runtime validation | `validateSummaryTransportBoundary` in `summaryValidation.ts`; called from `validateOutcomeEnvelope` and `validateExistingEnvelope` in client |
| Payload budget | `MAX_SUMMARY_PAYLOAD_BYTES = 8192`; `measureSerializedPayloadBytes` via `TextEncoder` on JSON serialization |
| Forbidden fields | 16-field `FORBIDDEN_SUMMARY_FIELDS` denylist; `detectForbiddenSummaryFields` runs first in validation pipeline |
| Oversized behavior | `createOversizedSummaryFixture` pads beyond budget; rejected with `payload_oversized`; maps to `generation_payload_oversized`; no summary rendered; `step5Complete` false |
| Hydration boundary | Invalid payloads converted to error outcomes in client **before** hook receives summary; hook state type remains `FirstTrustEnvelopeSummary \| null` — only validated summaries enter |

**Note:** No dedicated literal 5MB fixture test exists; oversized rejection is proven via budget-exceeding fixture on the same `measureSerializedPayloadBytes` code path that would reject any payload > 8192 bytes including multi-megabyte responses.

---

## 8. Failure-State Evidence

| Field | Finding |
|-------|---------|
| Schema invalid | `first_envelope_schema_invalid` → `generation_schema_invalid`; harness integration test; `step5Complete` false |
| Payload oversized | `first_envelope_payload_oversized` → `generation_payload_oversized`; alert role on UI; harness integration test |
| Forbidden fields | `first_envelope_forbidden_payload_fields` → `generation_payload_rejected`; harness integration test |
| Raw error sanitization | `outcomeMapping.ts` — no backend stack traces; network error → `generation_network_error` with retry |

Additional phases confirmed present: `generation_replay_rejected`, `generation_permission_denied`, `generation_rate_limited`, `generation_network_error`, `generation_unknown_error`.

---

## 9. Confidence Shape Evidence

| Field | Finding |
|-------|---------|
| Available confidence | `createAvailableConfidenceSummary` fixture with interval, uncertainty, method, source context; accepted by transport boundary |
| Unavailable/delayed confidence | Requires `confidenceReason`; mock default uses `DataUnavailablePanel` |
| Interval/uncertainty/method | `ConfidenceRegion` renders `credibleInterval`, numeric interval, `uncertaintyBand`, `qualitativeProbabilisticState`, method/source meta |
| Naked scalar rejection | `isNakedScalarConfidence` + transport boundary rejection; UI `ErrorBanner` fallback; sabotage detects `Confidence: 94%`; harness confirms bare `available` status not rendered when shaped data present |

---

## 10. Structural Truth Hierarchy Evidence

| Field | Finding |
|-------|---------|
| DOM order | Primary revenue first; model-output; probabilistic-subordinate; benchmark-subordinate (conditional); policy-governance; audit-reference; metadata-subordinate last |
| Authority tiers | Seven `data-authority-tier` values asserted in harness DOM-order test |
| Heading levels | H2 for verified revenue (primary); H3 for all subordinate regions |
| ARIA/regions | Section `aria-label="First TrustEnvelope summary"`; audit link `aria-label`; mobile accordion `aria-expanded` + named region |
| Visual weight | CSS region classes: `primaryRegion`, `subordinateRegion`, `governanceRegion`, `auditRegion`, `metadataRegion` — distinct from former uniform `.row` |
| Hierarchy sabotage | String sabotage detects uniform-row-only markup without tiers; integrity probe `summary-no-uniform-row-only` passes on clean tree |

---

## 11. Existing Level 6 Preservation Evidence

| Field | Finding |
|-------|---------|
| Step 5 | Route `/app/onboarding/step/5`; generate control; prerequisite gates; success path intact |
| Step 6 | Route `/app/onboarding/step/6`; locked before envelope; team/agent links for owner |
| Prerequisites | All six prerequisites tested in state machine harness |
| Idempotency | Double-click counter ≤1; submit lock; session idempotency key |
| Summary | Required fields render; authority badges; audit link; hash metadata |
| Audit reference | `buildAuditReferenceHref` → `/app/audit?eventId=aud_te_001`; missing audit blocks |
| Governance | viewer/billing_only cannot manage team or create agent keys |

---

## 12. Privacy / Secret / Evidence Safety

| Field | Value |
|-------|-------|
| Scan roots | `src/`, `evidence/Level_4/`, `evidence/Level_5/`, **`evidence/Level_6/`**, `scripts/` |
| Files scanned | **286** |
| Violations | **0** |
| Evidence self-scan | Level 6 evidence pack and visual index included in scan boundary |
| Sabotage result | Secret leak probes fire on controlled samples; clean tree 0 violations |

---

## 13. Negative Scope Evidence

| Surface class | In L6 product code? |
|---------------|---------------------|
| TrustEnvelope list/detail | No |
| `/trust`, `/claims` | No (blocked by redirect guard) |
| Export / verify / copy API | No |
| Budget / exceptions / billing / Command Center | No |
| Route scan | L6 scope: **21 files, 0 violations** |

---

## 14. Regression Evidence

| Phase | Result |
|-------|--------|
| Level 0 | 36/36 harness; tokens/scope/financial clean |
| Level 1 | Scope clean; redirect guard |
| Level 2 | Scope clean |
| Level 3 | Scope + privacy clean |
| Level 4 | Scope + secret clean |
| Level 5 | Scope 49/0; harness 35/35 |

---

## 15. Visual and Accessibility Evidence

| Field | Value |
|-------|-------|
| Artifact count | **52** PNG files |
| Viewports | mobile, tablet, desktop, wide |
| Missing states | Step 5 in-progress dedicated specimen; replay-rejected visual — non-blocking observations |
| Interaction tests | Progress rail keyboard; mobile accordion keyboard; retry keyboard; live-region assertive on error; generate click success; audit link accessible name |

---

## 16. Harness Non-Vacuousness Evidence

### Integrity probes (`runLevel6IntegritySabotageProbes`)

**21/21 PASS** on clean tree — includes envelope validation, no fetch, authority tiers, payload budget constant, forbidden-field rejection, oversized rejection, probabilistic shape requirement, payload-oversized/schema-invalid phases.

### String sabotage (`runLevel6SabotageProbes`)

Detects on injected samples: `/claims`, `/trust/`, export, verify, copy API, JSON viewer, platform-claim-as-truth, fetch in UI, raw stack, `rawEnvelope`, `signedPayload`, `envelopeJson`, `Confidence: 94%`, uniform-row-only summary.

Clean tree passes allowed patterns (`data-authority-tier`, `MAX_SUMMARY_PAYLOAD_BYTES`, audit link, Step 5 copy).

### Sabotage cases covered (directive Eval 11)

| Class | Detector | Clean pass | Sabotage fail |
|-------|----------|------------|---------------|
| Full payload fields | `raw-envelope-field`, `forbidden-fields-rejected` | Yes | Yes |
| Oversized payload | `oversized-payload-rejected` | Yes | Yes |
| Naked scalar confidence | `naked-confidence-scalar`, shape validator | Yes | Yes |
| Truth hierarchy collapse | `uniform-row-only-summary` | Yes | Yes |
| Level 7+ routes | `claims-route`, `trust-route` | Yes | Yes |
| Export/verify/copy | string probes | Yes | Yes |

---

## 17. Critical Findings

No blockers remain. Non-blocking observations:

### OBS-L6-II-01 — Integrity probe count differs from evidence pack claim

| Field | Value |
|-------|-------|
| **Severity** | Informational |
| **Affected files** | `level6NegativeScopeScan.ts` |
| **Evidence** | Independent count: **21** integrity probes pass; evidence pack claimed 20/20 |
| **Consequence** | None — probes are non-vacuous and all pass |

### OBS-L6-II-02 — No literal 5MB fixture test

| Field | Value |
|-------|-------|
| **Severity** | Informational |
| **Affected files** | `summaryValidation.ts`, `level6.harness.test.tsx` |
| **Evidence** | Oversized rejection proven via budget-exceeding padding fixture, not 5MB blob |
| **Consequence** | None — same `measureSerializedPayloadBytes > MAX_SUMMARY_PAYLOAD_BYTES` branch rejects any oversized payload |

---

## 18. Completion Determination

Level 6 is **empirically complete** under the Iteration II corrective-action standard.

The first TrustEnvelope generation substrate remains functionally intact. Step 5 accepts only runtime-validated, bounded summary DTOs. Oversized, forbidden-field, and schema-invalid payloads fail closed before hydration. Confidence preserves probabilistic shape and cannot render as a naked scalar. Truth hierarchy is encoded structurally in DOM, headings, and CSS regions. Level 6 evidence is inside the scan boundary. Step 5/6 interactions are behaviorally accessible. No later surfaces leak. Levels 0–5 remain green. The harness fails under meaningful sabotage while passing on the clean tree.

```
PHASE STATUS:  COMPLETE
ADVANCEMENT:   PERMITTED
```

---

## 19. Required Remediation Before Acceptance

Not applicable — verdict is **ACCEPT**.

---

*End of independent forensic audit — Level 6 Pass II.*
