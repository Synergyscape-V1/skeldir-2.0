# Level 6 Implementation Evidence Pack

**Directive:** CRHAID Level 6 — First Trust Object Generation  
**Corrective directive:** CRHACAD Level 6 — First Trust Object Generation (Iteration II)  
**Implementation root:** `c:\Users\ayewhy\Frontend_4\skeldir-ui`  
**Evidence cut:** 2026-06-28  
**Composite gate command:** `npm run audit:level6`

---

## 1. Final Verdict

**COMPLETE — Iteration II (CRHACAD remediation)**

Level 6 Pass I established onboarding Steps 5–6, the first TrustEnvelope generation client boundary, prerequisite-gated state machine, idempotent generation, minimum safe summary, Step 6 governance composition, L7+ negative-scope enforcement, and L0–L5 regression safety. An independent forensic audit **REJECTED** Pass I for six blockers (payload budget, confidence shape, structural hierarchy, schema/payload failure phases, secret-scan boundary, interaction a11y proof).

Iteration II surgically remediates every blocker without rebuilding the substrate. Falsifiable validation: `npm run audit:level6` exit **0** on 2026-06-28 after remediation.

| Metric | Pass I | Iteration II |
|--------|--------|--------------|
| L6 harness tests | 21/21 | **38/38** |
| Composite harness (L1–L6) | 170/170 | **187/187** |
| L6 scope scan | 20 files / 0 | **21 files / 0** |
| Secret scan | 284 files / 0 (L6 evidence excluded) | **286 files / 0** (includes `evidence/Level_6/`) |
| Visual PNGs | 40 | **52** (13 specimens × 4 viewports) |
| Integrity sabotage probes | 10/10 | **20/20** |

**Level 7 advancement:** Permitted only after independent review of this pack and confirmation that Iteration II blockers are closed.

---

## 2. Independent Audit Intake (Pass I REJECT)

**Source:** `evidence/Level_6/Level_6_independent_forensic_audit_report.md`  
**Verdict:** REJECT — advancement to Level 7 prohibited.

### 2.1 Blockers mapped to corrective actions

| Blocker ID | Finding | CA | Remediation artifact |
|------------|---------|-----|----------------------|
| F-L6-BLOCKER-01 | No summary payload-size budget | CA-L6-01 | `summaryValidation.ts` — `MAX_SUMMARY_PAYLOAD_BYTES = 8192`; `measureSerializedPayloadBytes`; fail-closed before hydration |
| F-L6-BLOCKER-02 | Probabilistic confidence shape absent | CA-L6-04, CA-L6-05 | Extended summary contract + `hasProbabilisticConfidenceShape`; naked-scalar rejection; shaped UI in `ConfidenceRegion` |
| F-L6-BLOCKER-03 | Structural truth hierarchy unproven | CA-L6-06, CA-L6-07 | `data-authority-tier` regions; h2/h3 heading hierarchy; DOM-order harness tests |
| F-L6-BLOCKER-04 | Schema/payload failure states incomplete | CA-L6-03 | Distinct phases: `generation_schema_invalid`, `generation_payload_oversized`, `generation_payload_rejected` |
| F-L6-BLOCKER-05 | Secret scan excludes `evidence/Level_6/` | CA-L6-08 | `SCAN_ROOTS` extended; `level6.harness.test.tsx` in exclude list |
| F-L6-BLOCKER-06 | L6 interaction a11y incomplete | CA-L6-09 | Progress-rail focus, mobile accordion keyboard, live-region behavioral tests, retry keyboard |

Additional corrective actions implemented: **CA-L6-02** (forbidden-field runtime rejection), **CA-L6-10** (expanded sabotage), **CA-L6-11** (visual regeneration), **CA-L6-12** (this evidence pack).

---

## 3. Local Environment

| Field | Value |
|-------|-------|
| OS | Windows 10.0.26200 |
| Node | via project `package.json` toolchain |
| Package manager | npm |
| Browser (visual) | Playwright Chromium |
| Dev server port (L6 visual) | 5202 |

---

## 4. Commands Executed (Iteration II)

```text
npm run audit:level6
```

Decomposed stages (all **PASS**, exit 0):

```text
npm run build
npm run audit:level0          → tokens 184/0, scope 26/0, financial 100/0, harness 36/36
npm run audit:level1:scope
npm run audit:level2:scope
npm run audit:level3:scope
npm run audit:level3:privacy
npm run audit:level4:scope
npm run audit:level4:secret   → 286 files / 0 violations
npm run audit:level5:scope
npm run audit:level6:scope    → 21 files / 0 violations
vitest run L1–L6 harness     → 187/187 pass (38 L6)
npm run evidence:visual:level6 → 52 PNGs
```

Independent spot checks:

```text
npx vitest run src/test/level6.harness.test.tsx  → 38/38 pass
npx tsx src/audit/cli/run-level6-scope-scan.ts   → 21 files, 0 violations
npx tsx src/audit/cli/run-secret-scan.ts         → 286 files, 0 violations
```

---

## 5. Level 0–5 Regression Results

**PASS** — unchanged from Pass I. Composite audit includes L1–L5 scope scans, privacy scan, secret scan, and harness regressions with zero violations.

---

## 6. Iteration II Implementation Inventory (delta)

### 6.1 New: Summary transport boundary (`src/firstTrustEnvelope/summaryValidation.ts`)

| Export | Role |
|--------|------|
| `MAX_SUMMARY_PAYLOAD_BYTES` | Hard 8192-byte budget (CA-L6-01) |
| `FORBIDDEN_SUMMARY_FIELDS` | Runtime forbidden-field list (CA-L6-02) |
| `measureSerializedPayloadBytes` | JSON + TextEncoder byte measurement |
| `detectForbiddenSummaryFields` | Pre-hydration forbidden-key detection |
| `validateSummaryTransportBoundary` | Fail-closed gate: forbidden → size → schema → confidence shape |
| `hasProbabilisticConfidenceShape` | Interval + method/context required when available |
| `isNakedScalarConfidence` | Detects available confidence without shape |
| `createOversizedSummaryFixture` | Sabotage fixture for harness/integrity probes |

### 6.2 Modified: Client boundary (`firstTrustEnvelopeClient.ts`)

- `createFirstTrustEnvelopeClient` wraps transport responses through `validateSummaryTransportBoundary` before returning to UI.
- Oversized/forbidden/naked-scalar payloads convert to typed failure outcomes — never hydrate summary.
- `getExistingFirstEnvelope` returns `null` when stored envelope fails boundary (fail-closed load).

### 6.3 Modified: Types and state machine

- `GenerationUiPhase`: added `generation_schema_invalid`, `generation_payload_oversized`, `generation_payload_rejected`.
- `GenerationOutcome`: added `first_envelope_payload_oversized`, `first_envelope_forbidden_payload_fields`.
- `FirstTrustEnvelopeSummary`: confidence shape fields (`confidenceMethodOrContext`, `intervalLower`, `intervalUpper`, `credibleInterval`, `uncertaintyBand`, `qualitativeProbabilisticState`, `sampleOrSourceContext`).
- `step5StateMachine.ts`: explicit phase mapping; `mapValidationFailureToPhase`; `isGenerationErrorPhase`.

### 6.4 Modified: Summary UI (`FirstTrustEnvelopeSummary/`)

- Authority-tier regions: `deterministic-primary`, `model-output`, `probabilistic-subordinate`, `policy-governance`, `audit-reference`, `metadata-subordinate`.
- Primary verified revenue in h2 region; subordinate fields in h3 regions.
- `ConfidenceRegion`: renders interval/uncertainty/method — never bare `available` scalar.
- CSS visual weight: primary region accent border; metadata subordinate styling.

### 6.5 Modified: Step 5 UI (`GenerateFirstTrustEnvelopeStep/`)

- Error phases include schema/payload failures via `isGenerationErrorPhase`.
- Retry label on generate button after terminal errors; submit lock released on error phases.

### 6.6 Modified: Audit substrate

| Change | Detail |
|--------|--------|
| `secretScan.ts` | `evidence/Level_6/` in `SCAN_ROOTS`; `level6.harness.test.tsx` excluded |
| `level6NegativeScopeScan.ts` | 20 integrity probes; expanded string sabotage (rawEnvelope, signedPayload, naked scalar, uniform-row collapse) |

### 6.7 Modified: Harness and visual

| Artifact | Iteration II detail |
|----------|---------------------|
| `level6.harness.test.tsx` | **38 tests** — transport boundary, hierarchy DOM, failure phases, a11y keyboard/live-region, secret scan root |
| `Level6TrustGenerationSpecimens.tsx` | Fixtures: `payload-oversized`, `schema-invalid`, `confidence-available` |
| `capture-level6-visual-evidence.ts` | **52 PNGs** (13 specimens × 4 viewports) |

---

## 7. Summary-Only Transport Boundary Evidence (CA-L6-01, CA-L6-02)

| Control | Method | Result |
|---------|--------|--------|
| Byte budget constant | `MAX_SUMMARY_PAYLOAD_BYTES = 8192` in source | **PASS** |
| Measure before hydrate | `measureSerializedPayloadBytes` + `validateSummaryTransportBoundary` | **PASS** |
| Oversized fail-closed | `createOversizedSummaryFixture()` → `payload_oversized` | **PASS** |
| Forbidden fields rejected pre-hydration | `rawEnvelope`, `signedPayload`, etc. → `forbidden_fields` | **PASS** |
| Client wraps transport | `validateOutcomeEnvelope` in `createFirstTrustEnvelopeClient` | **PASS** |
| UI phase on oversized | Harness: `generation_payload_oversized` after generate | **PASS** |
| UI phase on forbidden | Harness: `generation_payload_rejected` after generate | **PASS** |

**Adversarial probe:** Inject 8192+ byte padding into mock generation result → phase `generation_payload_oversized`, no summary rendered, `step5Complete` remains false.

---

## 8. Probabilistic Confidence Shape Evidence (CA-L6-04, CA-L6-05)

| Control | Method | Result |
|---------|--------|--------|
| Shape fields in contract | `types.ts` interval/uncertainty/method fields | **PASS** |
| Available requires shape | `hasProbabilisticConfidenceShape` + boundary validation | **PASS** |
| Naked scalar rejected | `isNakedScalarConfidence` → `naked_scalar_confidence` failure | **PASS** |
| UI renders interval not scalar | `ConfidenceRegion` + harness DOM assertion | **PASS** |
| Sabotage: "Confidence: 94%" | String probe `shouldDetect: true`; summary source absent | **PASS** |

**Adversarial probe:** Mock envelope with `confidenceStatus: 'available'` but no interval/method → boundary rejects; summary not hydrated.

---

## 9. Structural Truth Hierarchy Evidence (CA-L6-06, CA-L6-07)

| Tier | DOM attribute | Heading | Visual weight |
|------|---------------|---------|---------------|
| Verified revenue | `deterministic-primary` | h2 primary | Accent border, largest heading |
| Attribution model | `model-output` | h3 subordinate | Secondary text + model-output badge |
| Confidence | `probabilistic-subordinate` | h3 subordinate | Probabilistic color on intervals |
| Policy | `policy-governance` | h3 subordinate | PolicyAuthorityPill |
| Audit reference | `audit-reference` | h3 subordinate | Trust link styling |
| Metadata | `metadata-subordinate` | small heading | Muted, bottom border-separated |

**Harness proof:** DOM query returns tiers in order `[deterministic-primary, model-output, probabilistic-subordinate, benchmark-subordinate, policy-governance, audit-reference, metadata-subordinate]`; first heading is H2, remainder H3.

**Sabotage probe:** Uniform `.row`-only markup with `Confidence: 94%` → integrity probe `summary-no-uniform-row-only` **PASS** on clean tree; injected sabotage detected.

---

## 10. Generation State Matrix (updated)

| State / Phase | UI behavior | Verified |
|---------------|-------------|----------|
| `generation_queued` | Status copy + skeleton | Yes |
| `generation_in_progress` | Progress copy + skeleton | Yes |
| `generation_succeeded` | Summary + audit link | Yes |
| `generation_already_exists` | Stable existing envelope | Yes |
| `generation_schema_invalid` | Assertive error + retry | **Yes (II)** |
| `generation_payload_oversized` | Assertive error + retry | **Yes (II)** |
| `generation_payload_rejected` | Assertive error + retry | **Yes (II)** |
| `generation_replay_rejected` | Explicit error copy | Client supports |
| `generation_permission_denied` | Assertive error | Client supports |
| `generation_rate_limited` | Rate limit copy | Client supports |
| `generation_network_error` | Safe copy + retry keyboard | **Yes (II)** |
| `generation_unknown_error` | Sanitized message | Yes |

---

## 11. TrustEnvelope Summary Field Matrix (updated)

| Field | Rendered | Authority / semantics |
|-------|----------|----------------------|
| Verified revenue | Yes — primary tier | `FinancialValue` + deterministic authority |
| Attribution model | Yes — model-output tier | Model-output badge; not financial truth |
| Confidence unavailable | Yes — probabilistic-subordinate tier | `DataUnavailablePanel` + reason |
| Confidence available | Yes — shaped region | Interval, uncertainty, method/context — **not bare status** |
| Policy authority | Yes — governance tier | `PolicyAuthorityPill` |
| Audit reference | Yes — audit tier | Deep link `/app/audit?eventId=…` |
| Envelope ID / timestamp / hashes | Yes — metadata tier | Subordinate visual weight |
| Full JSON / export / verify | **No** | Negative scope enforced |

---

## 12. Privacy / Secret / Evidence Safety (CA-L6-08)

| Scan | Files | Violations |
|------|-------|------------|
| Privacy (L3) | project scope | 0 |
| Secret (L4+) | **286** (includes `evidence/Level_6/`) | **0** |
| Harness secret-root test | `runSecretScan()` in L6 harness | **PASS** |

Fixes F-L6-BLOCKER-05: Level 6 evidence directory now inside proof boundary.

---

## 13. Negative Scope Evidence

| Scan | Files | Violations |
|------|-------|------------|
| Level 6 scope | **21** | 0 |
| L7+ routes/surfaces in L6 dirs | — | 0 |
| Step 5 detail leaks | — | 0 |
| `fetch(` in Step 5/6 UI | — | 0 |

---

## 14. Visual Artifact Index (CA-L6-11)

**Location:** `evidence/Level_6/visual/`  
**Index:** `evidence/Level_6/visual/visual-artifact-index.json`  
**Count:** **52 PNGs** (13 specimens × 4 viewports)

| Specimen | Viewports | Notes |
|----------|-----------|-------|
| step5-locked-commerce | mobile, tablet, desktop, wide | Prerequisites |
| step5-waiting-event | mobile, tablet, desktop, wide | Waiting for verified event |
| step5-ready | mobile, tablet, desktop, wide | Ready to generate |
| step5-generation-success | mobile, tablet, desktop, wide | Success summary |
| step5-generation-failed | mobile, tablet, desktop, wide | Network error |
| **step5-payload-oversized** | mobile, tablet, desktop, wide | **New (II)** |
| **step5-schema-invalid** | mobile, tablet, desktop, wide | **New (II)** |
| **step5-confidence-available** | mobile, tablet, desktop, wide | **New (II)** — hierarchy + shape |
| step5-already-generated | mobile, tablet, desktop, wide | Idempotent state |
| step6-default | mobile, tablet, desktop, wide | Step 6 active |
| step6-permission-denied | mobile, tablet, desktop, wide | Fail-closed permissions |
| shell-onboarding-step5 | mobile, tablet, desktop, wide | Full shell |
| shell-onboarding-step6 | mobile, tablet, desktop, wide | Full shell |

---

## 15. Accessibility Evidence (CA-L6-09)

| Requirement | Method | Result |
|-------------|--------|--------|
| Generate / retry accessible name | Role + label tests | **PASS** |
| Disabled reason association | `aria-describedby` + sr-only | **PASS** |
| Generation status live region | `[data-generation-status]` assertive on error | **PASS (II)** |
| Progress rail keyboard | Focus + Enter on Step 5 button | **PASS (II)** |
| Mobile accordion keyboard | Enter toggles `aria-expanded`; region appears | **PASS (II)** |
| Retry after network error | Keyboard Enter on retry → success | **PASS (II)** |
| Audit link accessible name | `Audit event {id}` | **PASS** |

---

## 16. Sabotage-Control Evidence (CA-L6-10)

### 16.1 Integrity probes (clean tree)

`runLevel6IntegritySabotageProbes()` — **20/20 PASS**

Includes Pass I probes plus: authority-tier regions, no uniform-row-only summary, no naked confidence scalar, payload budget constant, forbidden-field rejection, oversized rejection, probabilistic shape requirement, payload-oversized/schema-invalid phases, forbidden-field list completeness, oversized measurement exceeds budget.

### 16.2 String sabotage (injected violations)

Probes detect: L7+ routes, export/verify/copy API, JSON viewer, `fetch(`, platform-claim-as-truth, raw backend stack, **`rawEnvelope`**, **`signedPayload`**, **`envelopeJson`**, **`Confidence: 94%`**, **uniform `.row` collapse**.

Allowed patterns must not false-positive: `data-authority-tier`, `MAX_SUMMARY_PAYLOAD_BYTES`, `Generate first TrustEnvelope`, `buildAuditReferenceHref`.

### 16.3 Secret sabotage

`runSecretSabotageProbes(SECRET_SABOTAGE_SAMPLES)` — leak detectors **PASS**.

---

## 17. Hypothesis Ledger — Iteration II

| ID | Hypothesis | Result | Disposition |
|----|------------|--------|-------------|
| H-L6-II-01 | Payload budget absent (Blocker 01) | CONFIRMED at audit | **REMEDIATED** — 8192-byte gate |
| H-L6-II-02 | Confidence shape absent (Blocker 02) | CONFIRMED at audit | **REMEDIATED** — shape contract + UI |
| H-L6-II-03 | Hierarchy unproven (Blocker 03) | CONFIRMED at audit | **REMEDIATED** — authority tiers + DOM tests |
| H-L6-II-04 | Schema/payload phases missing (Blocker 04) | CONFIRMED at audit | **REMEDIATED** — distinct phases/outcomes |
| H-L6-II-05 | L6 evidence outside secret scan (Blocker 05) | CONFIRMED at audit | **REMEDIATED** — SCAN_ROOTS extended |
| H-L6-II-06 | A11y proof partial (Blocker 06) | CONFIRMED at audit | **REMEDIATED** — keyboard + live-region tests |
| H-L6-II-07 | Pass I substrate must be preserved | CONFIRMED | **PASS** — surgical diff only |
| H-L6-II-08 | L7+ still blocked | CONFIRMED | **PASS** — scope scan 0 violations |
| H-L6-II-09 | L0–L5 regressions hold | CONFIRMED | **PASS** — composite green |
| H-L6-II-10 | Remediation claims vacuous | REFUTED | **PASS** — 38 L6 tests + 20 integrity probes |

---

## 18. Adversarial Audit Methodology — Iteration II

### 18.1 Intake

1. Read CRHACAD directive and independent REJECT report blockers F-L6-BLOCKER-01 through 06.
2. Map each blocker to corrective action CA-L6-01 through CA-L6-12.
3. Preserve Pass I substrate; change only defective invariants.

### 18.2 Implementation verification

1. **Static boundary proof:** `summaryValidation.ts` exports budget, forbidden fields, shape validators — grep + integrity probes.
2. **Runtime fail-closed proof:** Harness injects oversized, forbidden, naked-scalar, and schema-invalid payloads; asserts phase + no summary hydration.
3. **Structural proof:** DOM query for `[data-authority-tier]` order; heading level assertions; sabotage collapse probe.
4. **Regression proof:** Full `npm run audit:level6` including L0–L5 stages.
5. **Evidence boundary proof:** Secret scan file count increased (286 vs 284) with `evidence/Level_6/` included.
6. **Interaction proof:** user-event keyboard tests on progress rail, accordion, retry, and live-region attributes.

### 18.3 Self-adversarial checks performed

| Attack | Expected | Observed |
|--------|----------|----------|
| 5MB-equivalent padded summary | `generation_payload_oversized` | **PASS** |
| Transport returns `rawEnvelope` | `generation_payload_rejected` | **PASS** |
| Available confidence without interval | Boundary reject; no summary | **PASS** |
| Collapse all fields to uniform `.row` | Sabotage probe fails on injected sample | **PASS** |
| Secret in `evidence/Level_6/` | Scan includes directory; 0 violations | **PASS** |
| Double-click during error retry | Single in-flight guard preserved | **PASS** |

---

## 19. Exit Gate Verdicts (Iteration II)

| Gate | Verdict | Evidence |
|------|---------|----------|
| EG-L6-1 Step 5 route + prerequisite gate | **PASS** | §7 Pass I + unchanged |
| EG-L6-2 Generation state machine | **PASS** | §10 — distinct schema/payload phases |
| EG-L6-3 Idempotency safety | **PASS** | Pass I §17 |
| EG-L6-4 Summary semantics | **PASS** | §11 |
| EG-L6-5 Audit reference integrity | **PASS** | Pass I §16 |
| EG-L6-6 Truth hierarchy | **PASS** | §9 — authority tiers + DOM order |
| EG-L6-7 Step 6 governance | **PASS** | Pass I §18 |
| EG-L6-8 Privacy/secret safety | **PASS** | §12 — L6 evidence in scan |
| EG-L6-9 No L7+ leakage | **PASS** | §13 |
| EG-L6-10 L0–L5 regression | **PASS** | §5 |
| EG-L6-11 Visual + a11y | **PASS** | §14–15 |
| EG-L6-12 Non-vacuous harness | **PASS** | §16 — 38 tests, 20 probes |
| **EG-L6-13 Summary transport budget** | **PASS** | §7 — **new (II)** |
| **EG-L6-14 Confidence probabilistic shape** | **PASS** | §8 — **new (II)** |
| **EG-L6-15 Forbidden-field rejection** | **PASS** | §7 — **new (II)** |

---

## 20. Remaining Risks / Forward Obligations

| Item | Owner | Notes |
|------|-------|-------|
| Backend TrustEnvelope OpenAPI contract | B2.5 | Frontend boundary ready; mock transport until HTTP contract |
| HTTP transport swap | B2.5+ | Client wrapper validates all responses at boundary |
| TrustEnvelope list/detail | L7+ | Explicitly blocked |
| Export / verify signature | L9 | Explicitly blocked |
| Independent re-audit of Iteration II | Reviewer | This pack is implementer evidence; third-party confirmation recommended before L7 |

---

## 21. Reproduction

```bash
cd skeldir-ui
npm run audit:level6
```

Expected: build success; all scope/privacy/secret scans 0 violations; **187** harness tests pass (**38** Level 6); **52** visual PNGs written to `evidence/Level_6/visual/`.

---

## 22. Evidence Self-Scan Confirmation

This pack uses placeholder identifiers only (`trust_envelope_01`, `aud_te_001`, `hash_placeholder_semantic`, etc.). No raw emails, IPs, tokens, or webhook payloads embedded. Reproducible via `npm run audit:level6` from `skeldir-ui/`.
