import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "TrustEnvelope | Skeldir",
  description: "TrustEnvelope public overview is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/trust-envelope") },
};

export default function TrustEnvelopePlaceholderPage() {
  return (
    <PlaceholderDocPage headline="TrustEnvelope">
      <p>
        This URL is reserved for a public TrustEnvelope overview. Detailed technical material is being prepared and is
        not published here yet.
      </p>
      <p>For product questions, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
