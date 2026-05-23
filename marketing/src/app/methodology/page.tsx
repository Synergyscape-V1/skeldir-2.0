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
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "Methodology — How Skeldir verifies revenue and bounds attribution";
const PAGE_DESCRIPTION =
  "Skeldir's methodology: how deterministic revenue verification works, how attribution models answer bounded questions, how discrepancies are classified, and the strict boundary between deterministic engine output and LLM-generated explanations.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function MethodologyProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
            dateModified: LAST_REVIEWED,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Methodology" }),
        ]}
      />
      <TrustProofPage
        headline="Methodology"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page explains how Skeldir produces deterministic values, where attribution models answer bounded questions, and where LLM-generated explanations are allowed. It is technical disclosure only — it is not a contract.",
        }}
        sections={[
          {
            id: "deterministic-reconciliation",
            heading: "Deterministic reconciliation",
            body: (
              <>
                <p>
                  Skeldir reconciles platform-reported ad revenue against
                  verified commerce and payment evidence. Reconciliation is a
                  deterministic process: given the same inputs and policy
                  authority, the output is byte-for-byte reproducible.
                </p>
                <p>
                  Authoritative financial numbers come from verified evidence,
                  not from a model. Stripe charges, Shopify orders, and the
                  payment processor's record of settled funds are the ground
                  truth. Platform-reported revenue is treated as a claim that
                  must be reconciled against that ground truth, never accepted
                  on its own.
                </p>
              </>
            ),
          },
          {
            id: "evidence-sources",
            heading: "What counts as verified evidence",
            body: (
              <>
                <p>
                  Verified evidence is commerce and payment data Skeldir can
                  reach independently of the ad platform whose revenue is being
                  evaluated. Today that means the operator's connected Stripe
                  account, Shopify shop, or equivalent commerce platform.
                </p>
                <p>
                  Evidence is normalized into integer cents, with currency,
                  refund, chargeback, tax, and shipping treatment recorded
                  alongside the raw record. The normalization rules are part of
                  the policy authority captured in every{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>
                  .
                </p>
              </>
            ),
          },
          {
            id: "attribution-models",
            heading: "What attribution models do and do not prove",
            body: (
              <>
                <p>
                  Attribution models answer bounded questions about how to
                  assign verified revenue across the touchpoints that may have
                  influenced it. They do not prove causal lift on their own,
                  and Skeldir does not present model output as deterministic
                  truth.
                </p>
                <p>
                  Each attribution model carries explicit assumptions (window
                  length, touchpoint weighting, exclusion rules) and is
                  documented separately on the{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>{" "}
                  surface. Model output is always paired with the verified
                  revenue total it is distributing, so any reviewer can see
                  exactly which number was modeled and which was reconciled.
                </p>
              </>
            ),
          },
          {
            id: "discrepancy-handling",
            heading: "How discrepancies are classified",
            body: (
              <>
                <p>
                  When platform-reported revenue and verified commerce evidence
                  disagree, Skeldir classifies the discrepancy rather than
                  silently averaging the difference. The full taxonomy of
                  discrepancy classes — timing mismatch, currency / tax /
                  shipping mismatch, refund and chargeback adjustment,
                  attribution-window mismatch, duplicate or order-id mismatch,
                  missing commerce event, unmatched platform claim, delayed
                  arrival — is published separately on the{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>{" "}
                  surface.
                </p>
              </>
            ),
          },
          {
            id: "delayed-events",
            heading: "How delayed events are handled",
            body: (
              <p>
                Commerce and payment evidence arrives on different latencies
                from the ad platform's reporting. Skeldir does not freeze a
                value at first sight; it restates the deterministic value as
                later evidence arrives, recording each restatement in the
                envelope's audit trail. A value marked <code>verified</code> at
                T+1 day may become <code>partially_verified</code> if a
                processor delay is detected, and vice versa as the missing
                evidence lands.
              </p>
            ),
          },
          {
            id: "confidence-and-benchmark",
            heading: "How confidence and benchmark context are bounded",
            body: (
              <p>
                Skeldir does not emit a single "confidence score" that
                collapses verification state and model uncertainty together.
                Verification state is the enumerated confidence status carried
                in every TrustEnvelope; attribution model uncertainty is
                expressed as bounded ranges on the attribution methodology
                surface. Benchmark context (platform vs commerce delta, peer
                cohort, historical baseline) is explanatory metadata, not a
                source of truth.
              </p>
            ),
          },
          {
            id: "ai-boundary",
            heading: "Why LLMs do not compute financial truth",
            body: (
              <>
                <p>
                  Large language models (LLMs) are useful for explaining
                  reconciliation outcomes, summarizing discrepancies in plain
                  language, and generating narrative answers grounded in
                  deterministic records. They are not used to compute the
                  numbers themselves.
                </p>
                <p>
                  In Skeldir, every authoritative number is produced by the
                  deterministic reconciliation engine. LLMs read those numbers
                  and their TrustEnvelope; LLMs do not invent, average, or
                  estimate values. LLM-generated explanations are bounded to
                  the deterministic record they reference. The detailed
                  policy lives on the{" "}
                  <Link className="underline" href="/ai-boundary">
                    AI boundary
                  </Link>{" "}
                  surface.
                </p>
              </>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              Reconciliation depends on the operator connecting authoritative
              commerce and payment systems. If a revenue source is not
              connected, Skeldir cannot reconcile against it; envelopes for
              that source will be marked <code>unverified</code> or{" "}
              <code>blocked</code> rather than guessed.
            </p>
            <p>
              The attribution model surface answers bounded questions only. It
              does not prove causality. Any business decision that depends on
              causal lift requires experimentation, not just attribution
              model output.
            </p>
            <p>
              Skeldir does not currently reconcile every commerce platform.
              Unsupported platforms are explicitly listed when an integration
              cannot proceed; in those cases the reconciliation engine refuses
              to assert deterministic truth.
            </p>
          </>
        }
      />
    </>
  );
}
