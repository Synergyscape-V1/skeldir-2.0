import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/docs";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "Documentation — Concepts and availability";
const PAGE_DESCRIPTION =
  "Skeldir's public documentation surface. This page is a concepts and availability index: it lists the concepts a buyer or integrator should learn before requesting access and states what is publicly documented today vs. what is delivered under a signed integration agreement.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: { title: PAGE_TITLE, description: PAGE_DESCRIPTION },
};

export default function DocsProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
            dateModified: LAST_REVIEWED,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "Documentation" }),
        ]}
      />
      <TrustProofPage
        headline="Documentation"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This is the documentation concepts and availability index. It does not enumerate every endpoint or integration surface; concrete integration documentation is delivered to operators under a signed agreement.",
        }}
        sections={[
          {
            id: "concepts",
            heading: "Concepts to learn before integrating",
            body: (
              <>
                <p>
                  Before evaluating Skeldir, a buyer or integrator should be
                  comfortable with these concepts. Each is documented on its
                  own public proof page:
                </p>
                <ul className="list-disc pl-6 space-y-2">
                  <li>
                    <Link className="underline" href="/trust-envelope">
                      TrustEnvelope
                    </Link>{" "}
                    — the deterministic truth contract Skeldir produces.
                  </li>
                  <li>
                    <Link className="underline" href="/methodology">
                      Methodology
                    </Link>{" "}
                    — how Skeldir reconciles platform claims against
                    commerce and payment evidence.
                  </li>
                  <li>
                    <Link className="underline" href="/revenue-verification">
                      Revenue verification
                    </Link>{" "}
                    — how commerce evidence supports or rejects platform
                    claims.
                  </li>
                  <li>
                    <Link className="underline" href="/attribution-methodology">
                      Attribution methodology
                    </Link>{" "}
                    — what attribution models can and cannot answer.
                  </li>
                  <li>
                    <Link className="underline" href="/discrepancy-taxonomy">
                      Discrepancy taxonomy
                    </Link>{" "}
                    — how mismatches are classified.
                  </li>
                  <li>
                    <Link className="underline" href="/ai-boundary">
                      AI boundary
                    </Link>{" "}
                    — where LLM-generated explanation is and is not allowed.
                  </li>
                  <li>
                    <Link className="underline" href="/security">
                      Security
                    </Link>{" "}
                    — reserved URL for security disclosures (placeholder until
                    published).
                  </li>
                </ul>
              </>
            ),
          },
          {
            id: "availability",
            heading: "Availability of integration documentation",
            body: (
              <>
                <p>
                  The proof pages above describe Skeldir's product concepts
                  and are public, static, and indexable. They are the
                  authoritative starting point for any evaluation.
                </p>
                <p>
                  Step-by-step integration documentation (connector setup,
                  schema, webhook contracts, error semantics, version
                  pinning) is currently delivered to operators under a
                  signed integration agreement rather than published
                  publicly. To request a copy or a guided walkthrough,
                  contact <a className="underline" href="mailto:sales@skeldir.com">sales@skeldir.com</a>.
                </p>
                <p>
                  The availability boundary will move as Skeldir publishes
                  more material. When integration documentation becomes
                  public, this page will be updated and
                  the index above will gain direct links.
                </p>
              </>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              This is a documentation concepts and availability index, not a
              full developer portal. It does not list every endpoint, every
              integration, or every error code. Those are delivered as part
              of a signed integration agreement.
            </p>
            <p>
              Public concepts are maintained on each proof page. Integration material delivered under
              agreement is versioned separately.
            </p>
          </>
        }
      />
    </>
  );
}
