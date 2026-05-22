import type { Metadata } from "next";
import { PlaceholderDocPage } from "@/components/discoverability/PlaceholderDocPage";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Press | Skeldir",
  description: "Skeldir press information is being prepared.",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: { canonical: absoluteUrl("/press") },
};

export default function PressPlaceholderPage() {
  return (
    <PlaceholderDocPage headline="Press">
      <p>This URL is reserved for press materials. Content is being prepared and is not published here yet.</p>
      <p>For press inquiries, contact press@skeldir.com.</p>
    </PlaceholderDocPage>
  );
}
