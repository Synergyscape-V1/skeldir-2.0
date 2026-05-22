import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Status | Skeldir",
  description: "Skeldir service status is not yet published at this URL.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/status") },
};

export default function StatusPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Status">
      <p>
        A public status page is not yet published at this URL. This placeholder exists so navigation labels do not
        point at unrelated marketing surfaces.
      </p>
      <p>If you need uptime information today, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
