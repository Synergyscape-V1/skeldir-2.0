import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import publicContacts from "../../../discoverability.public-contacts.json";
import pressRegistry from "../../../discoverability.press-registry.json";

const ROUTE = "/press";
const PAGE_TITLE = "Press | Skeldir";
const PAGE_DESCRIPTION =
  "Press and media information for Skeldir — evidence-first public proof surfaces, inquiry routing, and boundaries for factual engagement.";

const APPROVED_EMAILS = publicContacts.contacts
  .filter((c) => c.publicly_rendered)
  .reduce(
    (acc, c) => {
      acc[c.contact_type] = c.email;
      return acc;
    },
    {} as Record<string, string>,
  );

const KEY_FACTS = [
  "Skeldir's authoritative public record consists of published technical disclosure and proof pages — not marketing briefs or forward-looking roadmaps.",
  "Public claims are structured, scope-bounded, and traceable to published methodology pages with explicit limitations.",
  "Skeldir does not distribute press kits, revenue projections, competitive positioning decks, or speculative product materials for media consumption.",
  "Press inquiries are answered against published proof surfaces rather than ad hoc or unpublished commentary.",
  "Security, commercial, and operational inquiries are routed through separate dedicated channels.",
];

const BLUF = (
  <>
    <p>
      Skeldir is deterministic revenue-verification and financial-trust infrastructure. This page
      directs journalists and industry analysts to Skeldir&apos;s public proof surfaces and sets
      the boundary for factual press engagement. Skeldir publishes evidence-first technical
      documentation; public claims should cite those surfaces rather than informal commentary.
    </p>
    <p>
      Skeldir does not currently distribute public press kits, roadmap briefs, revenue projections,
      or speculative product materials. Journalists should use published methodology and proof pages
      as the public factual record.
    </p>
  </>
);

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function PressPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Press",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Press" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Press"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: pressRegistry.owner,
          status: "operator_approved",
          lastReviewed: pressRegistry.last_reviewed,
          notes:
            "This page routes media inquiries to published proof surfaces and approved contact channels. It does not replace contractual terms.",
        }}
        bluf={{
          paragraphs: BLUF,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "technical-disclosures",
            heading: "Technical disclosures as primary source",
            body: (
              <>
                <p>
                  Skeldir&apos;s public methodology surfaces are the authoritative record for
                  external coverage. They document how deterministic reconciliation produces
                  verified revenue truth, how attribution models answer bounded questions under
                  documented assumptions, how discrepancies between platform claims and commerce
                  evidence are classified, and how the AI boundary keeps large language models from
                  computing financial truth.
                </p>
                <p>
                  Each proof page is an indexable public surface with explicit limitations.
                  Journalists referencing Skeldir should cite{" "}
                  <Link className="underline" href="/methodology">
                    methodology
                  </Link>
                  ,{" "}
                  <Link className="underline" href="/revenue-verification">
                    revenue verification
                  </Link>
                  ,{" "}
                  <Link className="underline" href="/attribution-methodology">
                    attribution methodology
                  </Link>
                  ,{" "}
                  <Link className="underline" href="/discrepancy-taxonomy">
                    discrepancy taxonomy
                  </Link>
                  ,{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope concept documentation
                  </Link>
                  , and the{" "}
                  <Link className="underline" href="/ai-boundary">
                    AI boundary
                  </Link>{" "}
                  as primary sources for claims about system behavior or trust architecture.
                </p>
              </>
            ),
          },
          {
            id: "inquiry-routing",
            heading: "Inquiry routing and verification",
            body: (
              <p>
                Press inquiries are handled through the dedicated press contact below. Responses
                are grounded in published technical disclosures and verified against public proof
                pages. Skeldir does not provide commentary on unpublished capabilities, unannounced
                integrations, speculative future states, or roadmap timing. Factual verification
                requests about published methodology are answered promptly; requests beyond the
                published disclosure boundary are declined rather than answered provisionally.
              </p>
            ),
          },
          {
            id: "public-information-boundary",
            heading: "Scope of public information",
            body: (
              <p>
                Skeldir publishes technical disclosures at the outcome boundary only. Skeldir does
                not publicly disclose internal architecture, implementation modules, phase identifiers,
                schema details, or pipeline specifics. This boundary protects competitive intellectual
                property while keeping public claims externally reviewable against published proof
                pages. Operational posture is described on{" "}
                <Link className="underline" href="/status">
                  status
                </Link>
                ; security posture on{" "}
                <Link className="underline" href="/security">
                  security
                </Link>
                .
              </p>
            ),
          },
          {
            id: "contact",
            heading: "Contact",
            body: (
              <>
                <p>
                  For press inquiries, contact{" "}
                  <a className="underline" href={`mailto:${APPROVED_EMAILS.press}`}>
                    {APPROVED_EMAILS.press}
                  </a>
                  .
                </p>
                <p>
                  For security-related questions, contact{" "}
                  <a
                    className="underline"
                    href={`mailto:${APPROVED_EMAILS.security_engineering}`}
                  >
                    {APPROVED_EMAILS.security_engineering}
                  </a>{" "}
                  or review the{" "}
                  <Link className="underline" href="/security">
                    security
                  </Link>{" "}
                  page ({APPROVED_EMAILS.security} for vulnerability reporting).
                </p>
                <p>
                  For operational or procurement questions, contact{" "}
                  <a className="underline" href={`mailto:${APPROVED_EMAILS.sales}`}>
                    {APPROVED_EMAILS.sales}
                  </a>{" "}
                  and see{" "}
                  <Link className="underline" href="/status">
                    status
                  </Link>{" "}
                  for public operational declarations.
                </p>
              </>
            ),
          },
        ]}
        limitations={
          <p>
            This page explains press boundaries only. It is not a press kit, brand asset library, or
            executive briefing document.
          </p>
        }
      />
    </>
  );
}
