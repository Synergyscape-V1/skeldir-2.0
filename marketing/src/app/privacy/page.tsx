import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import privacyRegistry from "../../../discoverability.privacy-surface-registry.json";
import publicContacts from "../../../discoverability.public-contacts.json";

const ROUTE = "/privacy";
const PAGE_TITLE = "Privacy | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir public privacy posture — data minimization, tenant-scoped financial records, and how privacy inquiries are handled through approved channels.";

const PRIVACY_EMAIL =
  publicContacts.contacts.find(
    (c) =>
      c.publicly_rendered &&
      c.email === "engineering@skeldir.com" &&
      (c.contact_type === "privacy" || c.contact_type === "security_engineering"),
  )?.email ?? "engineering@skeldir.com";

const SECURITY_EMAIL =
  publicContacts.contacts.find(
    (c) => c.publicly_rendered && c.email === "security@skeldir.com" && c.contact_type === "security",
  )?.email ?? "security@skeldir.com";

const KEY_FACTS = [
  "Skeldir processes commerce, payment, and advertising-platform data for revenue verification — not as a general data broker or ad-tech profile store.",
  "Skeldir is designed around data minimization and tenant-scoped financial records rather than broad personal-data collection.",
  "Advertising-platform data is not treated as the authority for verified revenue; reconciliation uses operator-authorized integration context.",
  "This page is a public privacy posture summary, not a complete legal privacy policy.",
  "Formal privacy terms, data-processing terms, and operator-specific documentation are provided through approved legal and operator channels.",
];

const BLUF = (
  <>
    <p>
      This page summarizes Skeldir&apos;s public privacy posture for operators, auditors, and
      integration partners. It describes how Skeldir approaches data handling for revenue
      verification without exposing internal privacy-control architecture. This page is a public
      privacy posture summary, not a complete legal privacy policy.
    </p>
    <p>
      Formal privacy terms, data-processing terms, retention commitments, subprocessors, transfer
      mechanisms, and operator-specific documentation are handled through approved legal and
      operator channels — not asserted on this public summary.
    </p>
  </>
);

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  robots: { index: false, follow: true, googleBot: { index: false, follow: true } },
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function PrivacyPosturePage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Privacy",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Privacy" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Privacy"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: privacyRegistry.owner,
          status: "operator_approved",
          lastReviewed: privacyRegistry.last_reviewed,
          notes:
            "This page summarizes Skeldir's public privacy posture. It is not a complete legal privacy policy.",
        }}
        bluf={{
          paragraphs: BLUF,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "privacy-posture",
            heading: "Privacy posture",
            body: (
              <p>
                Skeldir is built for privacy-preserving financial trust: limited use of
                commerce, payment, and advertising-platform data for reconciliation purposes,
                with operator-controlled integration context. Public disclosure focuses on
                posture and boundaries — not internal enforcement mechanics.
              </p>
            ),
          },
          {
            id: "data-processed",
            heading: "Data Skeldir processes",
            body: (
              <p>
                Skeldir receives operator-authorized data through controlled integration paths
                to produce verified financial-trust outputs. Evidence for verification is drawn
                from commerce and payment sources appropriate to reconciliation — not from
                treating the advertising platform under evaluation as the authority for verified
                revenue. See{" "}
                <Link className="underline" href="/revenue-verification">
                  revenue verification
                </Link>{" "}
                and{" "}
                <Link className="underline" href="/methodology">
                  methodology
                </Link>{" "}
                for how verified outcomes are framed publicly.
              </p>
            ),
          },
          {
            id: "data-minimization",
            heading: "Data minimization",
            body: (
              <p>
                Skeldir is designed to minimize durable personal identifiers in the reconciliation
                substrate. The reconciliation substrate is designed to avoid retaining raw personal
                identifiers where they are not required for verified financial records. Skeldir
                limits public disclosure of privacy architecture; internal control design is not
                published on this page.
              </p>
            ),
          },
          {
            id: "tenant-scoped",
            heading: "Tenant-scoped data handling",
            body: (
              <p>
                Verified transactional records are scoped to the tenant that owns them through
                tenant-scoped access controls. Cross-tenant intelligence, where produced, uses
                privacy-preserving aggregate controls — not exposure of tenant identifiers or raw
                commerce identifiers on this public surface. Security posture is described on{" "}
                <Link className="underline" href="/security">
                  security
                </Link>
                ; verified outcome concepts on{" "}
                <Link className="underline" href="/trust-envelope">
                  TrustEnvelope
                </Link>
                .
              </p>
            ),
          },
          {
            id: "aggregate-boundary",
            heading: "Aggregate and benchmark privacy boundary",
            body: (
              <p>
                Benchmark and aggregate products are subject to privacy-preserving aggregate
                controls so public or cross-tenant outputs do not re-identify operators. Skeldir
                does not publish aggregate construction details, dominance rules, or
                corpus-handling implementation on this page.
              </p>
            ),
          },
          {
            id: "legal-boundary",
            heading: "Legal and operator documentation boundary",
            body: (
              <p>
                This page summarizes Skeldir&apos;s public privacy posture. Operator-specific
                privacy, data-processing, retention, subprocessor, and transfer documentation is
                handled through approved legal and operator channels. For privacy rights
                disclosures, see{" "}
                <Link className="underline" href="/gdpr">
                  privacy rights &amp; GDPR
                </Link>
                . Automated consumption boundaries are described on{" "}
                <Link className="underline" href="/ai-boundary">
                  AI boundary
                </Link>
                .
              </p>
            ),
          },
          {
            id: "contact",
            heading: "Contact",
            body: (
              <p>
                For privacy-related inquiries, contact{" "}
                <a className="underline" href={`mailto:${PRIVACY_EMAIL}`}>
                  {PRIVACY_EMAIL}
                </a>
                . For security-related questions, contact{" "}
                <a className="underline" href={`mailto:${SECURITY_EMAIL}`}>
                  {SECURITY_EMAIL}
                </a>{" "}
                or review the{" "}
                <Link className="underline" href="/security">
                  security
                </Link>{" "}
                page.
              </p>
            ),
          },
        ]}
        limitations={
          <p>
            This public privacy posture summary does not assert compliance certifications, data
            subject rights procedures, retention schedules, subprocessor lists, or transfer
            mechanisms that have not been approved for publication. Do not treat this page as a
            substitute for operator-specific legal documentation.
          </p>
        }
      />
    </>
  );
}
