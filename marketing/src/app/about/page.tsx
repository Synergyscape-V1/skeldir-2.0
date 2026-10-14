import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import aboutRegistry from "../../../discoverability.about-surface-registry.json";

const ROUTE = "/about";
const PAGE_TITLE = "About Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir is financial-trust infrastructure for deterministic revenue verification — helping operators and finance teams distinguish platform-reported claims from revenue supported by independent commerce and payment evidence.";

const KEY_FACTS = [
  "Skeldir is financial-trust infrastructure for deterministic revenue verification.",
  "Skeldir is not an analytics dashboard. Skeldir is not an AI attribution assistant.",
  "Skeldir compares platform-reported revenue claims with operator-authorized independent commerce and payment evidence to produce verified revenue outcomes.",
  "Structured trust outputs are designed for human and system review with clear verification status, evidence context, and audit-ready trust context — bounded by public proof pages.",
  "Skeldir is designed around tenant-scoped financial memory, privacy-preserving design, and a strict AI explanation boundary.",
  "Skeldir serves digital operators, finance and revenue operations teams, and downstream automated systems that need verified revenue context.",
];

const BLUF = (
  <>
    <p>
      Skeldir is financial-trust infrastructure for deterministic revenue verification. It helps
      digital operators and finance teams distinguish platform-reported revenue claims from revenue
      supported by independent commerce and payment evidence.
    </p>
    <p>
      Skeldir&apos;s value is not better attribution prose. Operators, finance teams, and automated
      systems can consume verified revenue context without treating platform-reported numbers,
      model-generated estimates, or privacy-invasive identity graphs as authoritative financial
      truth.
    </p>
  </>
);

export const metadata: Metadata = {
  title: `${PAGE_TITLE} | Skeldir`,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function AboutPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "About Skeldir",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "About" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="About Skeldir"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: aboutRegistry.owner,
          status: "operator_approved",
          lastReviewed: aboutRegistry.last_reviewed,
          notes:
            "Public entity-definition page. Detailed proof boundaries live on linked methodology, security, privacy, and API surfaces.",
        }}
        bluf={{
          paragraphs: BLUF,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "what-skeldir-does",
            heading: "What Skeldir Does",
            body: (
              <>
                <p>
                  Skeldir verifies advertising platform revenue claims against independent commerce
                  and payment evidence through precise financial reconciliation. Platform-reported
                  revenue is treated as a claim to evaluate — not as ground truth. When evidence
                  supports a claim, the outcome is verified; when it does not, discrepancies are
                  classified by type rather than silently averaged.
                </p>
                <p>
                  Outputs are structured trust outputs designed for human and system review —
                  bundling deterministic values with verification status, evidence context, and
                  auditability within governed limits. See{" "}
                  <Link className="underline" href="/revenue-verification">
                    revenue verification
                  </Link>{" "}
                  and{" "}
                  <Link className="underline" href="/methodology">
                    methodology
                  </Link>
                  .
                </p>
              </>
            ),
          },
          {
            id: "principles",
            heading: "Principles That Govern Skeldir",
            body: (
              <ul className="list-disc pl-6 space-y-3 text-slate-700">
                <li>
                  <strong>Deterministic financial truth is authoritative.</strong> Authoritative
                  values come from deterministic reconciliation over verified evidence. Probabilistic
                  models and heuristic inference may inform understanding but do not override
                  deterministic financial outcomes.
                </li>
                <li>
                  <strong>Tenant-scoped financial memory.</strong> Skeldir is designed around
                  tenant-scoped records and privacy-preserving data boundaries. Isolation posture is
                  described on{" "}
                  <Link className="underline" href="/security">
                    security
                  </Link>
                  .
                </li>
                <li>
                  <strong>Privacy-preserving by design.</strong> Skeldir is designed to minimize
                  durable personal identifiers in the reconciliation substrate. Public privacy
                  posture is on{" "}
                  <Link className="underline" href="/privacy">
                    privacy
                  </Link>
                  .
                </li>
                <li>
                  <strong>Precise monetary representation.</strong> Authoritative financial paths use
                  precise monetary representation suitable for audit and system consumption — not
                  floating-point guesses where determinism matters.
                </li>
                <li>
                  <strong>Explanation and computation are separate.</strong> Deterministic values and
                  verification status are authoritative; explanatory content is advisory. See the{" "}
                  <Link className="underline" href="/ai-boundary">
                    AI boundary
                  </Link>
                  .
                </li>
              </ul>
            ),
          },
          {
            id: "who-skeldir-serves",
            heading: "Who Skeldir Serves",
            body: (
              <ul className="list-disc pl-6 space-y-2 text-slate-700">
                <li>
                  <strong>Finance and revenue operations teams</strong> who need auditable,
                  deterministic records for reporting and reconciliation.
                </li>
                <li>
                  <strong>Marketing and growth operators</strong> who need to know which revenue
                  claims are verified and which are classified discrepancies — see{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>
                  .
                </li>
                <li>
                  <strong>Downstream automated systems and agents</strong> that consume structured
                  trust outputs under policy limits — see{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>{" "}
                  and{" "}
                  <Link className="underline" href="/api">
                    API access boundary
                  </Link>
                  .
                </li>
              </ul>
            ),
          },
          {
            id: "how-skeldir-differs",
            heading: "How Skeldir Differs From Analytics and Attribution Platforms",
            body: (
              <>
                <p>
                  Skeldir is not an analytics dashboard with a programmatic wrapper. It is not a
                  generic attribution surface or a probabilistic attribution oracle detached from
                  verified evidence.
                </p>
                <ul className="list-disc pl-6 space-y-2 text-slate-700 mt-4">
                  <li>
                    <strong>Evidence-first, not platform-first.</strong> Platform-reported revenue is
                    a claim; independent commerce and payment evidence ground verification.
                  </li>
                  <li>
                    <strong>Deterministic, not inferred.</strong> Authoritative numbers are computed
                    deterministically from verified evidence — not generated by statistical models or
                    large language models.
                  </li>
                  <li>
                    <strong>Structured trust outputs, not narrative summaries.</strong> Primary
                    outputs preserve verification status and evidence context for systems and
                    reviewers; explanations layer on top without substituting underlying truth.
                  </li>
                </ul>
                <p className="mt-4">
                  Attribution concepts are documented on{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>
                  .
                </p>
              </>
            ),
          },
          {
            id: "engage",
            heading: "How Organizations Engage With Skeldir",
            body: (
              <p>
                Organizations interested in Skeldir&apos;s deterministic revenue-verification
                infrastructure should contact the team through{" "}
                <Link className="underline" href="/book-demo">
                  book a demo
                </Link>
                . Integration availability, scoped programmatic access, and operational parameters
                are governed by individual agreements. Operators establish verification scope and
                review boundaries through governed engagement — detailed in{" "}
                <Link className="underline" href="/docs">
                  docs
                </Link>
                .
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology" },
          { href: "/revenue-verification", label: "Revenue verification" },
          { href: "/trust-envelope", label: "TrustEnvelope" },
          { href: "/security", label: "Security" },
          { href: "/privacy", label: "Privacy" },
        ]}
        limitations={
          <p>
            This page defines Skeldir&apos;s public category and trust positioning. It does not
            describe reconciliation mechanics, enforcement architecture details, or field-level
            trust-output contracts. Public claims are bounded by linked proof surfaces including
            methodology, security, privacy, API access boundary, and TrustEnvelope concepts.
          </p>
        }
      />
    </>
  );
}
