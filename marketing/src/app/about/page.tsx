import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "About | Skeldir",
  description: "Skeldir company overview is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/about") },
};

export default function AboutPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="About">
      <p>
        This URL is reserved for a concise company overview. Content is being prepared and is not published here yet.
      </p>
      <p>For background on the product, see the Product page.</p>
    </PlaceholderDocPage>
  );
}
