import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/attribution-methodology";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "Attribution methodology — Bounded questions, explicit assumptions";
const PAGE_DESCRIPTION =
  "Skeldir's attribution methodology answers bounded questions about how to distribute verified revenue across touchpoints. Each attribution model has named assumptions and stated limitations; no model proves causality on its own.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function AttributionMethodologyProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, {
            label: "Attribution methodology",
          }),
        ]}
      />
      <TrustProofPage
        headline="Attribution methodology"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page describes what attribution models can answer, what they cannot answer, and how Skeldir bounds the questions they are asked.",
        }}
        sections={[
          {
            id: "what-attribution-answers",
            heading: "What an attribution model answers",
            body: (
              <p>
                An attribution model answers a bounded question of the form
                "given a fixed window and a fixed set of touchpoints, how
                should this verified revenue be distributed across the
                touchpoints?". The model takes verified revenue as input — it
                does not invent revenue, and it does not change the
                deterministic value reconciled by the revenue verification
                pipeline.
              </p>
            ),
          },
          {
            id: "assumptions",
            heading: "Named assumptions",
            body: (
              <>
                <p>
                  Every supported attribution model carries a named set of
                  assumptions:
                </p>
                <ul className="list-disc pl-6 space-y-1">
                  <li>
                    <strong>Window length</strong> — how long after a
                    touchpoint a conversion may still be assigned to it.
                  </li>
                  <li>
                    <strong>Touchpoint weighting</strong> — how credit is
                    distributed across touchpoints (e.g. first-touch,
                    last-touch, linear, position-based, time-decay,
                    data-driven).
                  </li>
                  <li>
                    <strong>Eligibility rules</strong> — which touchpoints are
                    even considered (paid only, paid plus organic, etc.).
                  </li>
                  <li>
                    <strong>Exclusions</strong> — which categories of
                    conversion are excluded by policy (refunds, duplicates,
                    test orders).
                  </li>
                </ul>
                <p>
                  The chosen assumption set is captured in the policy authority
                  of every TrustEnvelope so a reviewer can always reproduce the
                  model output.
                </p>
              </>
            ),
          },
          {
            id: "bounded-questions",
            heading: "Bounded questions, not universal claims",
            body: (
              <p>
                The attribution model is{" "}
                <strong>bounded</strong> to the data it was fed and the
                assumptions it was given. It does not extrapolate beyond the
                connected platforms. It does not infer touchpoints it did not
                observe. It does not produce a single "true" attribution number
                independent of its assumptions.
              </p>
            ),
          },
          {
            id: "not-causality",
            heading: "Why attribution is not causality",
            body: (
              <p>
                An attribution model distributes credit; it does not measure
                causal lift. A last-touch model does not prove the last touch
                caused the conversion; a data-driven model does not prove the
                touchpoints it weights heavily would not have converted
                without intervention. Causal lift requires experimentation
                (geo holdouts, conversion-lift studies, incrementality
                tests). Skeldir surfaces attribution model output alongside
                its assumptions so operators can see what the model is and is
                not asserting.
              </p>
            ),
          },
          {
            id: "interaction-with-envelope",
            heading: "Interaction with TrustEnvelopes",
            body: (
              <p>
                Attribution model output is layered on top of verified
                revenue. The verified revenue itself sits in a deterministic{" "}
                <Link className="underline" href="/trust-envelope">
                  TrustEnvelope
                </Link>
                . The attribution distribution sits in a separate, clearly
                labeled record that references the underlying envelope. This
                keeps the deterministic and the model-derived layers from
                being collapsed in dashboards or in LLM-generated
                explanations.
              </p>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              No attribution model proves causality. Treat model output as a
              decision-support signal, not as the ground truth of marketing
              effectiveness.
            </p>
            <p>
              Model output depends on completeness of touchpoint capture. Lost
              touchpoints (ITP, ad blockers, cookieless contexts, off-platform
              influence) will not appear in the model and will distort the
              distribution.
            </p>
            <p>
              Changing assumptions between reporting periods makes
              period-over-period comparison invalid unless the change is
              explicitly noted in the policy authority and the operator
              re-runs prior periods under the new assumptions.
            </p>
          </>
        }
      />
    </>
  );
}
