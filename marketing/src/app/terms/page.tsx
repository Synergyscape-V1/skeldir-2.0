import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Terms of Service | Skeldir",
  description: "Skeldir terms of service are being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/terms") },
};

export default function TermsPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Terms of Service">
      <p>
        This URL is reserved for Skeldir terms of service. Formal terms are being prepared with legal review and are
        not published here yet.
      </p>
      <p>For contractual questions, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
