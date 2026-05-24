import type { Metadata } from "next";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/discrepancy-taxonomy";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "Discrepancy taxonomy — How Skeldir classifies platform vs commerce mismatches";
const PAGE_DESCRIPTION =
  "The exhaustive set of discrepancy classes Skeldir recognizes when platform-reported revenue and verified commerce/payment evidence disagree. Each class has a definition, an evidence signature, and an effect on the TrustEnvelope confidence status.";

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
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Discrepancy taxonomy" }),
        ]}
      />
      <TrustProofPage
        headline="Discrepancy taxonomy"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "Each class below describes how Skeldir recognizes the discrepancy, what evidence pattern triggers the classification, and how the resulting TrustEnvelope is marked.",
        }}
        sections={[
          {
            id: "timing-mismatch",
            heading: "Timing mismatch",
            body: (
              <p>
                The platform reports revenue under one timestamp (click time,
                conversion time, or post-attribution-window assignment), while
                commerce evidence records the order under a different
                timestamp. The two records describe the same money but arrive
                under different time keys. Skeldir aligns them under a chosen
                policy and marks the envelope <code>verified</code> if the
                aligned values match.
              </p>
            ),
          },
          {
            id: "currency-tax-shipping-mismatch",
            heading: "Currency, tax, or shipping mismatch",
            body: (
              <p>
                The platform reports a gross figure that includes (or excludes)
                tax, shipping, or non-merchandise charges that the commerce
                record treats differently. Currency conversion at a different
                rate produces a similar mismatch. Skeldir normalizes both
                sides into the policy-defined accounting basis and records the
                normalization in benchmark metadata.
              </p>
            ),
          },
          {
            id: "refund-chargeback-adjustment",
            heading: "Refund and chargeback adjustment",
            body: (
              <p>
                A refund or chargeback lands after the platform has already
                reported revenue. The commerce/payment side records the
                reversal; the platform does not retroactively correct its
                report. Skeldir produces a corrected envelope that reflects
                net revenue after refund / chargeback, with the original
                envelope retained in the audit trail.
              </p>
            ),
          },
          {
            id: "attribution-window-mismatch",
            heading: "Platform attribution-window mismatch",
            body: (
              <p>
                The platform's reported revenue uses an attribution window
                different from the operator's policy window. The same
                conversion may be claimed by the platform but excluded by the
                operator policy (or vice versa). Skeldir records both the
                platform attribution-window and the operator window so the
                difference is explicit, and assigns the conversion under the
                operator's policy authority.
              </p>
            ),
          },
          {
            id: "duplicate-order-id-mismatch",
            heading: "Duplicate or order-id mismatch",
            body: (
              <p>
                The platform reports the same conversion more than once
                (multiple touchpoints, multiple campaigns), or the operator's
                order id does not align with the platform's conversion id.
                Skeldir deduplicates against the commerce id and refuses to
                double-count. The duplicate evidence is preserved in the
                envelope's audit trail.
              </p>
            ),
          },
          {
            id: "missing-commerce-event",
            heading: "Missing commerce event",
            body: (
              <p>
                The platform claims revenue for a conversion that has no
                corresponding commerce record. The envelope is marked
                <code> unverified</code> with a fallback reason naming the
                missing commerce event. Skeldir does not invent a commerce
                record to make the platform claim verify.
              </p>
            ),
          },
          {
            id: "unmatched-platform-claim",
            heading: "Unmatched platform claim",
            body: (
              <p>
                The commerce side records a sale, but no ad platform claims
                attribution for it. Skeldir records the sale as organic /
                unattributed under the operator's policy, and does not assign
                paid attribution to fill the gap.
              </p>
            ),
          },
          {
            id: "delayed-arrival",
            heading: "Delayed arrival",
            body: (
              <p>
                Either side of the reconciliation is late: a delayed Stripe
                payout, a delayed platform report, or a delayed webhook. The
                envelope is initially marked <code>partially_verified</code>{" "}
                and Skeldir restates it as the late evidence lands, with each
                restatement recorded in the audit trail.
              </p>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              This taxonomy describes the classes Skeldir actively classifies.
              New patterns observed in production may extend the taxonomy;
              extensions are recorded in this page's last-reviewed date.
            </p>
            <p>
              Classification is deterministic given a fixed policy authority.
              Operators that change policy (e.g. a different attribution
              window) will reclassify historical discrepancies; the audit
              trail preserves both classifications.
            </p>
            <p>
              Some discrepancies cannot be resolved without operator input
              (e.g. whether a refund counts as a chargeback). In those cases
              Skeldir presents the discrepancy and the candidate
              classifications rather than guessing.
            </p>
          </>
        }
      />
    </>
  );
}
