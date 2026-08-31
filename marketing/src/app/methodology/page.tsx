import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/methodology";
const PAGE_TITLE = "How Skeldir Produces Verified Revenue Truth | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir's methodology for deterministic revenue verification — how platform-reported ad revenue is reconciled against verified commerce and payment evidence, how attribution models answer bounded questions, and where LLM-generated explanations are and are not used.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

const FIVE_FACTS = [
  "Every authoritative revenue figure originates from verified commerce and payment evidence — not from a model, and not from platform-reported data accepted at face value.",
  "Reconciliation is deterministic: identical inputs produce identical verified outputs.",
  "Discrepancies between platform-reported revenue and verified evidence are classified by type — not averaged, estimated, or suppressed.",
  "Attribution model output is always displayed alongside the verified revenue total it distributes, so reviewers can see exactly what was computed and what was modeled.",
  "LLMs in Skeldir explain deterministic outputs — they do not compute, invent, or estimate financial values.",
];

export default function MethodologyProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "How Skeldir Produces Verified Revenue Truth",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Methodology" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="How Skeldir Produces Verified Revenue Truth"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-02-01",
          notes:
            "This page is technical disclosure for informational use. It is not a contract, service-level agreement, or legal commitment.",
        }}
        bluf={{
          paragraphs: (
            <>
              <p>
                Skeldir reconciles platform-reported ad revenue against verified commerce and
                payment evidence using a deterministic process: given the same inputs, the same
                verified output is produced every time. This page explains what counts as verified
                evidence, what attribution models prove and do not prove, how discrepancies are
                classified, and the strict boundary between deterministic computation and
                LLM-generated explanation.
              </p>
              <p>
                This is technical disclosure for informational use. It is not a contract.
              </p>
            </>
          ),
          fiveFacts: FIVE_FACTS,
        }}
        sections={[
          {
            id: "deterministic-reconciliation",
            heading: "How deterministic reconciliation works",
            body: (
              <>
                <p>
                  Skeldir reconciles platform-reported ad revenue against verified commerce and
                  payment evidence. Reconciliation is deterministic: given the same inputs and the
                  same verification policy, the output is reproducible.
                </p>
                <p>
                  Authoritative financial numbers originate from verified evidence, not from a
                  model. Payment processor settlement records, order records from connected commerce
                  platforms, and charge records from connected payment systems are the ground
                  truth. Platform-reported revenue is treated as a claim that must be reconciled
                  against that ground truth — it is never accepted on its own authority.
                </p>
              </>
            ),
          },
          {
            id: "verified-evidence",
            heading: "What counts as verified evidence",
            body: (
              <>
                <p>
                  Verified evidence is commerce and payment data that Skeldir reaches independently
                  of the ad platform whose revenue is being evaluated. Verified evidence sources
                  include the operator&apos;s connected Stripe account, Shopify shop, or equivalent
                  connected commerce platform.
                </p>
                <p>
                  Evidence is standardized to integer-precision monetary units. Currency treatment,
                  refunds, chargebacks, taxes, and shipping are recorded alongside each evidence
                  record — not inferred or estimated after the fact. The standardization policy that
                  governs each evidence record is captured in the verified audit record Skeldir
                  maintains for every reconciliation.
                </p>
              </>
            ),
          },
          {
            id: "attribution-models",
            heading: "What attribution models prove — and what do they not prove",
            body: (
              <>
                <p>
                  Attribution models answer a bounded question: given a verified revenue total, how
                  should that total be distributed across the touchpoints that may have influenced
                  it?
                </p>
                <p>
                  Attribution models do not prove causal lift. Skeldir does not present attribution
                  model output as deterministic truth.
                </p>
                <p>
                  Each attribution model operates under documented assumptions — including
                  attribution window boundaries and touchpoint treatment rules — published on the{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>{" "}
                  surface. Model output is always paired with the verified revenue total it
                  distributes, so any reviewer can see exactly which number was modeled and which
                  was reconciled from evidence.
                </p>
              </>
            ),
          },
          {
            id: "discrepancy-classification",
            heading: "How discrepancies are classified",
            body: (
              <>
                <p>
                  When platform-reported revenue and verified commerce evidence disagree, Skeldir
                  classifies the discrepancy by type rather than averaging or suppressing the
                  difference. The published discrepancy taxonomy covers:
                </p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>Timing mismatch</li>
                  <li>Currency, tax, and shipping treatment mismatch</li>
                  <li>Refund and chargeback adjustment</li>
                  <li>Attribution window mismatch</li>
                  <li>Duplicate or order-ID mismatch</li>
                  <li>Missing commerce event</li>
                  <li>Unmatched platform claim</li>
                  <li>Delayed evidence arrival</li>
                </ul>
                <p>
                  The full discrepancy taxonomy with classification criteria is published on the{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>{" "}
                  surface.
                </p>
              </>
            ),
          },
          {
            id: "delayed-evidence",
            heading: "How delayed evidence is handled",
            body: (
              <p>
                Commerce and payment evidence arrives on different latencies than ad platform
                reporting. Skeldir does not lock a verification state at first observation. As later
                evidence arrives, the verified value is restated — with each restatement recorded in
                the verified audit record. A value that is fully verified on day one may shift
                verification state if a processor delay is subsequently detected; it returns to full
                verification as the missing evidence lands. The audit record preserves every
                restatement.
              </p>
            ),
          },
          {
            id: "confidence-expression",
            heading: "How confidence is expressed — and what does it not collapse",
            body: (
              <p>
                Skeldir does not emit a single confidence score that collapses verification state and
                model uncertainty into one number. Verification state is expressed as an enumerated
                verification status on the verified output — reflecting what the deterministic
                reconciliation engine has established from evidence, not what a model has estimated.
                Attribution model uncertainty is expressed as bounded ranges on the{" "}
                <Link className="underline" href="/attribution-methodology">
                  attribution methodology
                </Link>{" "}
                surface. Benchmark context — comparisons between platform-reported figures and
                verified commerce figures, peer cohort reference points, and historical baselines — is
                explanatory metadata. It informs analysis. It is not a source of financial truth.
              </p>
            ),
          },
          {
            id: "llm-boundary",
            heading: "Why LLMs do not compute financial truth in Skeldir",
            body: (
              <>
                <p>
                  Large language models are useful for explaining reconciliation outcomes,
                  summarizing discrepancies in plain language, and generating narrative answers
                  grounded in verified records. They are not used to compute the numbers
                  themselves.
                </p>
                <p>
                  In Skeldir, every authoritative number is produced by the deterministic
                  reconciliation engine. LLMs read verified outputs and the audit records that
                  accompany them. LLMs do not invent, average, or estimate values. LLM-generated
                  explanations are bounded to the deterministic record they reference. The governing
                  policy for this architectural boundary is published on the{" "}
                  <Link className="underline" href="/ai-boundary">
                    AI explanation boundary
                  </Link>{" "}
                  surface.
                </p>
              </>
            ),
          },
        ]}
        relatedProofLinks={[
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
          {
            href: "/ai-boundary",
            label: "AI / LLM boundary — explanation vs computation",
          },
        ]}
        limitations={
          <>
            <p>
              <strong>Unconnected revenue sources cannot be reconciled.</strong> Reconciliation
              depends on the operator connecting authoritative commerce and payment systems. If a
              revenue source is not connected, Skeldir cannot reconcile against it. Verified outputs
              for unconnected sources are marked accordingly — they are not estimated or guessed.
            </p>
            <p>
              <strong>Attribution models do not prove causality.</strong> Attribution model output
              answers the distribution question only. Any business decision that depends on causal
              lift requires controlled experimentation — attribution model output alone is not
              sufficient evidence of causal effect.
            </p>
            <p>
              <strong>Not every commerce platform is currently supported.</strong> When an
              integration is unsupported, Skeldir explicitly identifies it. The reconciliation engine
              does not assert verified truth it cannot reach.
            </p>
          </>
        }
      />
    </>
  );
}
