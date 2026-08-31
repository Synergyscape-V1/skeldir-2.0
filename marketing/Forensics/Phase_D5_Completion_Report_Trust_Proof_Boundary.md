# Phase D5 Completion Report — Trust Proof Boundary and Legal/Security Surface

**Date:** 2026-05-23
**Scope:** D5 only — Trust Proof Boundary and Legal/Security Surface. **No D6/D8/D9/D10 closure claimed.**
**Branch:** `feat/discoverability-remediation`

---

## 1. Verdict

**PASS — locally.**

| Gate | Result |
|---|---|
| D5.1 Required D5 routes exist as source + built HTML | **PASS** |
| D5.1 Legal placeholder routes carry explicit status + remain noindex | **PASS** |
| D5.1 Footer / legal / proof link policy | **PASS** |
| D5.1 `book-demo` Privacy Policy link resolves to `/privacy` | **PASS** |
| D5.2 Claim-proof registry shape | **PASS** |
| D5.2 Claim-proof anchors exist in built HTML | **PASS** |
| D5.2 High-stakes claim triggers covered by registry | **PASS** |
| D5.3 TrustEnvelope proof page concepts | **PASS** (12/12 required concepts) |
| D5.4 Methodology + AI boundary concepts | **PASS** (`/methodology` 6/6, `/ai-boundary` 6/6) |
| D5.5 Revenue verification / attribution / discrepancy concepts | **PASS** |
| D5.6 Legal/security honesty boundary (no invented compliance) | **PASS** (scanned 112 source files) |
| D5.7 Static HTML + indexability baseline (every proof page) | **PASS** |
| D5.7 Sitemap manifest contains every indexable proof route, excludes legal placeholders | **PASS** |
| D5.8 Local phase vs production closure separation (informational) | **REPORTED** |
| `npm run discoverability:d5` | **PASS** (73 passes, 1 informational warning, 0 failures) |
| `npm run discoverability:d5:negative-controls` | **PASS** (15 passes, 0 failures) |

Prior-phase regression checks (re-run after D5 changes):

| Phase | Result |
|---|---|
| `npm run discoverability:d0` | **PASS** (121 / 0 / 0) |
| `npm run discoverability:d1` | **PASS** (37 / 0) |
| `npm run discoverability:d2` | **PASS** (39 / 0) |
| `npm run discoverability:d3` | **PASS** (51 / 0) |
| `npm run discoverability:d4` | **PASS** (24 / 0) — now also validates all 9 new indexable D5 proof pages |
| `npm run discoverability:d4:negative-controls` | **PASS** (11 / 0) |

---

## 2. Scope Confirmation

D5 only — Trust Proof Boundary and Legal/Security Surface.

No D6 evidence-library architecture, no D8 referral measurement, no D9 production deploy, no D10 governance loop is claimed by this report. D5 was executed under the operating rule that local phase correctness may proceed while production-final closure remains globally blocked.

---

## 3. Global Release Blocker Status

| Field | Value |
|---|---|
| Local branch | `feat/discoverability-remediation` |
| Common ancestor with `origin/main` | `git merge-base origin/main HEAD` → exit code **1** (no merge-base) |
| Mainline integration | **NOT RESOLVED** — unrelated-history reconciliation pending from D4-C2 |
| CI | **Not re-proven in this session** |
| Deploy preview | **Not attached** (no preview URL in environment) |
| Production curl proof for D5 routes | **Not run** |
| **Production-final blocked?** | **YES** — D5 production-final closure remains blocked by the pre-existing global release blocker first identified in the D4-C2 report. D5 introduces no new release defects. |

D5 production-final closure additionally requires:
1. Mainline Git lineage resolved (unrelated-history reconciliation onto `origin/main`),
2. CI green on the mergeable `main`-based branch,
3. Deploy-preview curl proof for the D5 proof routes,
4. Production-equivalent curl proof showing the same static HTML the harness reads.

---

## 4. Files Changed

### New source files (D5 proof routes + helpers)

| File | Purpose |
|---|---|
| `src/app/methodology/page.tsx` | New `/methodology` proof page (deterministic reconciliation, evidence sources, attribution boundaries, discrepancy handling, delayed events, AI boundary). |
| `src/app/ai-boundary/page.tsx` | New `/ai-boundary` proof page (LLMs explain, do not calculate). |
| `src/app/revenue-verification/page.tsx` | New `/revenue-verification` proof page (commerce + payment evidence, reconciliation). |
| `src/app/attribution-methodology/page.tsx` | New `/attribution-methodology` proof page (bounded questions, named assumptions, not causality). |
| `src/app/discrepancy-taxonomy/page.tsx` | New `/discrepancy-taxonomy` proof page (8 classified discrepancy classes). |
| `src/components/discoverability/TrustProofPage.tsx` | Shared D5 proof page layout — header, owner/status/last-reviewed metadata strip, sections, mandatory Limitations section. |
| `src/components/discoverability/LegalPlaceholderPage.tsx` | Shared legal placeholder layout — explicit `legal_review_required` status badge, no invented legal claims. |
| `src/lib/schema/trustProof.ts` | Conservative WebPage + BreadcrumbList JSON-LD for D5 proof routes. |

### Modified source files

| File | Change | Reason |
|---|---|---|
| `src/app/trust-envelope/page.tsx` | Replaced placeholder with full TrustEnvelope spec covering all 11 required concepts + limitations. | D5.3. |
| `src/app/security/page.tsx` | Replaced placeholder with status-taxonomy security page (`implemented` / `partially implemented` / `planned` / `not applicable`). | D5.7 (Security), D5.6 honesty boundary. |
| `src/app/docs/page.tsx` | Replaced placeholder with concepts + availability index linking every D5 proof page. | D5.1 + D5.7. |
| `src/app/api/page.tsx` | Replaced placeholder with API concepts + availability page; explicitly states no live external endpoint. | D5.1 + D5.7 + honesty boundary. |
| `src/app/privacy/page.tsx` | Re-implemented as `LegalPlaceholderPage` with explicit `legal_review_required` status; remains noindex. | D5.1 + D5.6 — never invent legal claims. |
| `src/app/terms/page.tsx` | Same as `/privacy` — `legal_review_required` placeholder. | D5.1 + D5.6. |
| `src/app/gdpr/page.tsx` | Same as `/privacy` — `legal_review_required` placeholder. | D5.1 + D5.6. |
| `src/components/layout/Footer.tsx` | Added `TRUST & METHODOLOGY` column with 6 D5 proof links (Methodology, TrustEnvelope, Revenue Verification, Attribution Methodology, Discrepancy Taxonomy, AI Boundary). Grid widened to 5 columns. Legal/proof labels confirmed wired to canonical routes. | D5.1 + D5.2 (no legal label may target `/resources`). |
| `discoverability.sitemap-manifest.json` | Added 9 new indexable D5 proof paths; kept legal placeholders excluded. | D5.7 + D5.10. |
| `discoverability.routes.json` | Promoted `/trust-envelope`, `/security`, `/docs`, `/api` from `missing_required` → `active` with implementation flags. Added 5 new D5 route entries (methodology, ai-boundary, revenue-verification, attribution-methodology, discrepancy-taxonomy). | D0 parity for new routes. |
| `scripts/discoverability/lib/d2-crawl-graph.mjs` | Removed `/security`, `/docs`, `/api`, `/trust-envelope` from `META_NOINDEX_PUBLIC_PATHS` (they are now indexable proof surfaces). Removed the same paths from the sitemap-forbidden set. | D5.7 vs D2 contract alignment. |
| `package.json` | Added `discoverability:d5` and `discoverability:d5:negative-controls` scripts. | D5 harness wiring. |

### New harness / registry files

| File | Purpose |
|---|---|
| `scripts/discoverability/lib/d5-trust-proof.mjs` | D5 helpers: required-routes lists, required-concepts map, banned-compliance-phrases, page baseline validator, legal placeholder validator, footer link policy validator, book-demo link validator, claim registry shape + anchor validators, high-stakes claim source scanner. |
| `scripts/discoverability-d5-harness.mjs` | D5 harness across Gates D5.1–D5.8. |
| `scripts/discoverability-d5-negative-controls.mjs` | 15 negative-control fixtures proving each validator catches its failure mode. |
| `discoverability.claim-proof-registry.json` | Machine-readable claim-proof registry — 12 high-stakes claims, each mapped to a proof route + anchor + owner + review date. |
| `D5_CLAIM_PROOF_REGISTRY.md` | Human-readable counterpart with field definitions. |

---

## 5. D5 Route Coverage

Built HTML sizes confirm every route is real static content (not a `Loading...` shell):

| Route | Exists? | Indexable? | Static H1 / body? | Review Status | Owner | Built bytes | Result |
|---|---|---|---|---|---|---|---|
| `/privacy` | ✅ | ❌ (noindex by design) | ✅ | `legal_review_required` | Skeldir Operator + Legal | 51,691 | **PASS (placeholder)** |
| `/terms` | ✅ | ❌ (noindex by design) | ✅ | `legal_review_required` | Skeldir Operator + Legal | 51,047 | **PASS (placeholder)** |
| `/gdpr` | ✅ | ❌ (noindex by design) | ✅ | `legal_review_required` | Skeldir Operator + Legal | 51,662 | **PASS (placeholder)** |
| `/security` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Security & Engineering | 69,100 | **PASS** |
| `/methodology` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 68,824 | **PASS** |
| `/ai-boundary` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 63,069 | **PASS** |
| `/trust-envelope` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 74,933 | **PASS** |
| `/revenue-verification` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 63,760 | **PASS** |
| `/attribution-methodology` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 63,707 | **PASS** |
| `/discrepancy-taxonomy` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 66,645 | **PASS** |
| `/docs` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 60,244 | **PASS** |
| `/api` | ✅ | ✅ | ✅ | `technical_disclosure_only` | Skeldir Product Engineering | 58,222 | **PASS** |

The D5 directive's full required-route set is present: `/privacy`, `/terms`, `/security`, `/gdpr`, `/methodology`, `/trust-envelope`, `/docs`, `/api`, `/revenue-verification`, `/attribution-methodology`, `/discrepancy-taxonomy`, plus the additional `/ai-boundary` page that anchors D5-CLAIM-006.

---

## 6. Legal/Security Link Map

| Link label | Source file (label → href) | Resolves to | Correct? |
|---|---|---|---|
| Privacy Policy | `Footer.tsx` `legalLinks` | `/privacy` | ✅ |
| Terms of Service | `Footer.tsx` `legalLinks` | `/terms` | ✅ |
| GDPR | `Footer.tsx` `legalLinks` | `/gdpr` | ✅ |
| Security | `Footer.tsx` `legalLinks` + `footerLinks.product` | `/security` | ✅ |
| Documentation | `Footer.tsx` `footerLinks.support` | `/docs` | ✅ |
| API Reference | `Footer.tsx` `footerLinks.support` | `/api` | ✅ |
| Methodology | `Footer.tsx` `footerLinks.trust` | `/methodology` | ✅ |
| TrustEnvelope | `Footer.tsx` `footerLinks.trust` | `/trust-envelope` | ✅ |
| Revenue Verification | `Footer.tsx` `footerLinks.trust` | `/revenue-verification` | ✅ |
| Attribution Methodology | `Footer.tsx` `footerLinks.trust` | `/attribution-methodology` | ✅ |
| Discrepancy Taxonomy | `Footer.tsx` `footerLinks.trust` | `/discrepancy-taxonomy` | ✅ |
| AI Boundary | `Footer.tsx` `footerLinks.trust` | `/ai-boundary` | ✅ |
| Privacy Policy (book-demo form) | `src/app/book-demo/page.tsx` | `/privacy` (and `out/privacy.html` exists) | ✅ |

**No legal/security/docs/API label points to `/resources`.** Negative control NC-D5-01 explicitly proves the harness catches a Privacy → `/resources` regression.

---

## 7. Claim-Proof Registry Summary

`discoverability.claim-proof-registry.json` contains 12 high-stakes claims; every proof anchor was verified present in the built HTML by the harness. Excerpt:

| ID | Claim (short) | Source route | Risk | Proof route → anchor | Owner | Status |
|---|---|---|---|---|---|---|
| D5-CLAIM-001 | Every ad dollar traced, verified to the source | `/` | high | `/methodology#deterministic-reconciliation` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-002 | Skeldir reconciles platform-reported ad revenue with verified commerce/payment evidence | `/` | high | `/revenue-verification#reconciliation` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-003 | AI Agents and teams execute from confirmed truth | `/` | high | `/ai-boundary#agent-policy` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-004 | Skeldir is deterministic revenue-verification infrastructure that exposes audit-ready financial truth through TrustEnvelopes | `/` | high | `/trust-envelope#what-it-is` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-005 | Deterministic financial truth backed by a provenance chain and semantic truth hash | `/trust-envelope` | high | `/trust-envelope#audit-trail` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-006 | LLMs explain deterministic truth but do not calculate financial truth | `/ai-boundary` | high | `/ai-boundary#llm-does-not-calculate` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-007 | Discrepancies are classified, not averaged | `/methodology` | medium | `/discrepancy-taxonomy#timing-mismatch` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-008 | Attribution models answer bounded questions; they do not prove causality | `/methodology` | medium | `/attribution-methodology#bounded-questions` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-009 | Security posture under explicit status taxonomy; we do not claim certifications we have not earned | `/security` | high | `/security#status-taxonomy` | Skeldir Security & Engineering | technical_disclosure_only |
| D5-CLAIM-010 | Privacy-minimizing within reconciliation engine; "no PII" not asserted globally | `/security` | high | `/security#pii-policy` | Skeldir Security & Engineering | technical_disclosure_only |
| D5-CLAIM-011 | Commerce evidence (Shopify) + payment evidence (Stripe) ingested independently of ad platform | `/revenue-verification` | medium | `/revenue-verification#commerce-evidence` | Skeldir Product Engineering | operator_approved |
| D5-CLAIM-012 | TrustEnvelope confidence status is an enumerated verification state, not probabilistic | `/trust-envelope` | medium | `/trust-envelope#confidence-status` | Skeldir Product Engineering | operator_approved |

**High-stakes trigger coverage** (harness output):

| Trigger | Files containing trigger | Covered by registry? |
|---|---|---|
| `verified` | 22 | ✅ (revenue_verification) |
| `deterministic` | 12 | ✅ (deterministic_truth) |
| `financial truth` | 3 | ✅ (deterministic_truth) |
| `TrustEnvelope` | 10 | ✅ (trust_envelope) |
| `source of truth` | 5 | ✅ (auditability) |
| `audit` | 9 | ✅ (auditability) |
| `no PII` | 2 | ✅ (privacy_no_pii) |
| `commerce evidence` | 5 | ✅ (revenue_verification) |
| `policy authority` | 7 | ✅ (trust_envelope) |
| `AI Agents` | 6 | ✅ (ai_boundary) |

---

## 8. TrustEnvelope Proof Evidence

Built file: `out/trust-envelope.html` (74,933 bytes). Every required TrustEnvelope concept is present as a visible section with an `id="..."` anchor (verified by harness Gate D5.3 and claim-proof anchor validator):

| Required concept | Section id in built HTML |
|---|---|
| Deterministic values | `#deterministic-values` |
| Provenance chain | `#provenance-chain` |
| Semantic truth hash | `#semantic-truth-hash` |
| Artifact hash | `#artifact-hash` |
| Confidence status | `#confidence-status` |
| Benchmark metadata | `#benchmark-metadata` |
| Policy authority | `#policy-authority` |
| Fallback reason | `#fallback-reason` |
| External verification metadata | `#external-verification-metadata` |
| Action authority | `#action-authority` |
| Audit trail | `#audit-trail` |
| Limitations | `#limitations` |

The page explicitly states **what is not guaranteed yet** in its Limitations section: "It does not promise a live external API contract; concrete API availability is documented separately on /api and the integration documentation surface on /docs."

---

## 9. Methodology / AI Boundary Evidence

`/methodology` (`out/methodology.html`, 68,824 bytes) explains:
- deterministic reconciliation engine produces authoritative numbers,
- LLMs do not compute financial truth,
- attribution models answer bounded questions, not causality,
- discrepancies are classified,
- delayed events trigger restatement with audit trail,
- limitations (unconnected revenue, no causality, unsupported platforms).

`/ai-boundary` (`out/ai-boundary.html`, 63,069 bytes) further isolates the LLM boundary:
- `#llm-does-not-calculate` section explicitly says "the model explains; it does not calculate the truth";
- LLMs are bounded to the TrustEnvelope they reference (no extrapolation);
- AI Agents must treat the deterministic value and confidence status as authoritative and the LLM-generated explanation as advisory.

Negative control NC-D5-08 verifies the harness catches a `/methodology` page missing the `deterministic` concept marker.

---

## 10. Revenue Verification / Attribution / Discrepancy Evidence

| Route | Built bytes | Limitations section present? | Notable required concepts |
|---|---|---|---|
| `/revenue-verification` | 63,760 | ✅ | `commerce evidence`, `payment evidence`, `reconciliation`, `discrepancy`, `last reviewed` |
| `/attribution-methodology` | 63,707 | ✅ | `attribution model`, `bounded`, `assumptions`, `limitations`, `last reviewed` |
| `/discrepancy-taxonomy` | 66,645 | ✅ | All 8 discrepancy classes: timing mismatch, currency/tax/shipping, refund, attribution-window, duplicate, missing commerce event, unmatched platform claim, delayed arrival, plus `limitations` and `last reviewed` |

Each page explicitly disclaims what it does not assert: revenue verification cannot answer incrementality; attribution cannot prove causality; the discrepancy taxonomy is open-ended and tracks new classes via the last-reviewed date.

---

## 11. Legal/Security Honesty Boundary

The D5 harness scans every source file under `src/app/` and `src/components/` (112 files) for the banned-phrase list in `D5_BANNED_UNAPPROVED_COMPLIANCE_PHRASES`:

- `SOC 2 certified` / `SOC2 certified`
- `ISO 27001 certified` / `ISO certified`
- `HIPAA compliant`
- `PCI DSS compliant` / `PCI compliant`
- `GDPR compliant`
- `CCPA compliant`
- `FedRAMP authorized`
- `fully encrypted`
- `end-to-end encrypted`
- `we never store any PII`
- `we collect no PII`
- `we collect zero data`
- `cannot be hacked`

**Result: 0 invented compliance claims in source.**

What the site *does* say about compliance/security:

| Page | Compliance posture | Status |
|---|---|---|
| `/security` (`#compliance-claims`) | Skeldir is **not** SOC 2, ISO 27001, HIPAA, or PCI DSS certified; we do not claim those certifications. | `not applicable` |
| `/security` (`#transport-encryption`) | HTTPS required on every public surface. We avoid blanket encryption shorthand because those phrases mean different things to different reviewers. | `implemented` |
| `/security` (`#pii-policy`) | Privacy-minimizing design *within the reconciliation engine*. We do not assert "no PII" globally. | `partially implemented` |
| `/security` (`#tenant-isolation`) | Per-tenant isolation enforcement is staged; status will move to `implemented` when audited. | `planned` |
| `/security` (`#vulnerability-disclosure`) | security@skeldir.com mailbox; good-faith engagement; no bounty program. | `implemented` |
| `/privacy`, `/terms`, `/gdpr` | All three carry `legal_review_required` badges, are noindex, and explicitly state Skeldir refuses to publish legal language without operator/legal review. | `legal_review_required` |

Negative control NC-D5-09 verifies the harness catches a fixture page that claims `SOC 2 certified` or `HIPAA compliant`.

---

## 12. Harness Proof

| Command | Result |
|---|---|
| `npm run build` | **PASS** — 36 static pages generated, including all 12 D5 routes. `d4-move-jsonld-to-head` moved JSON-LD into `<head>` for all 9 indexable D5 pages. |
| `npm run discoverability:d0` | **PASS** — 121 / 0 / 0. New routes classified; no UNCLASSIFIED. |
| `npm run discoverability:d1` | **PASS** — 37 / 0. HTML-first retrieval intact. |
| `npm run discoverability:d2` | **PASS** — 39 / 0. After updating the sitemap-forbidden list to release `/security`, `/docs`, `/api`, `/trust-envelope`, sitemap matches manifest exactly. |
| `npm run discoverability:d3` | **PASS** — 51 / 0. Bot policy unchanged. |
| `npm run discoverability:d4` | **PASS** — 24 / 0. JSON-LD head placement + parity confirmed for every D5 indexable route. |
| `npm run discoverability:d4:negative-controls` | **PASS** — 11 / 0. |
| **`npm run discoverability:d5`** | **PASS** — 73 / 0 / 0 (1 informational warning about production-final separation). |
| **`npm run discoverability:d5:negative-controls`** | **PASS** — 15 / 0. |

### Intentional failures caught by negative controls (proof that validators bite)

| ID | Negative-control fixture | Caught? |
|---|---|---|
| NC-D5-01 | Footer `Privacy Policy` → `/resources` | ✅ |
| NC-D5-02 | Footer missing required `Methodology` label | ✅ |
| NC-D5-03 | Proof page emits `Loading...` shell | ✅ |
| NC-D5-04 | Proof page accidentally `noindex` | ✅ |
| NC-D5-05 | Proof page missing review-status token | ✅ |
| NC-D5-06 | Proof page missing `last reviewed` token | ✅ |
| NC-D5-07 | `/trust-envelope` missing `semantic truth hash` concept | ✅ |
| NC-D5-08 | `/methodology` missing `deterministic` concept | ✅ |
| NC-D5-09 | Page asserts `SOC 2 certified` / `HIPAA compliant` | ✅ |
| NC-D5-10 | `/privacy` missing `legal_review_required` status | ✅ |
| NC-D5-11 | `/privacy` missing noindex while flagged as placeholder | ✅ |
| NC-D5-12 | Claim registry entry missing required field | ✅ |
| NC-D5-13 | Claim with unknown category | ✅ |
| NC-D5-14 | Regression — real proof pages still satisfy concept gates | ✅ |
| NC-D5-15 | Regression — real legal placeholder pages still satisfy gate | ✅ |

---

## 13. Artifact Excerpts

### `/privacy` (legal placeholder, noindex)

```html
<title>Privacy | Skeldir — legal_review_required</title>
<meta name="description" content="Reserved URL for the Skeldir privacy policy. Status: legal_review_required..." />
<meta name="robots" content="noindex,nofollow" />
<link rel="canonical" href="https://skeldir.com/privacy" />
...
<h1>Privacy</h1>
<dt>Status</dt><dd><code>legal_review_required</code></dd>
<dt>Last reviewed</dt><dd><time datetime="2026-05-23">2026-05-23</time></dd>
...
"We will not publish legal language we have not had reviewed by operator and legal counsel."
```

### `/security` (indexable, technical_disclosure_only)

```html
<title>Security — Technical disclosure with explicit status taxonomy</title>
<link rel="canonical" href="https://skeldir.com/security" />
<script type="application/ld+json">{"@type":"WebPage","@id":"https://skeldir.com/security#webpage","dateModified":"2026-05-23",...}</script>
...
<h1>Security</h1>
<dt>Status</dt><dd><code>technical_disclosure_only</code></dd>
<section id="status-taxonomy">implemented | partially implemented | planned | not applicable</section>
<section id="compliance-claims">Skeldir is not currently SOC 2, ISO 27001, HIPAA, or PCI DSS certified.</section>
```

### `/methodology` (indexable, technical_disclosure_only)

```html
<h1>Methodology</h1>
<section id="deterministic-reconciliation">...deterministic reconciliation engine...</section>
<section id="ai-boundary">...In short: the model explains; it <strong>does not calculate</strong> the truth.</section>
<section id="limitations">...Reconciliation depends on the operator connecting authoritative commerce and payment systems...</section>
```

### `/trust-envelope` (indexable, technical_disclosure_only)

```html
<h1>TrustEnvelope: the deterministic truth contract</h1>
<section id="semantic-truth-hash">...stable hash of the envelope's normalized claim...</section>
<section id="artifact-hash">...byte-level hash of the serialized envelope itself...</section>
<section id="audit-trail">...append-only sequence of envelope revisions...</section>
<section id="limitations">...This page does not promise a public machine-callable Trust API endpoint...</section>
```

### `/revenue-verification` and `/discrepancy-taxonomy`

Each emits an `id="..."` section per required concept; the harness Gate D5.2 cross-checks every claim anchor against the built HTML. All 12 registered anchors resolved.

---

## 14. Remaining Unknowns

1. Whether `origin/main` can be reconciled via unrelated-history merge, subtree import, or manifest-backed patch replay without silent loss (carried over from D4-C2 — not in D5 scope).
2. Whether production Netlify hosting injects any transforms beyond `out/` that could change the static HTML the harness validates (requires deploy-preview or production curl proof — not run in this environment).
3. Whether operator/legal will approve the `legal_review_required` placeholder pages with full legal copy (intentionally blocked on operator input; the page itself documents the blocking state).
4. Whether the `legal_review_required` for D5-CLAIM-010 (privacy posture inside the reconciliation engine) is satisfied by `technical_disclosure_only` security copy or requires a separate legal-counsel-approved privacy-engineering disclosure — flagged for operator review.

---

## 15. D6 Readiness

D6 (evidence-library architecture and depth) may begin locally on the same branch with the following pre-conditions inherited from D5:

- Every D5 proof page is a stable static HTML surface with a registered owner, status, and last-reviewed date — D6 evidence pages can link into them safely.
- The claim-proof registry (`discoverability.claim-proof-registry.json`) is the canonical place to register new D6 evidence-page claims as they appear.
- `/docs` is the index for documentation concepts and naturally extends into D6 evidence-library structure (Meta-vs-Stripe, Shopify reconciliation, platform-specific discrepancy pages, view-through window pages — all the H-A11 / H-B07 audit gaps the original audit called out).
- `/privacy`, `/terms`, `/gdpr` remain `blocked_by_legal_review_required` for D6 purposes; D6 must not invent legal copy to populate them.
- Production-final closure for D5 **and** any future phase remains blocked by the global Git/CI/deploy blocker.

D6 should **not** retroactively re-open the D5 routes to write legal copy. Legal/security copy enters the system through the claim-proof registry first, then becomes visible on `/privacy` / `/terms` / `/gdpr` only when `status: operator_approved` lands in the registry with cited evidence.

---

## Operator follow-ups required

To move D5 from "local PASS" to "production-final PASS":

1. Resolve mainline Git lineage onto `origin/main` (carried from D4-C2).
2. Run CI on the mergeable branch and attach the run URL.
3. Provide a deploy-preview URL so the harness's static-HTML claims can be curl-verified against the served response.
4. (Independent of release) Decide whether the `legal_review_required` placeholders should remain as-is or be promoted with operator/legal-approved copy. If promoted, add the corresponding rows to the claim-proof registry first; do not edit page text directly.
