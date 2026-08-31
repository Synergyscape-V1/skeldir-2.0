import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/security";
const PAGE_TITLE = "Security | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir's public security posture: tenant-scoped financial memory, privacy-preserving data handling, deterministic verification, integer-precision financial treatment, and auditability — with controlled disclosure of detailed security materials.";

const KEY_FACTS = [
  "Skeldir is designed around tenant-scoped financial memory so each operator's reconciliation context is handled separately.",
  "Skeldir's reconciliation substrate is designed to minimize durable personally identifiable information by excluding raw personal identifiers from authoritative verification records where applicable.",
  "Authoritative financial values use integer-precision monetary representation; floating-point currency is not used where deterministic truth is computed.",
  "Authoritative verification outputs are designed to retain audit context, including evidence provenance, policy context, and revision history where applicable.",
  "Security inquiries, vulnerability reports, and procurement documentation requests are handled through direct security engagement.",
];

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function SecurityProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Security",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Security" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Security"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: "Skeldir Security & Engineering",
          status: "technical_disclosure_only",
          lastReviewed: "2026-02-25",
          notes:
            "This page summarizes Skeldir's public security posture. Detailed security documentation, procurement materials, and vulnerability-report handling are available through direct security engagement.",
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
            id: "security-posture-principles",
            heading: "Security posture principles",
            body: (
              <p>
                Skeldir&apos;s security posture rests on tenant-scoped financial memory,
                privacy-preserving data handling, deterministic verification, and auditability.
                These principles govern how commerce and payment evidence is used for revenue
                verification and how outcomes are surfaced to operators and downstream systems.
                See{" "}
                <Link className="underline" href="/methodology">
                  methodology
                </Link>{" "}
                for the deterministic reconciliation boundary.
              </p>
            ),
          },
          {
            id: "tenant-isolation",
            heading: "Tenant isolation",
            body: (
              <p>
                Skeldir is designed around tenant-scoped financial memory so each operator&apos;s
                reconciliation context is handled separately. The public security posture is built
                around preventing cross-tenant exposure and keeping raw tenant data separated from
                aggregate or derived views. Aggregate intelligence, where offered, is intended to
                operate through privacy-safe derived products with explicit source labeling — not
                through raw cross-tenant data sharing.
              </p>
            ),
          },
          {
            id: "pii-policy",
            heading: "Sensitive data handling",
            body: (
              <>
                <p>
                  Skeldir ingests commerce and payment evidence required for revenue verification.
                  Raw personal identifiers are minimized before data becomes part of the durable
                  reconciliation substrate. Skeldir retains only the data necessary to reconcile
                  platform claims against verified commerce and payment evidence.
                </p>
                <p>
                  Privacy rights, data-subject requests, and site-wide privacy commitments are
                  described on the{" "}
                  <Link className="underline" href="/privacy">
                    privacy policy
                  </Link>
                  . This security page does not assert a global &ldquo;zero personal data&rdquo;
                  claim across every Skeldir surface.
                </p>
              </>
            ),
          },
          {
            id: "financial-value-precision",
            heading: "Financial value precision",
            body: (
              <p>
                All monetary values in authoritative verification paths use integer-precision
                representation. Floating-point currency is not used where deterministic financial
                truth is computed or stored. This reduces precision errors in reconciliation,
                attribution views, and trust output. See{" "}
                <Link className="underline" href="/revenue-verification">
                  revenue verification
                </Link>{" "}
                for how verified values are produced.
              </p>
            ),
          },
          {
            id: "auditability",
            heading: "Auditability",
            body: (
              <p>
                Authoritative verification outputs are designed to retain audit context — evidence
                provenance, governing policy, verification status, and revision history where
                applicable. Restatements triggered by delayed evidence are recorded as discrete
                revisions rather than silent overwrites, so operators and reviewers can trace outcomes
                back to source evidence categories. See{" "}
                <Link className="underline" href="/trust-envelope">
                  TrustEnvelope
                </Link>{" "}
                for how verified outcomes are packaged for review.
              </p>
            ),
          },
          {
            id: "security-inquiries",
            heading: "Security inquiries and vulnerability reporting",
            body: (
              <p>
                Detailed security documentation, procurement security materials, and vulnerability
                reports are handled through direct security engagement. Contact{" "}
                <a className="underline" href="mailto:security@skeldir.com">
                  security@skeldir.com
                </a>{" "}
                with specific questions or documentation requests. Skeldir reviews good-faith
                vulnerability reports through this channel; a public bug-bounty program is not
                advertised on this page.
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/methodology", label: "Methodology — deterministic reconciliation boundary" },
          {
            href: "/revenue-verification",
            label: "Revenue verification — authoritative financial values",
          },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcome container" },
          { href: "/ai-boundary", label: "AI / LLM boundary — explanation vs computation" },
          { href: "/privacy", label: "Privacy policy — data rights and site-wide commitments" },
          { href: "/api", label: "API — integration surface" },
          { href: "/docs", label: "Documentation — concepts and availability" },
        ]}
        limitations={
          <>
            <p>
              <strong>Current limitations.</strong> This page describes Skeldir&apos;s public
              security posture, not detailed technical architecture. Penetration-test results,
              certification evidence, and procurement-only materials are provided under controlled
              security review — not through public disclosure that could weaken operational security.
            </p>
            <p>
              Public integration behavior and API availability are documented on{" "}
              <Link className="underline" href="/api">
                API
              </Link>{" "}
              and{" "}
              <Link className="underline" href="/docs">
                documentation
              </Link>{" "}
              where applicable.
            </p>
          </>
        }
      />
    </>
  );
}
