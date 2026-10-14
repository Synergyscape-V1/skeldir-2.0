import type { Metadata } from "next";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Thank you | Skeldir",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: {
    canonical: absoluteUrl("/book-demo/thank-you"),
  },
};

export default function BookDemoThankYouLayout({ children }: { children: React.ReactNode }) {
  return children;
}
