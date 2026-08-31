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
const PAGE_TITLE = "Revenue Verification | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir verifies platform-reported ad revenue against commerce evidence (orders) and payment evidence (settled funds). When the evidence supports the platform claim it is marked verified; when it does not, the discrepancy is classified, not averaged away.";

const KEY_FACTS = [
  "Platform-reported revenue is a claim from the ad platform — not independent ground truth.",
  "Commerce and payment evidence are ingested independently of the ad platform that reported the revenue.",
  "Discrepancies between platform claims and evidence are classified by type, not averaged or suppressed.",
  "Revenue verification answers whether money arrived as claimed; it does not prove causal lift from ad spend.",
  "Unconnected or unsupported revenue sources cannot be reported as verified.",
];

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
            name: "Revenue Verification",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Revenue verification" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Revenue Verification"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-02-25",
          notes:
            "This page is informational and explains Skeldir's public revenue-verification methodology for operators and finance reviewers. It does not replace contractual terms and is not a contractual guarantee.",
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
            id: "platform-claim-boundary",
            heading: "Why platform-reported revenue is not sufficient",
            body: (
              <p>
                Each major ad platform reports the revenue it believes its clicks produced. Those
                reports rely on the platform&apos;s own tracking, its own attribution window, and its
                own definition of conversion. That is not the same as money that arrived in the
                operator&apos;s bank account. Reconciliation against independent commerce and payment
                evidence is how Skeldir tells the two apart.
              </p>
            ),
          },
          {
            id: "commerce-evidence",
            heading: "Commerce evidence",
            body: (
              <>
                <p>
                  Commerce evidence is the operator&apos;s record of the order itself — for example
                  Shopify orders or an equivalent commerce platform — with line items, refunds, taxes,
                  shipping, and currency. It is the closest available proxy to what the customer
                  actually bought, expressed as commerce records and order-level evidence.
                </p>
                <p>
                  Skeldir ingests commerce evidence directly from the operator&apos;s commerce
                  platform, never from the ad platform. That independence is what makes verification
                  credible to finance reviewers.
                </p>
              </>
            ),
          },
          {
            id: "payment-evidence",
            heading: "Payment evidence",
            body: (
              <p>
                Payment evidence is the operator&apos;s record of money settled: payment processor
                charges, refunds, disputes, and payouts. It anchors the order to a real funds
                movement. Payment evidence must corroborate the commerce record before revenue is
                treated as verified; commerce alone remains a pending claim until settlement is
                supported.
              </p>
            ),
          },
          {
            id: "reconciliation",
            heading: "How Skeldir verifies revenue claims",
            body: (
              <>
                <p>
                  Skeldir compares platform-reported revenue against independent commerce and
                  payment evidence under documented reconciliation policy and consistent evidence
                  scope. Skeldir produces a deterministic verified value in integer-precision
                  monetary units and records the outcome in a{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>{" "}
                  with verification status and policy context.
                </p>
                <p>
                  When platform claims, commerce evidence, and payment evidence align under policy,
                  the outcome is verified. When evidence is missing, late, or contradicts the
                  platform claim, the outcome is partially verified or unverified and the gap is
                  explained — not averaged away.
                </p>
              </>
            ),
          },
          {
            id: "discrepancy-classes",
            heading: "How discrepancies are handled",
            body: (
              <p>
                A discrepancy between a platform claim and commerce or payment evidence is
                classified rather than averaged. Every classification is published in the{" "}
                <Link className="underline" href="/discrepancy-taxonomy">
                  discrepancy taxonomy
                </Link>{" "}
                so operators can see which category produced a partially verified or unverified
                state and what evidence is still missing.
              </p>
            ),
          },
          {
            id: "delayed-evidence",
            heading: "Delayed evidence handling",
            body: (
              <p>
                Some commerce platforms emit events asynchronously. Verification can shift between
                confidence statuses as delayed evidence arrives. The audit trail records every
                restatement so finance teams can see when a value moved from pending to verified or
                back when late-arriving evidence changes the picture.
              </p>
            ),
          },
          {
            id: "what-it-proves",
            heading: "What revenue verification proves",
            body: (
              <p>
                Revenue verification proves whether platform-reported revenue is supported by
                independent commerce and payment evidence under Skeldir&apos;s deterministic
                reconciliation posture — with classified discrepancies when it is not. It gives
                operators and agents an audit-ready answer to &ldquo;did this money arrive as
                claimed?&rdquo; at the evidence category level.
              </p>
            ),
          },
          {
            id: "what-it-does-not-prove",
            heading: "What revenue verification does not prove",
            body: (
              <p>
                Revenue verification does not answer &ldquo;would this money have arrived without
                the ad spend?&rdquo; That is an incrementality and causal-lift question bounded on
                the{" "}
                <Link className="underline" href="/attribution-methodology">
                  attribution methodology
                </Link>{" "}
                surface — not something revenue verification alone can establish. See also the{" "}
                <Link className="underline" href="/ai-boundary">
                  AI / LLM boundary
                </Link>{" "}
                for what automated explanations may and may not assert.
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
          {
            href: "/discrepancy-taxonomy",
            label: "Discrepancy taxonomy — classification criteria",
          },
          {
            href: "/attribution-methodology",
            label: "Attribution methodology — bounded model assumptions",
          },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcome container" },
          { href: "/ai-boundary", label: "AI / LLM boundary — explanation vs computation" },
          { href: "/security", label: "Security — public security posture" },
        ]}
        limitations={
          <>
            <p>
              <strong>Operational limitations.</strong> Verification is only as strong as the
              operator&apos;s commerce and payment connections. Unconnected revenue streams cannot
              be verified by Skeldir and are not reported as verified. Unsupported platforms are
              explicitly identified rather than guessed.
            </p>
            <p>
              This page describes how Skeldir uses commerce and payment evidence categories to
              verify or reject platform-reported revenue. It does not enumerate every supported
              integration; integration inventory and availability are documented on the{" "}
              <Link className="underline" href="/docs">
                documentation
              </Link>{" "}
              surface when applicable.
            </p>
          </>
        }
      />
    </>
  );
}
