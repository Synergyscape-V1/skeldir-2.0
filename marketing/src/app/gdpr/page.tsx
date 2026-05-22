import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "GDPR | Skeldir",
  description: "Skeldir GDPR information is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/gdpr") },
};

export default function GdprPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="GDPR">
      <p>
        This URL is reserved for GDPR-related disclosures and workflows. Content is being prepared with legal review
        and is not published here yet.
      </p>
      <p>For data subject requests, contact privacy@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
