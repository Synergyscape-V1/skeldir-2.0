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
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "AI boundary — What LLMs may and may not do inside Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir uses LLMs for explanations, summaries, and narrative answers grounded in deterministic records. LLMs do not calculate authoritative financial numbers; the deterministic reconciliation engine does.";

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
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "AI boundary" }),
        ]}
      />
      <TrustProofPage
        headline="AI boundary"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page describes the boundary between the deterministic reconciliation engine and any LLM-backed explanation. It applies to Skeldir's own UI, to AI Agents reading Skeldir through the integration surface, and to any downstream consumer of TrustEnvelopes.",
        }}
        sections={[
          {
            id: "llm-role",
            heading: "What LLMs do in Skeldir",
            body: (
              <>
                <p>
                  LLMs in Skeldir generate explanations: plain-language
                  summaries of reconciliation outcomes, narrative descriptions
                  of why a discrepancy was classified the way it was, and
                  answers to operator questions that reference an existing
                  deterministic record.
                </p>
                <p>
                  Every LLM-generated explanation is grounded in a specific
                  TrustEnvelope or set of envelopes. The envelope's semantic
                  truth hash and audit trail are passed to the LLM as required
                  context; the LLM cannot produce an explanation that
                  references a value it did not see.
                </p>
              </>
            ),
          },
          {
            id: "llm-does-not-calculate",
            heading: "Why the LLM does not calculate financial truth",
            body: (
              <>
                <p>
                  Authoritative numbers in Skeldir come from the deterministic
                  reconciliation engine, not from an LLM. The engine reads
                  verified evidence, applies policy authority, and produces a
                  deterministic value. The LLM reads that value and explains
                  it.
                </p>
                <p>
                  This boundary is explicit and structural: the LLM does not
                  have write access to the deterministic value field of any
                  TrustEnvelope, and the explanation pipeline rejects any
                  generation that attempts to assert a number not present in
                  the input envelope.
                </p>
                <p>
                  In short: the model explains; it{" "}
                  <strong>does not calculate</strong> the truth.
                </p>
              </>
            ),
          },
          {
            id: "deterministic-grounding",
            heading: "Deterministic grounding",
            body: (
              <p>
                Every public Skeldir explanation cites the deterministic record
                it summarizes. If the operator asks "why is this ad spend
                marked unverified?", the answer must point to the envelope, the
                confidence status, the missing evidence, and the policy
                authority that produced the verdict. If the model cannot find
                deterministic grounding, the answer must say so rather than
                manufacture one.
              </p>
            ),
          },
          {
            id: "explanations-bounded",
            heading: "Bounded explanations",
            body: (
              <p>
                Explanations are bounded by the envelope they reference. The
                model is not allowed to extrapolate to a different time window,
                a different platform, or a different policy authority without
                an explicit operator instruction and an explicit deterministic
                lookup that produces the corresponding envelope. This is what
                prevents drift from explanation to speculation.
              </p>
            ),
          },
          {
            id: "agent-policy",
            heading: "Policy for AI Agents consuming Skeldir",
            body: (
              <p>
                AI Agents that read Skeldir through the integration surface
                must treat the deterministic value and confidence status as
                authoritative and the LLM-generated explanation as advisory.
                Agents are not permitted to act on an explanation that
                contradicts the underlying envelope's deterministic value or
                action authority. This boundary is documented in the
                envelope's action authority field on the{" "}
                <Link className="underline" href="/trust-envelope">
                  TrustEnvelope
                </Link>{" "}
                surface.
              </p>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              LLMs are probabilistic generators. Even when bounded to a
              deterministic record, an explanation can still phrase a fact
              imprecisely or omit a relevant nuance. Operators reviewing
              Skeldir output should always check the deterministic value and
              the confidence status, not the surrounding prose.
            </p>
            <p>
              This boundary applies to Skeldir-produced explanations. Skeldir
              cannot enforce the same boundary on third-party agents that
              consume Skeldir data and re-explain it elsewhere. Those agents
              should follow the same discipline; we strongly recommend they
              do.
            </p>
          </>
        }
      />
    </>
  );
}
