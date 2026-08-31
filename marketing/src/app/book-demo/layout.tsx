import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Book a demo | Skeldir",
  description: "Schedule a Skeldir product walkthrough.",
  /**
   * D2-C2: defective contained route — noindex,follow without self-canonical (canonical + noindex
   * is an avoidable mixed signal). Crawl remains allowed so noindex is observable.
   */
  robots: { index: false, follow: true, googleBot: { index: false, follow: true } },
};

export default function BookDemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
