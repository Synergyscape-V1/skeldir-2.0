import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import apiRegistry from "../../../discoverability.api-surface-registry.json";
import publicContacts from "../../../discoverability.public-contacts.json";

const ROUTE = "/api";
const PAGE_TITLE = "API | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir programmatic access boundary — governed integration for authorized operators, with verification context preserved and endpoint details provided under agreement.";

const INTEGRATION_EMAIL =
  publicContacts.contacts.find(
    (c) =>
      c.publicly_rendered &&
      c.email === apiRegistry.contact_channel &&
      (c.contact_type === "sales" || c.contact_type === "integration"),
  )?.email ?? apiRegistry.contact_channel;

const KEY_FACTS = [
  "Skeldir exposes verified financial-trust outputs to authorized integrators through governed programmatic access — not through a public endpoint catalog on this page.",
  "Authorized responses are designed to preserve verification context around financial values; deterministic values and verification status are authoritative and explanatory content is advisory.",
  "Concrete endpoint specifications, authentication details, versioning details, and usage boundaries are provided only to authorized integrators under agreement.",
  "This page describes the public access boundary; individual integration agreements supersede it.",
  "Skeldir does not publish public endpoint path catalogs, payload shapes, or field-level response documentation on the public web.",
];

const BLUF = (
  <>
    <p>
      Skeldir supports governed programmatic access to verified financial-trust outputs for
      authorized integrators. This page describes Skeldir&apos;s public API access boundary. It is
      not a public API reference. Concrete endpoint specifications, authentication details,
      versioning details, and usage boundaries are provided only to authorized integrators under
      agreement.
    </p>
    <p>
      Downstream systems must treat deterministic values and verification status as authoritative.
      Any explanatory or narrative content is advisory only.
    </p>
  </>
);

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function ApiProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "API",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "API" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="API"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: apiRegistry.owner,
          status: "operator_approved",
          lastReviewed: apiRegistry.last_reviewed,
          notes:
            "This page describes Skeldir's public programmatic access boundary. It is not a public API reference.",
        }}
        bluf={{
          paragraphs: BLUF,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "what-api-access-represents",
            heading: "What API access represents",
            body: (
              <>
                <p>
                  Programmatic access to Skeldir is a governed integration surface for operators
                  who need machine-readable verified outcomes — not a self-serve public API catalog.
                  Authorized integrators receive scoped access under signed agreement. Responses are
                  designed so callers can see verification context around financial values, not
                  isolated raw numbers divorced from policy and evidence limits.
                </p>
                <p>
                  Concept documentation for verified outcomes lives on{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelope
                  </Link>
                  ,{" "}
                  <Link className="underline" href="/methodology">
                    methodology
                  </Link>
                  , and{" "}
                  <Link className="underline" href="/revenue-verification">
                    revenue verification
                  </Link>
                  surfaces.
                </p>
              </>
            ),
          },
          {
            id: "verification-context",
            heading: "What context accompanies programmatic output",
            body: (
              <p>
                Authorized responses are designed to preserve verification context around
                financial values using precise monetary representation and bounded verification
                status. Callers can understand what a value claims and what limits apply without
                this page publishing response field names, payload shapes, or integrity metadata
                categories.
              </p>
            ),
          },
          {
            id: "agent-consumption",
            heading: "How agents consume Skeldir output responsibly",
            body: (
              <p>
                Agents and automated systems that read Skeldir programmatic output must treat
                deterministic values and verification status as authoritative. They must treat any
                explanatory or narrative content as advisory only. Agents are not permitted to
                trigger operational actions based on content that contradicts the underlying
                verified record. See the{" "}
                <Link className="underline" href="/ai-boundary">
                  AI boundary
                </Link>{" "}
                for how Skeldir separates explanation from computation.
              </p>
            ),
          },
          {
            id: "access-governed",
            heading: "How access is governed",
            body: (
              <p>
                Programmatic access availability is governed by signed integration agreements for
                authorized operators — not by a public self-serve catalog on this page.
                Each agreement defines scoped access level, operational parameters, and
                authentication requirements for that operator. Concrete endpoint specifications,
                versioning details, and usage boundaries are provided directly through the technical
                integration process — not on this public page.
              </p>
            ),
          },
          {
            id: "operational-boundaries",
            heading: "Current operational boundaries",
            body: (
              <>
                <p>
                  This page describes the public programmatic access boundary and consumption
                  policy. It does not enumerate concrete endpoints, authentication
                  details for public reuse, versioning details, or usage boundaries. Those operational
                  parameters are defined in individual integration agreements and provided
                  directly to authorized integrators.
                </p>
                <p>
                  For integration inquiries, contact{" "}
                  <a className="underline" href={`mailto:${INTEGRATION_EMAIL}`}>
                    {INTEGRATION_EMAIL}
                  </a>
                  . Security posture is described on{" "}
                  <Link className="underline" href="/security">
                    security
                  </Link>
                  ; broader documentation concepts on{" "}
                  <Link className="underline" href="/docs">
                    docs
                  </Link>
                  ; privacy commitments on{" "}
                  <Link className="underline" href="/privacy">
                    privacy
                  </Link>
                  .
                </p>
              </>
            ),
          },
        ]}
        limitations={
          <p>
            No SLA, usage ceiling, authentication mechanism, or published callable surface is implied or promised
            by this page. References elsewhere on the site to programmatic access should be read
            through this boundary until Skeldir publishes an approved public API reference.
          </p>
        }
      />
    </>
  );
}
