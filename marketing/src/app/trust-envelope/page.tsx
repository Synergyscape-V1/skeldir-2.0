import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/trust-envelope";
const PAGE_TITLE = "TrustEnvelope | Skeldir";
const PAGE_DESCRIPTION =
  "A TrustEnvelope is the smallest reproducible record that bundles a deterministic financial value with its evidence chain, verification status, governing policy, and audit trail — so downstream systems can read a number with its limits, not in isolation.";

const KEY_FACTS = [
  "Every surfaced number is wrapped with provenance, confidence status, policy context, and audit trail.",
  "Deterministic values are integer-precision financial quantities produced by the reconciliation engine, not by models or heuristics.",
  "Confidence status is a bounded verification state, not a probability score.",
  "Benchmark metadata and policy context are descriptive; they do not alter the deterministic value.",
  "Fallback conditions and coverage limits are explicitly recorded rather than silently assumed.",
];

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function TrustEnvelopeProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "TrustEnvelope",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "TrustEnvelope" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="TrustEnvelope"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-02-25",
          notes:
            "This page explains the TrustEnvelope concept. Public API availability, versioning, and integration behavior are documented separately when available.",
        }}
        sections={[
          {
            id: "key-facts",
            heading: "Key facts",
            body: (
              <ul className="list-disc pl-6 space-y-3 text-slate-700">
                {KEY_FACTS.map((fact) => (
                  <li key={fact.slice(0, 48)}>{fact}</li>
                ))}
              </ul>
            ),
          },
          {
            id: "what-it-is",
            heading: "What is a TrustEnvelope?",
            body: (
              <>
                <p>
                  A TrustEnvelope is a static, auditable bundle that wraps every number Skeldir
                  surfaces. It exists so no downstream system, dashboard, or agent can read a
                  deterministic value without simultaneously seeing where that value came from,
                  what policy context applied, what its verification status is, and whether any
                  fallback was recorded.
                </p>
                <p>
                  A TrustEnvelope is never an opinion. It is the smallest reproducible record
                  that lets an external reviewer corroborate the value from disclosed evidence
                  categories and confirm Skeldir&apos;s claim at the outcome level.
                </p>
              </>
            ),
          },
          {
            id: "deterministic-values",
            heading: "Deterministic values",
            body: (
              <>
                <p>
                  Every TrustEnvelope contains one or more deterministic values — integer-precision
                  financial quantities such as revenue, refund, fee, payout, or net recognized
                  amount — computed by Skeldir&apos;s deterministic reconciliation engine, not by
                  an LLM, statistical model, or heuristic.
                </p>
                <p>
                  Deterministic values are repeatable: given the same evidence inputs and the same
                  governing policy context, Skeldir returns the same verified output.
                </p>
              </>
            ),
          },
          {
            id: "provenance-chain",
            heading: "Evidence chain (provenance)",
            body: (
              <>
                <p>
                  The provenance chain — the evidence chain behind the envelope — is a traceable
                  history showing the categories of records and decisions that support a verified
                  number: payment charges, commerce orders, platform reports, currency snapshots,
                  refund records, and policy context applied along the way.
                </p>
                <p>
                  The evidence chain is the spine of the audit trail. Each step is individually
                  referenceable for review; it describes what supported the value without prescribing
                  internal storage or replay mechanics.
                </p>
              </>
            ),
          },
          {
            id: "claim-identity-signal",
            heading: "Claim identity signal (semantic truth hash)",
            body: (
              <p>
                The semantic truth hash is a <strong>claim identity signal</strong>: a stable
                identity marker used to compare whether two records refer to the same verified
                financial claim. Two TrustEnvelopes sharing the same semantic truth hash assert the
                same financial truth at the category level, even when presentation differs. This
                supports safe deduplication and cross-system equality checks without publishing
                construction recipes.
              </p>
            ),
          },
          {
            id: "record-integrity-signal",
            heading: "Record integrity signal (artifact hash)",
            body: (
              <p>
                The artifact hash is a <strong>record integrity signal</strong>: a tamper-evidence
                marker that helps detect whether a record has changed in transit or storage. Where
                the claim identity signal answers &ldquo;is this the same verified claim?&rdquo;,
                the record integrity signal answers &ldquo;has this record been altered?&rdquo; —
                without describing serialization format or internal representation.
              </p>
            ),
          },
          {
            id: "confidence-status",
            heading: "Confidence status",
            body: (
              <>
                <p>
                  Every envelope carries a confidence status drawn from a small bounded set:
                  verified, partially verified, unverified, and blocked. Verified means required
                  evidence inputs matched and reconciled under policy. Partially verified means
                  some inputs are missing or delayed and the envelope explains which. Unverified and
                  blocked mean Skeldir refuses to assert deterministic truth and explains why.
                </p>
                <p>
                  Confidence status is a verification state category, not a probability score.
                  Probabilistic ranges live separately on the{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>{" "}
                  surface.
                </p>
              </>
            ),
          },
          {
            id: "benchmark-metadata",
            heading: "Benchmark metadata",
            body: (
              <p>
                Benchmark metadata records comparison baselines that informed the envelope:
                platform-reported value, commerce-reported value, difference, disclosed tolerance
                context, and normalization context. Benchmark metadata is descriptive — it does not
                change the deterministic value, but it helps a reviewer understand the reconciliation
                outcome.
              </p>
            ),
          },
          {
            id: "policy-authority",
            heading: "Policy authority",
            body: (
              <p>
                Policy authority names which governing rules were active when the envelope was
                computed — for example attribution window context, currency treatment, tax and
                shipping treatment, and discrepancy handling posture. Two envelopes computed under
                different policy context may produce different deterministic values; policy authority
                makes that explicit at the governance category level.
              </p>
            ),
          },
          {
            id: "fallback-reason",
            heading: "Fallback reason",
            body: (
              <p>
                If the engine could not fully reconcile a value and had to use a degraded mode, the
                envelope records a fallback reason describing what was missing and what limit was
                applied. Envelopes with a fallback reason are not marked verified.
              </p>
            ),
          },
          {
            id: "external-verification-metadata",
            heading: "External verification metadata",
            body: (
              <p>
                External verification metadata references the categories of external systems a
                reviewer would use to corroborate the claim — for example connected payment,
                commerce, or ad-platform evidence sources — without prescribing account-level
                operational detail or Skeldir storage layout.
              </p>
            ),
          },
          {
            id: "action-authority",
            heading: "Action authority",
            body: (
              <p>
                Action authority describes which downstream actions may be influenced on the basis
                of this envelope&apos;s verification status. It is the governance link between
                confidence status and operational decisions. Downstream systems should respect these
                boundaries when triggering operational decisions.
              </p>
            ),
          },
          {
            id: "audit-trail",
            heading: "Audit trail",
            body: (
              <p>
                The audit trail is the recorded sequence of envelope revisions: who or what produced
                each revision, when, under which policy context, and what claim identity signal
                resulted. Together with the evidence chain, it lets an auditor walk a value backward
                to its evidence categories and forward through every disclosed restatement.
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
          {
            href: "/revenue-verification",
            label: "Revenue verification — commerce and payment evidence",
          },
          {
            href: "/attribution-methodology",
            label: "Attribution methodology — bounded model assumptions",
          },
          {
            href: "/discrepancy-taxonomy",
            label: "Discrepancy taxonomy — classification criteria",
          },
          { href: "/ai-boundary", label: "AI / LLM boundary — explanation vs computation" },
          { href: "/api", label: "API concepts — availability and boundaries" },
          { href: "/docs", label: "Documentation — integration surfaces" },
        ]}
        limitations={
          <>
            <p>
              <strong>Current limitations.</strong> A TrustEnvelope describes deterministic
              financial truth as Skeldir has reconciled it. It does not assert truths Skeldir cannot
              measure: brand lift, incrementality beyond what the{" "}
              <Link className="underline" href="/attribution-methodology">
                attribution methodology
              </Link>{" "}
              surface bounds, or any claim about a platform Skeldir does not currently ingest.
            </p>
            <p>
              This page describes the TrustEnvelope concept. It does not promise a live public API
              contract; public API availability, versioning, and integration behavior are documented
              separately on the{" "}
              <Link className="underline" href="/api">
                API
              </Link>{" "}
              and{" "}
              <Link className="underline" href="/docs">
                documentation
              </Link>{" "}
              surfaces when available.
            </p>
            <p>
              Confidence status is not a model probability. It is a bounded verification state.
              Probabilistic ranges over attribution outcomes live on the attribution methodology
              reference and do not override the envelope verification status.
            </p>
          </>
        }
      />
    </>
  );
}
