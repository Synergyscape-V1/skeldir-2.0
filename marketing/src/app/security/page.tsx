import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Security | Skeldir",
  description: "Skeldir security overview is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/security") },
};

export default function SecurityPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Security">
      <p>
        This URL is reserved for a public security overview (controls, subprocessors, and related artifacts). Content is
        being prepared and is not published here yet.
      </p>
      <p>For security inquiries, contact security@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
