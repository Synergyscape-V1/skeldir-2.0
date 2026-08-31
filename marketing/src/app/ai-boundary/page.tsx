import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/ai-boundary";
const PAGE_TITLE = "AI Boundary | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir uses LLMs for explanations grounded in deterministic verified records. LLMs do not compute, invent, or modify authoritative financial values — the deterministic reconciliation layer does.";

const KEY_FACTS = [
  "LLMs in Skeldir generate explanations, summaries, and narrative answers grounded in deterministic verified records; they do not compute, invent, or modify financial values.",
  "Each explanation is tied to the verified record it describes; extrapolation beyond that record is not treated as financial evidence.",
  "The deterministic system is the sole authority for financial truth; LLM outputs cannot assert values absent from the verified record they summarize.",
  "AI agents consuming Skeldir must treat deterministic values and verification statuses as authoritative and LLM explanations as advisory.",
  "Skeldir avoids treating repeated explanations as new financial evidence when the underlying verified record is unchanged.",
];

const BLUF_PARAGRAPHS = (
  <>
    <p>
      This page explains the structural boundary between Skeldir&apos;s deterministic financial
      truth layer and its LLM-powered explanation layer. It is for operators, compliance reviewers,
      and integration partners who need to verify that no LLM-generated content can override,
      modify, or invent the authoritative financial values surfaced in{" "}
      <Link className="underline" href="/trust-envelope">
        TrustEnvelopes
      </Link>
      .
    </p>
    <p>
      <strong>Deterministic value = authoritative.</strong>{" "}
      <strong>Verification status = authoritative.</strong>{" "}
      <strong>LLM explanation = advisory.</strong> Agent actions remain constrained by policy and
      authorization context.
    </p>
  </>
);

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function AiBoundaryProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "AI Boundary",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "AI boundary" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="AI Boundary"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-05-23",
          notes:
            "This page explains Skeldir's public AI boundary. Public integration behavior and API availability are documented separately where applicable.",
        }}
        bluf={{
          paragraphs: BLUF_PARAGRAPHS,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "llm-role",
            heading: "What LLMs do in Skeldir",
            body: (
              <>
                <p>
                  LLMs in Skeldir generate plain-language explanations of reconciliation outcomes,
                  narrative descriptions of discrepancy categories, and answers to operator questions
                  that reference existing deterministic verified records. Every explanation is
                  grounded in a specific TrustEnvelope or set of envelopes. The LLM cannot produce
                  an explanation that references a value not present in the referenced verified
                  record.
                </p>
                <p>
                  See{" "}
                  <Link className="underline" href="/methodology">
                    methodology
                  </Link>{" "}
                  for how deterministic reconciliation and explanation boundaries fit together.
                </p>
              </>
            ),
          },
          {
            id: "llm-does-not-calculate",
            heading: "Why LLMs do not compute financial truth",
            body: (
              <>
                <p>
                  Authoritative financial numbers in Skeldir come from{" "}
                  <Link className="underline" href="/revenue-verification">
                    revenue verification
                  </Link>
                  , not from an LLM. The deterministic system produces authoritative financial
                  values using precise monetary representation after commerce and payment evidence
                  are evaluated. The LLM reads those values and explains them.
                </p>
                <p>
                  LLM explanations are not allowed to change authoritative financial values. LLM
                  content is bounded to the deterministic values present in the referenced verified
                  record and cannot assert figures not derived from that record.
                </p>
                <p>
                  In short: the model explains; it <strong>does not calculate</strong> financial
                  truth.
                </p>
              </>
            ),
          },
          {
            id: "deterministic-grounding",
            heading: "Deterministic grounding",
            body: (
              <p>
                Every Skeldir explanation cites the verified record it summarizes. If an operator
                asks why a specific ad spend is marked unverified, the answer must point to the
                TrustEnvelope, the verification status, the missing evidence, and the documented
                policy context that produced the outcome. When Skeldir cannot find verified evidence
                for a question, the answer must say so explicitly rather than manufacture a record.
              </p>
            ),
          },
          {
            id: "explanations-bounded",
            heading: "Bounded explanations",
            body: (
              <p>
                Explanations are bounded by the verified record they reference. The model is not
                permitted to extrapolate to a different time window, a different platform, or a
                different policy context without an explicit operator instruction and a verified
                record that supports the broader question. This prevents drift from explanation to
                speculation.
              </p>
            ),
          },
          {
            id: "agent-policy",
            heading: "Policy for AI agents consuming Skeldir",
            body: (
              <>
                <p>
                  AI agents that consume Skeldir data through the integration surface must treat
                  the deterministic value and verification status as authoritative and the
                  LLM-generated explanation as advisory. Agents are not permitted to act on an
                  explanation that contradicts the underlying verified record.
                </p>
                <p>
                  Some downstream actions may require approval or may be limited by policy. Agents
                  must respect documented authorization boundaries on the{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>{" "}
                  surface and in published integration guidance.
                </p>
                <p>
                  Discrepancy and attribution questions should defer to{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>{" "}
                  and{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>{" "}
                  rather than LLM inference alone.
                </p>
              </>
            ),
          },
          {
            id: "scope-trust-boundary",
            heading: "Scope and trust boundary",
            body: (
              <p>
                LLMs are probabilistic generators. Even when bounded to a verified record, an
                explanation can phrase a fact imprecisely or omit a relevant nuance. Operators
                reviewing Skeldir output should always verify the deterministic value and the
                verification status in the TrustEnvelope, not rely solely on surrounding prose.
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcome container" },
          {
            href: "/revenue-verification",
            label: "Revenue verification — authoritative financial values",
          },
          {
            href: "/attribution-methodology",
            label: "Attribution methodology — bounded model output",
          },
          {
            href: "/discrepancy-taxonomy",
            label: "Discrepancy taxonomy — classified disagreement",
          },
          { href: "/api", label: "API — integration surface" },
          { href: "/docs", label: "Documentation — concepts and availability" },
        ]}
        limitations={
          <>
            <p>
              <strong>Current limitations.</strong> This boundary applies to Skeldir-produced
              explanations. Skeldir cannot enforce the same boundary on third-party agents that
              consume Skeldir data and re-explain it elsewhere. Those agents should treat
              deterministic TrustEnvelope values as authoritative and any generated explanation as
              advisory.
            </p>
            <p>
              Generated prose may be imprecise even when grounded in verified records. Always check
              deterministic values and verification statuses before acting on narrative output.
            </p>
          </>
        }
      />
    </>
  );
}
