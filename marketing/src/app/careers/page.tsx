import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";
import careersRegistry from "../../../discoverability.careers-registry.json";
import publicContacts from "../../../discoverability.public-contacts.json";

const ROUTE = "/careers";
const PAGE_TITLE = "Careers | Skeldir";
const PAGE_DESCRIPTION =
  "Skeldir careers and talent inquiry — hiring philosophy, what we value, and how to express interest when aligned with our technical standards.";

const TALENT_EMAIL =
  publicContacts.contacts.find(
    (c) =>
      c.publicly_rendered &&
      c.email === careersRegistry.talent_contact_channel &&
      c.contact_type === "careers",
  )?.email ?? careersRegistry.talent_contact_channel;

const KEY_FACTS = [
  "Skeldir evaluates candidates on demonstrated systems thinking and adversarial validation rather than credentials or conventional hiring metrics alone.",
  "We seek people who have built or maintained systems where technical correctness is falsifiable — including integrity-preserving systems, verifiable records, and tenant-scoped designs.",
  "Privacy is treated as an architectural constraint, not a compliance checklist.",
  "Our evaluation process is transparent and direct: structured technical assessment followed by conversation with the team members you would work alongside.",
  "We review relevant direct inquiries when they clearly align with Skeldir's current needs and technical standards.",
];

const BLUF = (
  <>
    <p>
      This page describes the capabilities, mindset, and engineering discipline Skeldir values. We
      are a small, technically rigorous team building deterministic financial trust infrastructure.
      We welcome highly relevant inquiries from engineers and operators who reason precisely about
      technical correctness, privacy, and system boundaries — even when no public roles are listed.
    </p>
    <p>
      This page is not a job board. There may be no public open roles at this time. Qualified inbound
      inquiries may be reviewed when aligned with Skeldir&apos;s needs.
    </p>
  </>
);

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function CareersPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: "Careers",
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Careers" }),
        ]}
      />
      <TrustProofPage
        presentation="public"
        headline="Careers"
        lede={PAGE_DESCRIPTION}
        lastUpdated="February 2026"
        meta={{
          owner: careersRegistry.owner,
          status: "operator_approved",
          lastReviewed: careersRegistry.last_reviewed,
          notes:
            "This page describes hiring philosophy and talent-inquiry posture. It is not a public job board.",
        }}
        bluf={{
          paragraphs: BLUF,
          fiveFactsHeading: "Key facts",
          fiveFacts: KEY_FACTS,
        }}
        sections={[
          {
            id: "what-we-value",
            heading: "What We Value",
            body: (
              <>
                <p>
                  We value engineers and operators who are comfortable with systems where ambiguity
                  is unacceptable. Relevant experience includes deterministic financial
                  reconciliation, integrity-preserving systems or verifiable records, tenant-scoped
                  systems and privacy-preserving architecture, canonical data handling and
                  reproducible system behavior, or testable engineering workflows with falsifiable
                  quality gates.
                </p>
                <p>
                  Experience with attribution systems, commerce platforms, payment processors, or
                  trust infrastructure is relevant but not required. The ability to reason
                  deterministically about financial truth, to identify edge cases in correctness, and
                  to treat privacy as a load-bearing architectural constraint is required.
                </p>
                <p>
                  We value intellectual honesty about what a system can and cannot prove, precision
                  in communication, and the discipline to reject convenient approximations when
                  exactness is possible. Public proof surfaces such as{" "}
                  <Link className="underline" href="/methodology">
                    methodology
                  </Link>{" "}
                  and{" "}
                  <Link className="underline" href="/security">
                    security
                  </Link>{" "}
                  describe how Skeldir approaches verification and data handling.
                </p>
              </>
            ),
          },
          {
            id: "how-we-hire",
            heading: "How We Hire",
            body: (
              <p>
                We add team members deliberately through direct referral and inbound inquiry. We do
                not operate high-volume automated screening pipelines. This respects both candidate
                time and team bandwidth. When we engage a candidate, evaluation centers on structured
                technical assessment of systems design and reasoning, followed by direct conversation
                with the engineers and operators who would work alongside them. There are no abstract
                panel interviews or take-home exercises evaluated by non-technical recruiters.
              </p>
            ),
          },
          {
            id: "how-to-express-interest",
            heading: "How to Express Interest",
            body: (
              <p>
                If you have demonstrated work at the intersection of distributed systems, financial
                correctness, and privacy engineering, you may signal interest through the contact
                below. We welcome highly relevant inquiries even when no public roles are listed on
                this page.
              </p>
            ),
          },
          {
            id: "scope-trust-boundary",
            heading: "Scope and Trust Boundary",
            body: (
              <p>
                This page describes our team philosophy and the capabilities we seek. It is not an
                exhaustive list of open roles and is not a job board. There may be no public open
                roles at this time. Specific role definitions and team structure are discussed
                directly with qualified candidates.
              </p>
            ),
          },
          {
            id: "contact",
            heading: "Contact",
            body: (
              <p>
                For talent inquiries, contact{" "}
                <a className="underline" href={`mailto:${TALENT_EMAIL}`}>
                  {TALENT_EMAIL}
                </a>
                .
              </p>
            ),
          },
        ]}
        limitations={
          <p>
            Skeldir does not publish internal implementation requirements, compensation bands, or
            benefits packages on this page unless explicitly approved elsewhere.
          </p>
        }
      />
    </>
  );
}
