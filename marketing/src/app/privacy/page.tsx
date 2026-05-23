import type { Metadata } from "next";
import { LegalPlaceholderPage } from "@/components/discoverability/LegalPlaceholderPage";
import { absoluteUrl } from "@/lib/siteCrawl";

const LAST_REVIEWED = "2026-05-23";

export const metadata: Metadata = {
  title: "Privacy | Skeldir — legal_review_required",
  description:
    "Reserved URL for the Skeldir privacy policy. Status: legal_review_required. We will not publish privacy language that has not been reviewed by legal counsel.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/privacy") },
};

export default function PrivacyPlaceholderPage() {
  return (
    <LegalPlaceholderPage
      headline="Privacy"
      description="This URL is reserved for the Skeldir privacy policy. The page is intentionally a placeholder while approved copy is being prepared with legal counsel."
      contactEmail="privacy@skeldir.com"
      owner="Skeldir Operator + Legal"
      lastReviewed={LAST_REVIEWED}
      body={
        <>
          <p>
            Skeldir handles operator-connected commerce, payment, and ad
            platform data, and is positioned in a financial-trust context. A
            published privacy policy at this URL needs to describe the actual
            data categories, retention, subprocessors, transfer mechanisms,
            and data subject rights — all of which require legal review
            before publication.
          </p>
          <p>
            Until that review is complete, this page deliberately does not
            assert any privacy guarantees. We do not claim "no PII", "zero
            data collection", or compliance certifications we have not
            earned. Anything more specific would be a legal claim, and a
            legal claim that has not been reviewed is worse than a missing
            page.
          </p>
        </>
      }
    />
  );
}
