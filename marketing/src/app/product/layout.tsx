import type { Metadata } from "next";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Product | Skeldir",
  description: "Decision intelligence for smarter ad spend with Skeldir.",
  alternates: {
    canonical: absoluteUrl("/product"),
  },
};

export default function ProductLayout({ children }: { children: React.ReactNode }) {
  return children;
}
