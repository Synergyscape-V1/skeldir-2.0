import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Privacy | Skeldir",
  description: "Privacy information for Skeldir is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/privacy") },
};

export default function PrivacyPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Privacy">
      <p>
        This URL is reserved for the Skeldir privacy policy. Detailed policy text is being prepared with legal
        review and is not published here yet.
      </p>
      <p>For privacy questions, contact privacy@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
