import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Careers | Skeldir",
  description: "Skeldir careers information is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/careers") },
};

export default function CareersPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Careers">
      <p>
        This URL is reserved for careers content. Skeldir is not publishing open roles or an applicant workflow on this
        placeholder page.
      </p>
      <p>For general inquiries, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
