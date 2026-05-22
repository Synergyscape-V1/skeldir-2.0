import type { Metadata } from "next";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Book a demo | Skeldir",
  description: "Schedule a Skeldir product walkthrough.",
  /** Defective static shell remains client-heavy — exclude from index until repaired (D2-C). Crawl allowed so noindex is observable. */
  robots: { index: false, follow: true, googleBot: { index: false, follow: true } },
  alternates: {
    canonical: absoluteUrl("/book-demo"),
  },
};

export default function BookDemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
