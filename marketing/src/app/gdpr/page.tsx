import type { Metadata } from "next";
import { LegalPlaceholderPage } from "@/components/discoverability/LegalPlaceholderPage";
import { absoluteUrl } from "@/lib/siteCrawl";

const LAST_REVIEWED = "2026-05-23";

export const metadata: Metadata = {
  title: "Privacy rights & GDPR | Skeldir — legal_review_required",
  description:
    "Reserved URL for Skeldir privacy rights / GDPR disclosures and data subject request workflow. Status: legal_review_required.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/gdpr") },
};

export default function GdprPlaceholderPage() {
  return (
    <LegalPlaceholderPage
      headline="Privacy rights & GDPR"
      description="This URL is reserved for Skeldir's GDPR / privacy rights disclosures and the data subject request workflow. The page is a placeholder while approved copy is being prepared with legal counsel."
      contactEmail="privacy@skeldir.com"
      owner="Skeldir Operator + Legal"
      lastReviewed={LAST_REVIEWED}
      body={
        <>
          <p>
            GDPR / privacy-rights disclosures need to describe data subject
            rights, lawful basis, controller / processor relationships,
            subprocessor lists, international transfer mechanisms, and the
            mechanics of submitting a data subject request. Publishing any
            of those without legal review would risk asserting rights or
            workflows we cannot guarantee.
          </p>
          <p>
            Data subject requests submitted in the interim should be sent
            to the privacy address below; they will be received, logged,
            and handled under the framework being prepared. We do not
            assert GDPR conformance on this site until the disclosure has
            been reviewed and approved.
          </p>
        </>
      }
    />
  );
}
