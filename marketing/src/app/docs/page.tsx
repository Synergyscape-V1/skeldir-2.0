import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Documentation | Skeldir",
  description: "Skeldir product documentation is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/docs") },
};

export default function DocsPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Documentation">
      <p>
        This URL is reserved for public product documentation. Technical documentation is being prepared and is not
        published here yet.
      </p>
      <p>For access questions, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
