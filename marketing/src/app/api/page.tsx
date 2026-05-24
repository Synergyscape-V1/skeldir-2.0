import type { Metadata } from "next";
import Link from "next/link";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/api";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "API — Concepts and availability";
const PAGE_DESCRIPTION =
  "Skeldir's public API surface as a concepts and availability page. This page describes what a Skeldir-callable contract would look like in terms of TrustEnvelopes and policy authority. It does not promise a live, generally available external endpoint today.";

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
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "API" }),
        ]}
      />
      <TrustProofPage
        headline="API"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page exists so the marketing site never references a 'Trust API' without a static public concept page to back it. It does not assert a generally available external endpoint, version, or SLA.",
        }}
        sections={[
          {
            id: "concepts",
            heading: "API concepts (what calling Skeldir looks like)",
            body: (
              <>
                <p>
                  A future Skeldir API surface would expose deterministic
                  values to downstream systems as{" "}
                  <Link className="underline" href="/trust-envelope">
                    TrustEnvelopes
                  </Link>
                  . Every response would carry the deterministic value, the
                  confidence status, the policy authority, the provenance
                  chain reference, and the artifact and semantic truth
                  hashes — never just a raw number.
                </p>
                <p>
                  This is the right shape for a machine-callable contract on
                  top of deterministic reconciliation: callers see not just
                  the number, but the verification state and the policy
                  basis for the number. AI Agents that consume this surface
                  must respect the envelope's action authority.
                </p>
              </>
            ),
          },
          {
            id: "availability",
            heading: "Availability today",
            body: (
              <>
                <p>
                  Skeldir does not currently expose a public, generally
                  available external API endpoint. Operators with signed
                  integration agreements may receive scoped programmatic
                  access; that access is governed by the agreement, not by
                  this page.
                </p>
                <p>
                  This page exists so the rest of the marketing site never
                  references a "Trust API" without a public proof page that
                  states the truthful availability state. If a future
                  release introduces a generally available external API,
                  this page will be updated and the
                  availability section will be replaced with a concrete
                  contract, versioning policy, and rate-limit description.
                </p>
              </>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              No SLA, no rate-limit, no authentication scheme, and no
              endpoint URL is implied or promised by this page. References
              elsewhere on the site to "the API" should be read as the
              concept described here until this page advertises a concrete
              contract.
            </p>
            <p>
              Operators on signed integration agreements receive the actual
              integration contract from their Skeldir technical contact.
              That contract supersedes anything on this page.
            </p>
          </>
        }
      />
    </>
  );
}
