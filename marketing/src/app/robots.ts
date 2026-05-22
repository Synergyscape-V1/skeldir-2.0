import type { MetadataRoute } from "next";
import { robotsSitemapUrl } from "@/lib/crawlUrls";

export const dynamic = "error";

/**
 * Root robots.txt for static export.
 * - Public marketing/resources remain crawlable.
 * - Do NOT Disallow paths that rely on HTML `<meta name="robots" content="noindex">` for index
 *   exclusion: crawlers that obey Disallow never fetch the page and cannot observe noindex
 *   (Google Search guidance). Review artifacts under /implementations/* were removed from
 *   `public/` (D2-C) instead of combining Disallow + noindex.
 * - Retrieval vs training/bulk crawler policy: explicit allows for common retrieval UAs; broader
 *   training-crawler tuning is deferred to Phase D3 (do not add sensitive path disclosure here).
 */
export default function robots(): MetadataRoute.Robots {
  const sitemap = robotsSitemapUrl();

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
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
