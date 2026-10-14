import type { Metadata } from "next";
import { LegalPlaceholderPage } from "@/components/discoverability/LegalPlaceholderPage";
import { absoluteUrl } from "@/lib/siteCrawl";

const LAST_REVIEWED = "2026-05-23";

export const metadata: Metadata = {
  title: "Terms of Service | Skeldir — legal_review_required",
  description:
    "Reserved URL for Skeldir terms of service. Status: legal_review_required. Formal terms are being prepared with legal counsel.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/terms") },
};

export default function TermsPlaceholderPage() {
  return (
    <LegalPlaceholderPage
      headline="Terms of Service"
      description="This URL is reserved for Skeldir terms of service. The page is a placeholder while approved terms are being prepared with legal counsel."
      contactEmail="sales@skeldir.com"
      owner="Skeldir Operator + Legal"
      lastReviewed={LAST_REVIEWED}
      body={
        <>
          <p>
            Public terms of service for a financial-trust product set
            obligations on use, acceptable conduct, dispute resolution,
            governing law, warranties, and limitations of liability. None
            of those are publishable without legal review.
          </p>
          <p>
            Until reviewed terms are published, the operational contract
            between Skeldir and an operator is the signed agreement
            negotiated with the Skeldir team. This page does not invent
            terms in the interim.
          </p>
        </>
      }
    />
  );
}
