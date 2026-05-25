import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import statusRegistry from "../../../discoverability.status-registry.json";

const ROUTE = "/status";
const PAGE_TITLE = "Status | Skeldir";
const PAGE_DESCRIPTION =
  "Manually verified public operational status for Skeldir operator-facing services — active incidents, scheduled maintenance, and how status updates are communicated.";

const OPERATOR_CONTACT = statusRegistry.operator_contact_channel;

const KEY_FACTS = [
  "No active incidents or service degradations are currently reported for Skeldir's active operator-facing services.",
  "This page is a manually verified public status declaration, not an automated real-time telemetry feed.",
  "Incident notifications and maintenance windows are communicated directly to affected operators through established channels.",
  "Operational inquiries and incident reports should be directed through the operator support channel listed below.",
];

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function StatusPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Status",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Status" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Status"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: statusRegistry.owner,
          status: "operator_approved",
          lastReviewed: statusRegistry.last_reviewed,
          notes:
            "This page reflects the current manually verified operational declaration. It is updated when public operational state changes are confirmed.",
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
            id: "current-status",
            heading: "Current status",
            body: (
              <p>
                Skeldir does not currently report any public service incidents. No service
                degradations are currently reported for active operator-facing services. This page
                will reflect operator-facing status updates as active service environments require
                public status communication.
              </p>
            ),
          },
          {
            id: "active-incidents",
            heading: "Active incidents",
            body: (
              <p>
                <strong>No active incidents are currently reported.</strong>
              </p>
            ),
          },
          {
            id: "scheduled-maintenance",
            heading: "Scheduled maintenance",
            body: (
              <p>
                <strong>No scheduled maintenance is currently listed.</strong>
              </p>
            ),
          },
          {
            id: "communication-policy",
            heading: "How operational events are communicated",
            body: (
              <p>
                Planned maintenance, incident notifications, and status updates are communicated
                directly to affected operators through established engagement channels. This page
                reflects the current manually verified operational declaration and is updated when
                state changes are confirmed — it is not an automated real-time feed.
              </p>
            ),
          },
          {
            id: "scope",
            heading: "Scope of the status surface",
            body: (
              <p>
                Skeldir&apos;s public status surface covers operator-facing reconciliation,
                ingestion, and trust-output availability where those services are active.
                Incident classification, maintenance windows, and detailed availability metrics are
                published through direct operator channels when applicable. See{" "}
                <Link className="underline" href="/methodology">
                  methodology
                </Link>{" "}
                and{" "}
                <Link className="underline" href="/trust-envelope">
                  TrustEnvelope
                </Link>{" "}
                for trust and verification context.
              </p>
            ),
          },
          {
            id: "report-issue",
            heading: "Report an issue",
            body: (
              <p>
                For immediate operational inquiries, incident reports, or maintenance scheduling
                questions, contact{" "}
                <a className="underline" href={`mailto:${OPERATOR_CONTACT}`}>
                  {OPERATOR_CONTACT}
                </a>
                . Security-related reports should use the channel on the{" "}
                <Link className="underline" href="/security">
                  security
                </Link>{" "}
                page. Data rights and privacy questions belong on{" "}
                <Link className="underline" href="/privacy">
                  privacy
                </Link>
                .
              </p>
            ),
          },
        ]}
        relatedProofLinks={[
          { href: "/security", label: "Security — public security posture" },
          { href: "/privacy", label: "Privacy policy — data rights" },
          { href: "/methodology", label: "Methodology — verification boundary" },
          { href: "/trust-envelope", label: "TrustEnvelope — verified outcomes" },
          { href: "/docs", label: "Documentation — concepts and availability" },
        ]}
        limitations={
          <p>
            Status information on this page is a manually verified public declaration. It does not
            include internal monitoring stack details, infrastructure topology, or non-public
            incident history.
          </p>
        }
      />
    </>
  );
}
