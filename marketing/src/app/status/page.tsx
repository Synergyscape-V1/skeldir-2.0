import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Status | Skeldir",
  description:
    "This URL is reserved for Skeldir service status. Content is being prepared and is not published here yet.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/status") },
};

export default function StatusPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Status">
      <p>
        This URL is reserved for a public service status page. Content is being prepared and is not
        published here yet.
      </p>
      <p>
        This placeholder exists so navigation labels resolve to a real page rather than unrelated
        marketing surfaces. For uptime questions today, contact sales@skeldir.com.
      </p>
    </PlaceholderDocPage>
  );
}
