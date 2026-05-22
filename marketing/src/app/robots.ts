import type { MetadataRoute } from "next";
import { SITE_ORIGIN } from "@/lib/siteCrawl";

export const dynamic = "force-static";

/**
 * Root robots.txt for static export.
 * - Public marketing/resources remain crawlable.
 * - /implementations/ is disallow-listed as defense-in-depth (review HTML also carries noindex).
 * - Retrieval vs training/bulk crawler policy: explicit allows for common retrieval UAs; broader
 *   training-crawler tuning is deferred to Phase D3 (do not add sensitive path disclosure here).
 */
export default function robots(): MetadataRoute.Robots {
  const sitemap = `${SITE_ORIGIN}/sitemap.xml`;
  const disallowReview = ["/implementations/"];

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: disallowReview,
      },
      { userAgent: "Googlebot", allow: "/" },
      { userAgent: "Googlebot-Image", allow: "/" },
      { userAgent: "OAI-SearchBot", allow: "/" },
      { userAgent: "Claude-SearchBot", allow: "/" },
      { userAgent: "PerplexityBot", allow: "/" },
      { userAgent: "GPTBot", allow: "/" },
    ],
    host: "skeldir.com",
    sitemap,
  };
}
