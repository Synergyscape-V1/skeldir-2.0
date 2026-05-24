import type { Metadata } from "next";
import { JsonLd } from "@/components/schema/JsonLd";
import { TrustProofPage } from "@/components/discoverability/TrustProofPage";
import { canonicalUrl } from "@/lib/crawlUrls";
import {
  trustProofBreadcrumbJsonLd,
  trustProofWebPageJsonLd,
} from "@/lib/schema/trustProof";

const ROUTE = "/trust-envelope";
const LAST_REVIEWED = "2026-05-23";
const PAGE_TITLE = "TrustEnvelope — Skeldir's deterministic truth contract";
const PAGE_DESCRIPTION =
  "A TrustEnvelope is the static contract Skeldir uses to bundle every deterministic value with its provenance, hashes, policy authority, confidence status, and audit trail so downstream systems can verify what is and is not guaranteed.";

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: { canonical: canonicalUrl(ROUTE) },
  openGraph: {
    title: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
  },
};

export default function TrustEnvelopeProofPage() {
  return (
    <>
      <JsonLd
        data={[
          trustProofWebPageJsonLd(ROUTE, {
            name: PAGE_TITLE,
            description: PAGE_DESCRIPTION,
          }),
          trustProofBreadcrumbJsonLd(ROUTE, { label: "TrustEnvelope" }),
        ]}
      />
      <TrustProofPage
        headline="TrustEnvelope: the deterministic truth contract"
        lede={PAGE_DESCRIPTION}
        meta={{
          owner: "Skeldir Product Engineering",
          status: "technical_disclosure_only",
          lastReviewed: LAST_REVIEWED,
          notes:
            "This page describes the TrustEnvelope concept and its required fields. It does not promise a live external API contract; concrete API availability is documented separately on /api and the integration documentation surface on /docs.",
        }}
        sections={[
          {
            id: "what-it-is",
            heading: "What a TrustEnvelope is",
            body: (
              <>
                <p>
                  A TrustEnvelope is a static, auditable bundle that wraps every
                  number Skeldir surfaces. It exists to make sure no downstream
                  system, dashboard, or AI agent can read a deterministic value
                  without simultaneously seeing where that value came from, what
                  policy stood behind it, what its confidence status is, and
                  whether any fallback was applied.
                </p>
                <p>
                  A TrustEnvelope is never an opinion. It is the smallest
                  reproducible record that lets an external reviewer recompute
                  the value from raw evidence and confirm Skeldir's claim.
                </p>
              </>
            ),
          },
          {
            id: "deterministic-values",
            heading: "Deterministic values",
            body: (
              <>
                <p>
                  Every TrustEnvelope contains one or more{" "}
                  <strong>deterministic values</strong>. These are integer-cents
                  financial quantities (revenue, refund, fee, payout, net
                  recognized amount) computed by Skeldir's deterministic
                  reconciliation engine, not by an LLM, model, or heuristic.
                </p>
                <p>
                  Deterministic values are repeatable: given the same evidence
                  inputs and the same policy authority, Skeldir returns the same
                  number byte-for-byte.
                </p>
              </>
            ),
          },
          {
            id: "provenance-chain",
            heading: "Provenance chain",
            body: (
              <>
                <p>
                  The <strong>provenance chain</strong> records the ordered set
                  of evidence records that produced the deterministic value:
                  Stripe charges, Shopify orders, platform reports, currency
                  rate snapshots, refund records, and any policy decisions
                  applied along the way.
                </p>
                <p>
                  The provenance chain is the spine of the audit trail. Every
                  link is content-addressable and can be replayed.
                </p>
              </>
            ),
          },
          {
            id: "semantic-truth-hash",
            heading: "Semantic truth hash",
            body: (
              <p>
                The <strong>semantic truth hash</strong> is a stable hash of the
                envelope's normalized claim — the deterministic value plus the
                resolved policy authority plus the evidence reference set. Two
                TrustEnvelopes with the same semantic truth hash assert the same
                financial truth even if their raw bytes differ. This is what
                makes deduplication and cross-system equality checks safe.
              </p>
            ),
          },
          {
            id: "artifact-hash",
            heading: "Artifact hash",
            body: (
              <p>
                The <strong>artifact hash</strong> is a byte-level hash of the
                serialized envelope itself. It detects tampering, transport
                corruption, and serialization drift. Where the semantic truth
                hash answers "is this the same claim?", the artifact hash
                answers "is this the same record?".
              </p>
            ),
          },
          {
            id: "confidence-status",
            heading: "Confidence status",
            body: (
              <>
                <p>
                  Every envelope carries a <strong>confidence status</strong>{" "}
                  drawn from a small enumerated set: <code>verified</code>,{" "}
                  <code>partially_verified</code>, <code>unverified</code>, and{" "}
                  <code>blocked</code>. <em>Verified</em> means every required
                  evidence input matched and reconciled. <em>Partially
                  verified</em> means some inputs are missing or delayed and the
                  envelope explains which. <em>Unverified</em> and{" "}
                  <em>blocked</em> mean Skeldir refuses to assert deterministic
                  truth and explains why.
                </p>
                <p>
                  Confidence status is a status enum, not a probability score.
                  Probability ranges live separately under the attribution
                  methodology surface.
                </p>
              </>
            ),
          },
          {
            id: "benchmark-metadata",
            heading: "Benchmark metadata",
            body: (
              <p>
                <strong>Benchmark metadata</strong> records the comparison
                baselines that informed the envelope: the platform-reported
                value, the commerce-reported value, the difference, the
                tolerance applied, and any normalization (currency conversion,
                tax/shipping treatment). Benchmark metadata is descriptive — it
                does not change the deterministic value, but it is required for
                a reviewer to understand the reconciliation outcome.
              </p>
            ),
          },
          {
            id: "policy-authority",
            heading: "Policy authority",
            body: (
              <p>
                The <strong>policy authority</strong> field names which Skeldir
                policy governed this envelope: which attribution window applied,
                which currency conversion source was used, which tax/shipping
                treatment was in force, and which discrepancy tolerance was
                applied. Two envelopes computed under different policy authority
                versions will produce different deterministic values; the policy
                authority makes that explicit.
              </p>
            ),
          },
          {
            id: "fallback-reason",
            heading: "Fallback reason",
            body: (
              <p>
                If the engine could not fully reconcile a value and had to fall
                back to a degraded mode (e.g. a platform-only number when
                commerce evidence was missing), the envelope records a{" "}
                <strong>fallback reason</strong> describing what was missing and
                what assumption was used. Envelopes with a fallback reason are
                never marked <code>verified</code>.
              </p>
            ),
          },
          {
            id: "external-verification-metadata",
            heading: "External verification metadata",
            body: (
              <p>
                <strong>External verification metadata</strong> describes which
                external systems can independently re-verify the envelope: which
                Stripe account, which Shopify shop, which ad platform account,
                which third-party processor. It tells an auditor where to look
                to reproduce the value without depending on Skeldir's own
                storage.
              </p>
            ),
          },
          {
            id: "action-authority",
            heading: "Action authority",
            body: (
              <p>
                <strong>Action authority</strong> describes which downstream
                actions Skeldir is allowed to authorize on the basis of this
                envelope (e.g. budget reallocation thresholds, alert escalation,
                attribution adjustment). It is the contract between the
                envelope's confidence status and the operational decisions it
                may influence. AI agents that read the envelope must respect
                this field.
              </p>
            ),
          },
          {
            id: "audit-trail",
            heading: "Audit trail",
            body: (
              <p>
                The <strong>audit trail</strong> is the append-only sequence of
                envelope revisions: who or what produced each revision, when,
                under which policy authority version, and what the resulting
                semantic truth hash was. Combined with the provenance chain it
                lets an auditor walk a value backward to its evidence inputs and
                forward through every restatement.
              </p>
            ),
          },
        ]}
        limitations={
          <>
            <p>
              A TrustEnvelope describes deterministic financial truth as Skeldir
              has reconciled it. It does not assert truths Skeldir cannot
              measure: brand lift, incrementality beyond what the attribution
              methodology surface bounds, or any claim about a platform that
              Skeldir does not currently ingest.
            </p>
            <p>
              The envelope concept is implemented inside Skeldir's
              reconciliation engine. This page does not promise a public
              machine-callable Trust API endpoint; concrete API availability and
              versioning are documented separately on the API and documentation
              surfaces, and may be operator_approved on a per-integration basis.
            </p>
            <p>
              Confidence status is not a model probability. It is an enumerated
              verification state. Probabilistic ranges over attribution outcomes
              live on the attribution methodology surface, and never override
              the envelope's status enum.
            </p>
          </>
        }
      />
    </>
  );
}
