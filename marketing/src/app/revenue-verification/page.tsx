import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/revenue-verification";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "Revenue verification — How commerce and payment evidence support or reject platform claims";
const PAGE_DESCRIPTION =
  "Skeldir verifies platform-reported ad revenue against commerce evidence (orders) and payment evidence (settled funds). When the evidence supports the platform claim it is marked verified; when it does not, the discrepancy is classified, not averaged away.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function RevenueVerificationProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Revenue verification" }),
        ]}
      />
      <TrustProofPage
        headline="Revenue verification"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page describes how Skeldir uses commerce and payment evidence to verify or reject platform-reported revenue. It does not enumerate every supported integration; the integration inventory lives on the documentation surface.",
        }}
        sections={[
          {
            id: "ad-platforms-grade-themselves",
            heading: "Why platform-reported revenue alone is not enough",
            body: (
              <p>
                Each major ad platform reports the revenue it believes its
                clicks produced. Those reports rely on the platform's own
                tracking, its own attribution window, and its own definition of
                conversion. That is not the same as money that arrived in the
                operator's bank account. Reconciliation against independent
                commerce and payment evidence is how Skeldir tells the two
                apart.
              </p>
            ),
          },
          {
            id: "commerce-evidence",
            heading: "Commerce evidence",
            body: (
              <>
                <p>
                  Commerce evidence is the operator's record of the order
                  itself: Shopify orders (or the equivalent commerce platform),
                  with line items, refunds, taxes, shipping, currency, and
                  customer identifiers. It is the closest available proxy to
                  what the customer actually bought.
                </p>
                <p>
                  Skeldir ingests commerce evidence directly from the
                  operator's commerce platform, never from the ad platform.
                  This is what gives the verification independence.
                </p>
              </>
            ),
          },
          {
            id: "payment-evidence",
            heading: "Payment evidence",
            body: (
              <p>
                Payment evidence is the operator's record of money settled:
                Stripe charges, refunds, disputes, and payouts. It anchors the
                order to a real funds movement. A commerce record without a
                matching payment record is not yet verified revenue; it is a
                pending claim.
              </p>
            ),
          },
          {
            id: "reconciliation",
            heading: "How reconciliation works",
            body: (
              <>
                <p>
                  Reconciliation joins three streams — platform-reported
                  revenue, commerce evidence, and payment evidence — under a
                  shared time window and a shared identity key (order id,
                  charge id, or operator-defined join). The deterministic
                  engine then computes the reconciled value in integer cents
                  and writes the result into a{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>{" "}
                  with the matching confidence status and policy authority.
                </p>
                <p>
                  When the three streams agree, the envelope is{" "}
                  <code>verified</code>. When one stream is missing, late, or
                  contradicts the others, the envelope is{" "}
                  <code>partially_verified</code> or <code>unverified</code>{" "}
                  and the discrepancy is classified.
                </p>
              </>
            ),
          },
          {
            id: "discrepancy-classes",
            heading: "Discrepancy handling",
            body: (
              <p>
                A discrepancy between platform claim and commerce/payment
                evidence is classified rather than averaged. Every
                classification lives in the{" "}
                <Link className="underline" href="/discrepancy-taxonomy">
                  discrepancy taxonomy
                </Link>{" "}
                so the operator can see exactly which class produced the
                <code> partially_verified</code> or <code>unverified</code>{" "}
                state and what evidence is missing.
              </p>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              Verification is only as strong as the operator's commerce and
              payment connections. Unconnected revenue streams cannot be
              verified by Skeldir and are not reported as verified.
            </p>
            <p>
              Revenue verification answers the question "did this money
              arrive?". It does not answer "would this money have arrived
              without the ad spend?". The latter is an incrementality question
              that no attribution model alone can answer.
            </p>
            <p>
              Some commerce platforms emit events asynchronously; verification
              can shift between confidence statuses as delayed events land.
              The envelope's audit trail records every shift.
            </p>
          </>
        }
      />
    </>
  );
}
