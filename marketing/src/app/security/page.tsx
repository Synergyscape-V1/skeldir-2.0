import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Security | Skeldir",
  description:
    "This URL is reserved for Skeldir security disclosures. Content is being prepared and is not published here yet.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/security") },
};

export default function SecurityPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Security">
      <p>
        This URL is reserved for Skeldir security and technical disclosure content. Content is being
        prepared and is not published here yet.
      </p>
      <p>
        This placeholder exists so footer and navigation links resolve to a real page rather than a
        404. For security or procurement questions today, contact security@skeldir.com.
      </p>
    </PlaceholderDocPage>
  );
}
