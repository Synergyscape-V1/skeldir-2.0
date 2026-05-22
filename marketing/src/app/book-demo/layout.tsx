import type { Metadata } from "next";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Book a demo | Skeldir",
  description: "Schedule a Skeldir product walkthrough.",
  alternates: {
    canonical: absoluteUrl("/book-demo"),
  },
};

export default function BookDemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
