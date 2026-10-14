import type { Metadata } from "next";
import Link from "next/link";
import { absoluteUrl } from "@/lib/siteCrawl";

export const metadata: Metadata = {
  title: "Page not found | Skeldir",
  robots: { index: false, follow: false, googleBot: { index: false, follow: false } },
  alternates: {
    canonical: absoluteUrl("/404"),
  },
};

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 bg-slate-50 p-8">
      <h1 className="text-2xl font-semibold text-slate-900">Page not found</h1>
      <p className="text-slate-600 text-center max-w-md">
        The page you requested is not part of the public marketing export.
      </p>
      <Link href="/" className="text-blue-700 underline">
        Back to home
      </Link>
    </div>
  );
}
