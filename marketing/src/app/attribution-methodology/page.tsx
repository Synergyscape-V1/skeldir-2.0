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
const PAGE_TITLE = "Attribution Methodology | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir's attribution methodology answers bounded questions about how to distribute verified revenue across observed touchpoints under documented assumptions. It explains what attribution output means, what it does not prove, and why attribution should not be confused with verified revenue or causal lift.";

const KEY_FACTS = [
  "Attribution models take verified revenue as input and distribute credit across observed touchpoints; they do not invent revenue or alter deterministic verified values.",
  "Each attribution view depends on documented assumption categories such as time scope, touchpoint treatment, and inclusion boundaries.",
  "Attribution distributes credit across touchpoints; it does not measure causal lift. Causal proof requires controlled experimentation.",
  "Attribution output is presented separately from the verified revenue value it distributes so the two layers are not collapsed.",
  "Model output depends on complete touchpoint capture; unobserved touchpoints are omitted and can distort distribution.",
];

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
            name: "Attribution Methodology",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Attribution methodology" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Attribution Methodology"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-05-25",
          notes:
            "This page is informational and explains Skeldir's public attribution methodology for finance and marketing operators. It does not replace contractual terms.",
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
            id: "what-attribution-answers",
            heading: "What attribution models answer",
            body: (
              <p>
                An attribution model answers a bounded question: given documented time scope and a
                fixed set of observed touchpoints, how should verified revenue be distributed across
                those touchpoints? The model takes{" "}
                <Link className="underline" href="/revenue-verification">
                  verified revenue
                </Link>{" "}
                as input — it does not invent revenue, and it does not change the deterministic
                value produced by revenue verification.
              </p>
            ),
          },
          {
            id: "assumptions",
            heading: "What assumptions mean at a public level",
            body: (
              <>
                <p>
                  Each attribution view depends on documented assumption categories such as time
                  scope, touchpoint treatment, and inclusion boundaries. Those categories describe
                  what period and which touchpoints the view considers — not a single universal
                  truth independent of context.
                </p>
                <p>
                  The chosen assumption set is recorded with the output so a reviewer can understand
                  which assumptions shaped the distribution and where the model&apos;s limits apply.
                </p>
              </>
            ),
          },
          {
            id: "bounded-questions",
            heading: "Why attribution models are bounded",
            body: (
              <p>
                The attribution view is <strong>bounded</strong> to the data it was fed and the
                assumptions it was given. It does not extrapolate beyond connected platforms. It does
                not infer touchpoints it did not observe. It does not produce a single &ldquo;true&rdquo;
                attribution number independent of its assumptions. See the broader proof boundary on{" "}
                <Link className="underline" href="/methodology">
                  methodology
                </Link>
                .
              </p>
            ),
          },
          {
            id: "not-causality",
            heading: "Why attribution is not causality",
            body: (
              <p>
                An attribution model <strong>distributes credit</strong> across touchpoints; it does
                not measure <strong>causal lift</strong> or incrementality. Observed timing
                relationships in a model do not prove that a touchpoint caused a conversion. Causal
                lift requires controlled experimentation — geo holdouts, conversion-lift studies, and
                incrementality tests. Skeldir surfaces attribution output alongside its documented
                assumptions so operators can see exactly what the model is and is not asserting.
              </p>
            ),
          },
          {
            id: "deterministic-revenue-separation",
            heading: "How attribution output relates to deterministic revenue",
            body: (
              <>
                <p>
                  <strong>Verified revenue</strong> is the deterministic financial value produced by{" "}
                  <Link className="underline" href="/revenue-verification">
                    revenue verification
                  </Link>
                  . <strong>Attribution output</strong> is model-derived distribution of that verified
                  value across observed touchpoints under documented assumptions. The two are kept
                  separate in presentation so dashboards and automated explanations do not treat
                  allocation as if it were settlement truth.
                </p>
                <p>
                  When a discrepancy affects the verified total, classification lives in the{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>
                  ; attribution does not override or smooth those outcomes.
                </p>
              </>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
          {
            href: "/revenue-verification",
            label: "Revenue verification — verified revenue input",
          },
          {
            href: "/discrepancy-taxonomy",
            label: "Discrepancy taxonomy — classification when evidence disagrees",
          },
          { href: "/ai-boundary", label: "AI / LLM boundary — explanation vs computation" },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcome container" },
        ]}
        limitations={
          <>
            <p>
              <strong>Current limitations.</strong> No attribution model proves causality. Treat
              model output as a decision-support signal, not as the ground truth of marketing
              effectiveness.
            </p>
            <p>
              Model output depends on completeness of touchpoint capture. Lost touchpoints — whether
              from tracking prevention, ad blockers, cookieless contexts, or off-platform influence —
              will not appear in the model and will distort the distribution.
            </p>
            <p>
              Changing assumptions between reporting periods makes period-over-period comparison
              invalid unless the change is explicitly documented and prior periods are re-evaluated
              under the new assumption set.
            </p>
          </>
        }
      />
    </>
  );
}
