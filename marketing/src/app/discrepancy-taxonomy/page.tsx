import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/discrepancy-taxonomy";
const PAGE_TITLE = "Discrepancy Taxonomy | Skeldir";
const PAGE_DESCRIPTION =
  "When platform-reported revenue and verified commerce or payment evidence disagree, Skeldir classifies the discrepancy by type rather than averaging or hiding the difference. This page defines recognized discrepancy categories at the outcome level.";

const KEY_FACTS = [
  "Discrepancies are classified by type; they are never averaged, overridden, or guessed away.",
  "Each class describes a recognizable category of disagreement between a platform claim and independent commerce or payment evidence.",
  "Given the same evidence and the same documented reconciliation policy, the same category is assigned consistently.",
  "Refunds and chargebacks produce corrected net values with the original claim preserved in the audit trail.",
  "Some discrepancies require operator input to resolve; Skeldir surfaces the disagreement rather than guessing.",
];

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function DiscrepancyTaxonomyProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Discrepancy Taxonomy",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Discrepancy taxonomy" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Discrepancy Taxonomy"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-02-25",
          notes:
            "This page explains Skeldir's public discrepancy categories for operators and finance reviewers. It is informational and does not replace contractual terms.",
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
            id: "timing-mismatch",
            heading: "Timing mismatch",
            body: (
              <p>
                The platform reports revenue under one timestamp — click time, conversion time, or
                post-attribution-window assignment — while commerce evidence records the order under
                a different timestamp. The two records describe the same transaction but arrive under
                different time keys. Skeldir evaluates timing differences under the operator&apos;s
                documented reconciliation policy and marks the outcome verified when the compared
                values match after that policy is applied. Each class helps reviewers understand why
                the verification state changed.
              </p>
            ),
          },
          {
            id: "currency-tax-shipping-mismatch",
            heading: "Currency, tax, or shipping mismatch",
            body: (
              <p>
                The platform reports a gross figure that includes or excludes tax, shipping, or
                non-merchandise charges that the commerce record treats differently. Currency
                conversion at a different rate produces a similar mismatch. Skeldir presents the
                accounting basis used for comparison so the difference is visible rather than
                smoothed away.
              </p>
            ),
          },
          {
            id: "refund-chargeback-adjustment",
            heading: "Refund and chargeback adjustment",
            body: (
              <p>
                A refund or chargeback lands after the platform has already reported revenue. The
                commerce or payment side records the reversal; the platform does not retroactively
                correct its report. Skeldir produces a corrected outcome that reflects net revenue
                after refund or chargeback, with the original claim preserved in the audit trail.
              </p>
            ),
          },
          {
            id: "attribution-window-mismatch",
            heading: "Attribution-window mismatch",
            body: (
              <p>
                The platform&apos;s reported revenue uses an attribution window different from the
                operator&apos;s documented policy boundary. The same conversion may be claimed by the
                platform but excluded by operator policy, or vice versa. Skeldir reports the
                difference between platform attribution and the operator&apos;s documented policy
                boundary so the gap is explicit. See{" "}
                <Link className="underline" href="/attribution-methodology">
                  attribution methodology
                </Link>{" "}
                for how attribution views are bounded.
              </p>
            ),
          },
          {
            id: "duplicate-order-reference-mismatch",
            heading: "Duplicate or order-reference mismatch",
            body: (
              <p>
                The platform reports the same conversion more than once — multiple touchpoints,
                multiple campaigns — or order references on the commerce side do not line up with
                platform-reported conversions. Skeldir prevents the same verified sale from being
                counted more than once. Duplicate evidence is preserved in the audit trail.
              </p>
            ),
          },
          {
            id: "missing-commerce-event",
            heading: "Missing commerce evidence",
            body: (
              <p>
                The platform claims revenue for a conversion that has no corresponding commerce
                record — a missing commerce event. The outcome is marked unverified with an
                explanation that commerce evidence is missing. Skeldir does not invent commerce records to make a platform claim verify.
                See{" "}
                <Link className="underline" href="/revenue-verification">
                  revenue verification
                </Link>{" "}
                for how commerce and payment evidence categories anchor verification.
              </p>
            ),
          },
          {
            id: "unmatched-platform-claim",
            heading: "Unmatched platform claim",
            body: (
              <p>
                The commerce side records a sale, but no advertising platform claims attribution for
                it. Skeldir records the sale as organic or unattributed under the operator&apos;s
                documented policy and does not assign paid attribution to fill the gap.
              </p>
            ),
          },
          {
            id: "delayed-arrival",
            heading: "Delayed arrival",
            body: (
              <p>
                Either side of verification is late: a delayed payment settlement, a delayed platform
                report, or a delayed webhook. The outcome is initially marked partially verified and
                Skeldir restates it as late evidence arrives, with each restatement recorded in the
                audit trail. See{" "}
                <Link className="underline" href="/revenue-verification">
                  revenue verification
                </Link>{" "}
                for delayed evidence handling.
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
            label: "Attribution methodology — bounded attribution views",
          },
          { href: "/ai-boundary", label: "AI / LLM boundary — explanation vs computation" },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcome container" },
        ]}
        limitations={
          <>
            <p>
              <strong>Current limitations.</strong> This taxonomy describes discrepancy categories
              Skeldir actively recognizes. New patterns observed in production may extend the taxonomy;
              extensions are reflected in this page&apos;s last-updated date.
            </p>
            <p>
              Classification is consistent for a fixed documented reconciliation policy. Operators
              that change policy — for example, a different attribution window — may see historical
              discrepancies re-categorized; the audit trail preserves prior outcomes.
            </p>
            <p>
              Some discrepancies cannot be resolved without operator input, such as whether a refund
              should be treated as a chargeback for reporting purposes. In those cases Skeldir
              surfaces the disagreement and the available interpretation options rather than guessing.
            </p>
            <p>
              Discrepancy classification explains why platform claims and verified evidence differ; it
              does not erase, average, or guess away the disagreement.
            </p>
          </>
        }
      />
    </>
  );
}
