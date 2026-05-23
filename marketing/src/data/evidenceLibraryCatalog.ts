import type { EvidencePageDefinition } from "@/types/evidenceLibrary";

const LR = "2026-05-23";
const OWNER = "Skeldir Product Engineering";
const CADENCE = "Quarterly (90 days) or sooner after major platform API changes";

const D5_BASE = [
  { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
  { href: "/revenue-verification", label: "Revenue verification — commerce/payment evidence" },
  { href: "/discrepancy-taxonomy", label: "Discrepancy taxonomy — classification of mismatches" },
] as const;

function proof(extra: { href: string; label: string }[]) {
  return [...D5_BASE, ...extra];
}

export const EVIDENCE_SLUGS = [
  "meta-vs-stripe",
  "google-ads-vs-shopify",
  "shopify-reconciliation",
  "finance-roas-audit-checklist",
  "deterministic-attribution-methods",
  "deterministic-vs-probabilistic-confidence",
  "benchmark-methodology",
  "privacy-no-pii-methodology",
  "trust-envelope-technical-spec",
  "ai-llm-explanation-boundary",
  "tiktok-discrepancies",
  "pinterest-discrepancies",
  "paypal-reconciliation",
  "woocommerce-reconciliation",
] as const;

export type EvidenceSlug = (typeof EVIDENCE_SLUGS)[number];

export const EVIDENCE_CATALOG: Record<EvidenceSlug, EvidencePageDefinition> = {
  "meta-vs-stripe": {
    routePath: "/resources/evidence/meta-vs-stripe",
    h1: "Meta (Facebook) Ads vs Stripe: why totals diverge",
    metaDescription:
      "Mechanisms that inflate Meta purchase revenue vs Stripe-settled card money: attribution windows, dedupe rules, CAPI vs Pixel timing, refunds/chargebacks, and multi-currency presentation — with D5 proof anchors.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Meta Ads Manager can show higher “purchase” revenue than Stripe because Meta is crediting modeled or deduplicated web events on an attribution clock, while Stripe records card capture, refunds, disputes, and settlement in payment time. This page names the mechanisms; authoritative definitions stay on [[Methodology|/methodology]] and [[Revenue verification|/revenue-verification]].",
    keyFacts: [
      "Meta’s UI answers “which attributed touch paths get credit for conversions on this attribution setting,” not “what cleared your bank account this week.”",
      "Stripe’s ledger answers “what was authorized, captured, refunded, or disputed,” independent of Meta’s attribution graph.",
      "CAPI + Pixel mismatches (missing hashes, late events, or browser blocking) shift which purchases Meta can see vs what Shopify/Stripe can prove.",
    ],
    claimRows: [
      {
        claim: "“Meta is lying.”",
        evidence:
          "Usually false as a moral claim — often true as a *measurement* claim: two systems optimized for different questions. See [[Discrepancy taxonomy|/discrepancy-taxonomy]].",
      },
      {
        claim: "Stripe must match Ads Manager after reconciliation.",
        evidence:
          "Not guaranteed: residual gaps remain when attribution windows, currency display, or partial refunds differ. Skeldir documents residual classes rather than hiding them.",
      },
    ],
    howSkeldirTreats:
      "Skeldir treats Meta-reported revenue as a **platform claim** and Stripe/Shopify evidence as **commerce/payment truth** for the questions Skeldir is built to answer. The engine normalizes money into integer cents and pairs claims with evidence under policy captured in a [[TrustEnvelope concept|/trust-envelope]].\n\nThis retrieval page does **not** fork the D5 definitions — it routes you to them.",
    methodology:
      "Follow the reconciliation outline on [[Methodology|/methodology]]: deterministic joins on stable identifiers where available, explicit handling for timing and refund classes per [[Discrepancy taxonomy|/discrepancy-taxonomy]], and no silent substitution of modeled Meta revenue for settled funds.",
    whatDoesNotProve:
      "This explainer does not prove incremental lift from Meta spend, does not adjudicate creative quality, and does not replace your finance team’s close process. It also does not assert that any live Skeldir tenant dashboard matches examples on this marketing site.",
    limitations:
      "Examples are educational. Connector coverage, identity graph quality, and policy packs depend on tenant configuration. Bayesian enrichment or tenant-spanning benchmark-style features, if present in product, are **not authoritative** over deterministic reconciliation outcomes unless separately implemented and disclosed per tenant policy.",
    relatedProof: proof([
      { href: "/attribution-methodology", label: "Attribution methodology — bounded questions only" },
      { href: "/trust-envelope", label: "TrustEnvelope — policy + evidence container concept" },
    ]),
    relatedQuestions: [
      { href: "/resources/evidence/google-ads-vs-shopify", label: "Why do Google Ads and Shopify disagree?" },
      { href: "/resources/evidence/finance-roas-audit-checklist", label: "How should finance validate ROAS before budget shifts?" },
    ],
    capabilityRows: [
      { label: "Public static evidence pages", state: "Currently public" },
      { label: "Tenant-specific reconciliation outputs", state: "Unavailable on this marketing export (requires authenticated product)" },
      { label: "Benchmark intelligence across unrelated tenants", state: "Planned / not asserted as live here" },
    ],
  },

  "google-ads-vs-shopify": {
    routePath: "/resources/evidence/google-ads-vs-shopify",
    h1: "Google Ads vs Shopify: reconciliation lens for finance",
    metaDescription:
      "Why Google Ads conversion value and Shopify gross sales diverge: click vs order lifecycle, conversion lag settings, cart edits, tax/shipping presentation, and offline conversions — grounded in Skeldir’s D5 proof routes.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Google Ads attributes *conversion events* tied to ad clicks within configured windows, while Shopify totals reflect order rows that can change with edits, partial captures, refunds, and tax/shipping rules. Finance should expect systematic gaps even when both systems are “implemented correctly.” Start from [[Revenue verification|/revenue-verification]], not from either UI headline.",
    keyFacts: [
      "Conversion lag in Google Ads spreads credit across days; Shopify recognizes revenue on order state transitions you configure in commerce settings.",
      "Enhanced conversions and offline import can add rows to Google that never appear as first-party Shopify orders (B2B, phone sales, reseller paths).",
      "Tax inclusive/exclusive display and multi-market catalogs routinely create cents-level drift that compounds in weekly rollups.",
    ],
    claimRows: [
      {
        claim: "Google ROAS should equal Shopify sales / spend.",
        evidence:
          "Different numerators and denominators. ROAS from ads is not store net revenue without adjustment. See [[Attribution methodology|/attribution-methodology]].",
      },
      {
        claim: "Skeldir picks Google or Shopify as “winner.”",
        evidence:
          "Skeldir classifies discrepancies and preserves commerce/payment evidence as the financial anchor for supported integrations — see [[Methodology|/methodology]].",
      },
    ],
    howSkeldirTreats:
      "Skeldir aligns Google-reported conversion money to **bounded attribution questions** while treating Shopify order/payment evidence as the **commerce anchor** for revenue verification workflows. Where identifiers exist, deterministic joins are preferred; where they do not, Skeldir surfaces `confidence_status` / `fallback_reason` style semantics rather than inventing certainty (see [[TrustEnvelope|/trust-envelope]] concept page).",
    methodology:
      "Use the discrepancy classes in [[Discrepancy taxonomy|/discrepancy-taxonomy]] to label outcomes: timing skew, tax/shipping presentation, partial fulfillment, duplicate signals, and unmatched platform claims.",
    whatDoesNotProve:
      "Does not prove search incrementality, does not validate Quality Score mechanics, and does not replace Google Ads billing invoices for tax reporting.",
    limitations:
      "Marketing site copy cannot reflect your MCC structure, offline conversion schema, or Shopify markets configuration. No claim here implies a generally available external Trust API endpoint on skeldir.com — see [[API concepts|/api]].",
    relatedProof: proof([
      { href: "/attribution-methodology", label: "Attribution methodology" },
      { href: "/ai-boundary", label: "AI / LLM boundary" },
    ]),
    relatedQuestions: [
      { href: "/resources/evidence/meta-vs-stripe", label: "Why are Meta numbers higher than Stripe?" },
      { href: "/resources/evidence/shopify-reconciliation", label: "How do I reconcile Shopify orders to ad claims?" },
    ],
    capabilityRows: [
      { label: "Live Google ↔ Shopify connector guarantees", state: "Partially implemented — depends on product scope for your tenant" },
      { label: "Signed external verification artifacts", state: "Planned / not marketed as available on static pages" },
    ],
  },

  "shopify-reconciliation": {
    routePath: "/resources/evidence/shopify-reconciliation",
    h1: "Shopify order reconciliation against ad-channel revenue claims",
    metaDescription:
      "Practical join keys, timing classes, and refund behaviors when reconciling Shopify orders to Meta, Google, TikTok, or Pinterest claims — with explicit limitations and D5 proof anchors.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Reconciling Shopify to ad platforms is a **deterministic inventory problem with messy inputs**: you need stable order IDs, currency normalization, and explicit rules for partial refunds and split fulfillments. Skeldir’s proof stance is documented on [[Revenue verification|/revenue-verification]]; this page is a retrieval-oriented checklist, not a second methodology fork.",
    keyFacts: [
      "Shopify’s admin totals are commerce-state totals; ad platforms count modeled conversions on click/view clocks.",
      "Gift cards, split payments, and delayed captures routinely break naive one-click joins.",
      "UTM parameters help, but are not sufficient when platforms rewrite attribution after the fact.",
    ],
    claimRows: [
      {
        claim: "One export should tie out daily.",
        evidence:
          "Only if windows, taxes, and refund policies are aligned. Otherwise you need a labeled discrepancy backlog per [[Discrepancy taxonomy|/discrepancy-taxonomy]].",
      },
    ],
    howSkeldirTreats:
      "Skeldir normalizes commerce rows into evidence objects suitable for deterministic comparison against platform claims, then labels residual deltas instead of smoothing them away.",
    methodology:
      "Follow [[Methodology|/methodology]] for normalization and policy authority; use [[Attribution methodology|/attribution-methodology]] when the question is allocation, not settlement.",
    whatDoesNotProve:
      "Does not prove that any specific SKU’s margin supports continued spend; that is finance planning outside Skeldir’s commerce/payment proof boundary.",
    limitations:
      "Does not describe every Shopify app stack. Third-party subscription apps, external ERPs, or custom checkout scripts can change evidence availability.",
    relatedProof: proof([{ href: "/trust-envelope", label: "TrustEnvelope — evidence + policy container" }]),
    relatedQuestions: [
      { href: "/resources/evidence/google-ads-vs-shopify", label: "Google Ads vs Shopify" },
      { href: "/resources/evidence/paypal-reconciliation", label: "PayPal-specific reconciliation" },
    ],
    capabilityRows: [
      { label: "Operator-legal review for customer-facing commitments", state: "operator/legal review required" },
    ],
  },

  "finance-roas-audit-checklist": {
    routePath: "/resources/evidence/finance-roas-audit-checklist",
    h1: "Finance ROAS audit checklist before budget shifts",
    metaDescription:
      "A disciplined checklist: define the revenue numerator, align clocks, isolate refunds, separate modeled from settled, and document residual discrepancy classes — anchored to Skeldir D5 proof pages.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Before moving material budget, finance should verify **which revenue definition** ROAS uses, **which costs** the denominator includes, and **which timing axis** both sides use. This checklist is retrieval-shaped; authoritative methodology remains on [[Methodology|/methodology]] and [[Revenue verification|/revenue-verification]].",
    keyFacts: [
      "ROAS built on platform-attributed revenue is not interchangeable with ROAS built on settled card cash.",
      "Weekly rollups hide refund bursts that arrive late relative to click date.",
      "Agency fees, coupons, and COGS belong in finance models — not silently embedded inside ad UI ROAS.",
    ],
    claimRows: [
      {
        claim: "A single ROAS threshold should gate all spend.",
        evidence:
          "Dangerous without channel-specific nuance and confidence labels. See confidence discussion on [[Deterministic vs probabilistic confidence|/resources/evidence/deterministic-vs-probabilistic-confidence]].",
      },
    ],
    howSkeldirTreats:
      "Skeldir supports finance-grade questions by anchoring dashboards to commerce/payment evidence and clearly labeling modeled or platform-only numbers as claims.",
    methodology:
      "Cross-check steps with [[Discrepancy taxonomy|/discrepancy-taxonomy]] and ensure attribution windows are stated when discussing allocation questions per [[Attribution methodology|/attribution-methodology]].",
    whatDoesNotProve:
      "Does not provide accounting sign-off, tax advice, or investment recommendations.",
    limitations:
      "Checklist is generic. Your close calendar, intercompany billing, and marketplace fee structures may require additional controls.",
    relatedProof: proof([{ href: "/ai-boundary", label: "AI boundary — LLMs do not calculate financial truth" }]),
    relatedQuestions: [
      { href: "/resources/evidence/benchmark-methodology", label: "Benchmark methodology and limitations" },
    ],
    capabilityRows: [
      { label: "Automated CFO sign-off", state: "Unavailable" },
    ],
  },

  "deterministic-attribution-methods": {
    routePath: "/resources/evidence/deterministic-attribution-methods",
    h1: "Deterministic attribution methods Skeldir uses (and does not use)",
    metaDescription:
      "What deterministic means for joins, money normalization, and policy-bound attribution models — versus narrative or ML-explanations — with links to D5 methodology and AI boundary proof pages.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "**Deterministic** here means: given the same evidence inputs and the same published policy, Skeldir’s engine should reach the same reconciled outputs (byte-stable where specified). It does **not** mean “the market behaves deterministically.” Explanations in natural language are governed by [[AI boundary|/ai-boundary]].",
    keyFacts: [
      "Deterministic joins require explicit keys and clocks; otherwise Skeldir emits conservative statuses instead of guessing.",
      "Attribution models remain models: they allocate verified totals under assumptions documented on [[Attribution methodology|/attribution-methodology]].",
    ],
    claimRows: [
      {
        claim: "Deterministic implies causal truth.",
        evidence:
          "False. Deterministic means reproducible processing, not omniscience about incrementality.",
      },
    ],
    howSkeldirTreats:
      "Skeldir separates **reconciliation** (evidence vs claims) from **allocation** (how to split verified totals across touchpoints).",
    methodology:
      "Read [[Methodology|/methodology]] for the full proof outline; this page is a retrieval shortcut.",
    whatDoesNotProve:
      "Does not prove which creative caused a purchase; creative analytics remain platform- and experiment-specific.",
    limitations:
      "Where evidence is incomplete, outputs should carry explicit low-confidence semantics — never silent LLM backfill for money.",
    relatedProof: proof([
      { href: "/attribution-methodology", label: "Attribution methodology" },
      { href: "/trust-envelope", label: "TrustEnvelope" },
    ]),
    relatedQuestions: [
      { href: "/resources/evidence/deterministic-vs-probabilistic-confidence", label: "Deterministic vs probabilistic confidence" },
    ],
    capabilityRows: [
      { label: "LLM-generated numeric reconciliation", state: "Unavailable — excluded by product boundary" },
    ],
  },

  "deterministic-vs-probabilistic-confidence": {
    routePath: "/resources/evidence/deterministic-vs-probabilistic-confidence",
    h1: "Deterministic vs probabilistic confidence on commerce truth",
    metaDescription:
      "Clarifies deterministic verified values, model assumptions, confidence_status / fallback_reason semantics, cold-start behavior, and that Bayesian enrichment is not treated as overriding commerce evidence unless explicitly implemented and governed.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "**Deterministic verified values** (money in evidence, normalized under policy) are sovereign for Skeldir’s financial-trust posture. **Probabilistic** layers (if enabled in product) may rank, explain, or prioritize — but must not silently replace settled commerce totals. As of this review, treat any Bayesian benchmark story as **planned / non-authoritative** unless your tenant contract states otherwise.",
    keyFacts: [
      "`confidence_status` communicates evidence sufficiency and policy outcomes — not marketing optimism.",
      "`fallback_reason` should explain *why* a join or classification could not complete without guesswork.",
      "Cold start means insufficient history: probabilistic priors must not masquerade as measured performance.",
    ],
    claimRows: [
      {
        claim: "Bayesian posteriors should override Stripe-settled totals.",
        evidence:
          "Rejected positioning for Skeldir. If future product phases introduce Bayesian enrichment, it must be explicitly subordinate to deterministic commerce anchors — see [[TrustEnvelope|/trust-envelope]] concept fields.",
      },
    ],
    howSkeldirTreats:
      "Skeldir keeps reconciliation outputs auditable: deterministic core first; any enrichment is labeled, policy-governed, and tenant-scoped.",
    methodology:
      "Cross-read [[Methodology|/methodology]] and the TrustEnvelope field glossary on [[TrustEnvelope|/trust-envelope]].",
    whatDoesNotProve:
      "Does not provide a mathematical proof of posterior correctness for your catalog.",
    limitations:
      "This static page cannot know which future releases your organization purchased. It intentionally avoids implying “Bayesian confidence is shipping and binding” in product without an approved capability matrix signed by product + legal.",
    relatedProof: proof([{ href: "/trust-envelope", label: "TrustEnvelope concepts" }]),
    relatedQuestions: [{ href: "/resources/evidence/benchmark-methodology", label: "Benchmark methodology" }],
    capabilityRows: [
      { label: "Bayesian confidence as finance authority", state: "Not available as a global default (do not treat as live)" },
    ],
  },

  "benchmark-methodology": {
    routePath: "/resources/evidence/benchmark-methodology",
    h1: "Benchmark methodology: honest, privacy-bounded, non-spyware positioning",
    metaDescription:
      "How Skeldir discusses benchmarks without claiming live tenant-spanning intelligence: k-anonymity, dominance suppression, anti-differencing, and honest cold-start priors — mostly planned substrate, clearly labeled.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Skeldir’s public stance is conservative: **benchmark-style intelligence that spans unrelated tenants** is roadmap-class engineering, requiring statistical controls (k-anonymity, dominance suppression, anti-differencing) and honest priors. This page exists so buyers and agents do not infer live benchmark feeds from marketing prose.",
    keyFacts: [
      "A benchmark you cannot join to your own evidence is a vanity metric.",
      "Small-N segments leak information unless suppressed — a planned engineering obligation, not a slogan.",
    ],
    claimRows: [
      {
        claim: "Skeldir ships tenant-spanning benchmark feeds on skeldir.com today.",
        evidence:
          "Not claimed here. Treat as **Planned** unless a product changelog explicitly states otherwise for your tenant.",
      },
    ],
    howSkeldirTreats:
      "When benchmarks appear in product, they must be optional, labeled, and incapable of re-identifying counterparties — engineering detail remains in engineering disclosures, not in static marketing guarantees.",
    methodology:
      "Anchor operational decisions to your own reconciled evidence per [[Revenue verification|/revenue-verification]]; use external benchmarks only as context.",
    whatDoesNotProve:
      "Does not rank your brand against competitors with verified third-party data on this site.",
    limitations:
      "No live benchmark database is described as queryable from this static export.",
    relatedProof: proof([{ href: "/methodology", label: "Methodology" }]),
    relatedQuestions: [{ href: "/resources/evidence/finance-roas-audit-checklist", label: "Finance ROAS audit checklist" }],
    capabilityRows: [
      { label: "Tenant-spanning benchmark query API", state: "Planned — not described as live" },
    ],
  },

  "privacy-no-pii-methodology": {
    routePath: "/resources/evidence/privacy-no-pii-methodology",
    h1: "Privacy and durable PII boundaries inside the reconciliation substrate",
    metaDescription:
      "Privacy-minimizing design for financial reconciliation: what Skeldir avoids claiming (“zero PII everywhere”), what durable storage targets, and where legal review still applies — consistent with D5 honesty boundaries.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Skeldir targets **privacy-minimizing** commerce/payment reconciliation: reduce durable sensitive fields, strip where applicable, and avoid turning the reconciliation substrate into a global identity graph. This is **not** a promise that your company collects **zero** PII in every department — do not misread it as blanket “no PII” marketing.",
    keyFacts: [
      "Checkout flows may still collect customer PII for legal/tax reasons — Skeldir does not claim to abolish that.",
      "The reconciliation engine boundary focuses on what Skeldir persists for financial memory under policy.",
    ],
    claimRows: [
      {
        claim: "“We never store any customer identifiers anywhere in the company.”",
        evidence:
          "Avoid this phrasing — it is broader than the reconciliation substrate and invites legal challenge. Prefer explicit scope statements tied to engine storage.",
      },
    ],
    howSkeldirTreats:
      "Skeldir aligns public language with the claim-proof posture in [[Methodology|/methodology]] and security placeholders on [[Security|/security]] rather than inventing certifications.",
    methodology:
      "See D5 proof pages and your operator agreements for the authoritative boundary for your deployment.",
    whatDoesNotProve:
      "Does not provide GDPR legal analysis for your entity.",
    limitations:
      "Static marketing copy cannot know your data processing agreements. legal_review_required may apply before customer-facing promises.",
    relatedProof: proof([
      { href: "/security", label: "Security disclosures placeholder" },
      { href: "/docs", label: "Documentation concepts index" },
    ]),
    relatedQuestions: [{ href: "/resources/evidence/ai-llm-explanation-boundary", label: "AI / LLM explanation boundary" }],
    capabilityRows: [
      { label: "Global “zero PII” warranty", state: "Unavailable — explicitly rejected as wording" },
    ],
  },

  "trust-envelope-technical-spec": {
    routePath: "/resources/evidence/trust-envelope-technical-spec",
    h1: "TrustEnvelope technical spec (retrieval view)",
    metaDescription:
      "Retrieval-oriented summary of TrustEnvelope fields, hashes, confidence semantics, and externalization — citing the D5 TrustEnvelope proof page without forking definitions or implying live external signing.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Treat [[TrustEnvelope|/trust-envelope]] as the **canonical proof surface** for field names and semantics. This D6 page exists so agents can land on a shorter route that still points upward to the authority page — it must not introduce alternate hash algorithms, signing ceremonies, or API promises.",
    keyFacts: [
      "Canonical definitions live on /trust-envelope — not here.",
      "External verification and asymmetric signing are roadmap-sensitive; default assumption is **not live** on the marketing host.",
    ],
    claimRows: [
      {
        claim: "External signed artifacts are downloadable today from skeldir.com.",
        evidence:
          "Not asserted. Capability status below marks this as planned / unavailable on static marketing.",
      },
    ],
    howSkeldirTreats:
      "D6 routes cite D5 authorities; retrieval pages stay thin and link-heavy.",
    methodology:
      "Read the canonical page: [[TrustEnvelope|/trust-envelope]].",
    whatDoesNotProve:
      "Does not provide a W3C-style formal specification with independent test vectors.",
    limitations:
      "If product drift occurs, the D5 page must be updated first; this retrieval page follows it.",
    relatedProof: proof([
      { href: "/trust-envelope", label: "TrustEnvelope (canonical)" },
      { href: "/api", label: "API concepts + availability boundary" },
    ]),
    relatedQuestions: [{ href: "/resources/evidence/deterministic-vs-probabilistic-confidence", label: "Confidence semantics" }],
    capabilityRows: [
      { label: "Generally-available public Trust HTTP API on skeldir.com", state: "Unavailable — see [[API|/api]]" },
    ],
  },

  "ai-llm-explanation-boundary": {
    routePath: "/resources/evidence/ai-llm-explanation-boundary",
    h1: "AI / LLM explanation boundary for financial truth",
    metaDescription:
      "Retrieval explainer: LLMs may narrate deterministic outputs but do not compute reconciled money; links to the D5 AI boundary proof page and TrustEnvelope concepts.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Skeldir’s boundary is strict: **LLMs explain, they do not calculate financial truth.** The canonical disclosure is [[AI boundary|/ai-boundary]]; this page helps agents and buyers query that stance without duplicating the proof text.",
    keyFacts: [
      "Narration must cite engine outputs and policy IDs — not invent numbers.",
      "Hands-free financial actions triggered directly from LLM suggestions are out of scope for this public evidence layer.",
    ],
    claimRows: [
      {
        claim: "ChatGPT verified our revenue.",
        evidence:
          "Unsafe framing. LLMs can summarize Skeldir outputs; they are not evidence sources.",
      },
    ],
    howSkeldirTreats:
      "Product UX should surface deterministic tables first; any LLM layer is labeled as explanatory.",
    methodology:
      "Canonical: [[AI boundary|/ai-boundary]] + [[Methodology|/methodology]].",
    whatDoesNotProve:
      "Does not discuss third-party tool security for your org — that is an operator integration topic, not asserted here as live.",
    limitations:
      "Does not claim MCP integrations, invite-only partner programs, or hands-free budget changes are available from static pages.",
    relatedProof: proof([
      { href: "/ai-boundary", label: "AI boundary (canonical)" },
      { href: "/methodology", label: "Methodology" },
    ]),
    relatedQuestions: [{ href: "/resources/evidence/deterministic-attribution-methods", label: "Deterministic attribution methods" }],
    capabilityRows: [
      { label: "LLM-driven hands-free budget moves", state: "Unavailable on public marketing evidence" },
      { label: "Invite-only partner programs", state: "Not described as live here" },
    ],
  },

  "tiktok-discrepancies": {
    routePath: "/resources/evidence/tiktok-discrepancies",
    h1: "TikTok Ads discrepancies vs commerce evidence",
    metaDescription:
      "SKAdNetwork postbacks, modeled conversions, delayed attribution, and SAN limitations vs Shopify/Stripe settlement reality — unique mechanisms separate from Meta or Google drift.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "TikTok on iOS often operates under **SKAN constraints** and aggregated postbacks, which intentionally obscure user-level joins that Stripe receipts still contain. That structural opacity — not just “attribution windows” — drives persistent gaps versus commerce cash.",
    keyFacts: [
      "Modeled conversions fill gaps SKAN cannot expose; commerce evidence does not need those models to book cash.",
      "Android vs iOS reporting asymmetry can swing weekly blended ROAS without any creative change.",
    ],
    claimRows: [
      {
        claim: "TikTok should match Stripe daily.",
        evidence:
          "Often impossible at user level on iOS SKAN regimes; finance should expect cohort-level alignment at best.",
      },
    ],
    howSkeldirTreats:
      "Skeldir classifies TikTok-specific timing and aggregation limits under the taxonomy and preserves commerce totals as the financial anchor.",
    methodology:
      "See [[Discrepancy taxonomy|/discrepancy-taxonomy]] and platform-agnostic methodology on [[Methodology|/methodology]].",
    whatDoesNotProve:
      "Does not provide TikTok Ads API field-by-field mapping for your catalog.",
    limitations:
      "TikTok product surfaces change frequently; operator review may be needed quarterly.",
    relatedProof: proof([{ href: "/revenue-verification", label: "Revenue verification" }]),
    relatedQuestions: [{ href: "/resources/evidence/pinterest-discrepancies", label: "Pinterest discrepancies" }],
    capabilityRows: [
      { label: "SKAN user-level joins inside Skeldir", state: "Partially implemented / often unavailable by Apple design" },
    ],
  },

  "pinterest-discrepancies": {
    routePath: "/resources/evidence/pinterest-discrepancies",
    h1: "Pinterest Ads discrepancies vs store revenue",
    metaDescription:
      "Pin promotion catalogs, long-tail discovery traffic, and Pinterest’s delayed engagement model vs short conversion windows in Shopify — distinct from TikTok SKAN issues or Meta CAPI/Pixel mechanics.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "Pinterest frequently behaves like **discovery with long half-life**: a pin can earn traffic weeks after spend, while Shopify attributes revenue to checkout date and coupon rules. Misaligned **view-through** settings and catalog feed mismatches create deltas that are not numerically similar to Meta vs Stripe cases.",
    keyFacts: [
      "Catalog ingestion errors (SKU mismatches) create false “missing revenue” in Pinterest while Shopify shows valid orders.",
      "Pinterest’s assisted metrics can overweight upper-funnel touches relative to finance’s cash view.",
    ],
    claimRows: [
      {
        claim: "Pinterest ROAS should track 1:1 with Shopify daily sales.",
        evidence:
          "Expect systematic drift; use reconciliation classes instead of forcing tie-out.",
      },
    ],
    howSkeldirTreats:
      "Skeldir treats Pinterest numbers as platform claims requiring commerce evidence and explicit taxonomy labels — not as settlement truth.",
    methodology:
      "Use [[Attribution methodology|/attribution-methodology]] for view/click window disclosures; use [[Revenue verification|/revenue-verification]] for money anchoring.",
    whatDoesNotProve:
      "Does not evaluate creative fatigue for individual boards.",
    limitations:
      "Does not cover every Pinterest objective type or catalog edge case.",
    relatedProof: proof([{ href: "/attribution-methodology", label: "Attribution methodology" }]),
    relatedQuestions: [{ href: "/resources/evidence/tiktok-discrepancies", label: "TikTok discrepancies" }],
    capabilityRows: [
      { label: "Pin-level deterministic cash mapping", state: "Planned / tenant-dependent" },
    ],
  },

  "paypal-reconciliation": {
    routePath: "/resources/evidence/paypal-reconciliation",
    h1: "PayPal vs store orders: reconciliation pitfalls",
    metaDescription:
      "Express Checkout, partial captures, disputes, and multi-currency settlement vs Shopify order totals — distinct mechanisms from card-only Stripe drift or Google click attribution.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "PayPal introduces **wallet-specific settlement paths**, hold periods, and dispute flows that do not mirror card processors line-for-line. Shopify may show an order as paid while PayPal’s settlement file still shows a pending or reversed state — a different failure mode than Meta over-attribution.",
    keyFacts: [
      "Partial captures and multiple capture rows complicate naive order totals.",
      "Buyer disputes can claw back funds after Shopify marks fulfillment complete.",
    ],
    claimRows: [
      {
        claim: "PayPal total should always match Shopify admin.",
        evidence:
          "False without explicit mapping rules for pending/processing/failed states.",
      },
    ],
    howSkeldirTreats:
      "Skeldir models PayPal money movement as payment evidence with explicit state transitions rather than trusting a single UI column.",
    methodology:
      "See [[Discrepancy taxonomy|/discrepancy-taxonomy]] for refund/chargeback classes and [[Methodology|/methodology]] for normalization discipline.",
    whatDoesNotProve:
      "Does not provide PayPal merchant legal advice.",
    limitations:
      "PayPal product names and reporting exports vary by region; finance must validate field dictionaries locally.",
    relatedProof: proof([{ href: "/revenue-verification", label: "Revenue verification" }]),
    relatedQuestions: [{ href: "/resources/evidence/woocommerce-reconciliation", label: "WooCommerce reconciliation" }],
    capabilityRows: [
      { label: "Automated PayPal legal dispute prediction", state: "Unavailable" },
    ],
  },

  "woocommerce-reconciliation": {
    routePath: "/resources/evidence/woocommerce-reconciliation",
    h1: "WooCommerce reconciliation vs ad platforms",
    metaDescription:
      "Plugin-driven UTM capture, server-side order edits, HPOS, and mixed payment gateways vs ad platform conversion APIs — distinct from Shopify-native assumptions.",
    lastReviewed: LR,
    dateModified: LR,
    owner: OWNER,
    reviewCadence: CADENCE,
    disclosureStatus: "technical_disclosure_only",
    bluf:
      "WooCommerce sites inherit **plugin combinatorics**: the same order might be touched by tax plugins, subscription renewals, and manual admin edits. Ad platforms see conversion pings that may never reflect the final `wp_post` totals Woo reports — a different reconciliation graph than SaaS-native Shopify stores.",
    keyFacts: [
      "HPOS and legacy tables affect how events are emitted to connectors.",
      "Partial refunds via manual line-item edits can desync Meta CAPI payloads if plugins do not re-fire events.",
    ],
    claimRows: [
      {
        claim: "WooCommerce should reconcile like Shopify out of the box.",
        evidence:
          "False — integration surface area is larger and more variable.",
      },
    ],
    howSkeldirTreats:
      "Skeldir assumes Woo evidence requires explicit connector contracts and stronger `fallback_reason` labeling when plugin graphs are unknown.",
    methodology:
      "Start from [[Methodology|/methodology]]; expect more manual taxonomy labels early in an engagement.",
    whatDoesNotProve:
      "Does not audit PHP plugin security for your store.",
    limitations:
      "Self-hosted variance is high; this page cannot enumerate every plugin interaction.",
    relatedProof: proof([{ href: "/docs", label: "Documentation concepts" }]),
    relatedQuestions: [{ href: "/resources/evidence/shopify-reconciliation", label: "Shopify reconciliation primer" }],
    capabilityRows: [
      { label: "Universal Woo plugin graph inference", state: "Planned / operator-intensive today" },
    ],
  },
};

export function getEvidenceDefinition(slug: string): EvidencePageDefinition | undefined {
  return EVIDENCE_CATALOG[slug as EvidenceSlug];
}

export function allEvidenceDefinitions(): EvidencePageDefinition[] {
  return EVIDENCE_SLUGS.map((s) => EVIDENCE_CATALOG[s]);
}
