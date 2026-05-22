import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "API reference | Skeldir",
  description: "Skeldir static API reference is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/api") },
};

/**
 * Static marketing route at `/api` (HTML). This is not the runtime Trust API backend.
 */
export default function ApiDocsPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="API reference">
      <p>
        This URL is reserved for a static, export-safe API reference for integrators. It is not a live API endpoint and
        does not execute server handlers in the marketing export.
      </p>
      <p>For integration planning, contact sales@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
