import type { MetadataRoute } from "next";
import manifest from "../../discoverability.sitemap-manifest.json";
import { articles } from "@/data/articlesData";
import { SITE_ORIGIN, sitemapUrl } from "@/lib/crawlUrls";

/** Static export contract: fail the build if Next would treat this route as dynamic. */
export const dynamic = "error";

export default function sitemap(): MetadataRoute.Sitemap {
  const manifestOrigin = (manifest as { origin?: string }).origin;
  if (manifestOrigin !== undefined && manifestOrigin !== SITE_ORIGIN) {
    throw new Error(
      `discoverability.sitemap-manifest.json origin must equal SITE_ORIGIN from crawlUrls.ts (got ${manifestOrigin})`,
    );
  }

  const hubRaw = (manifest as { hubLastmod?: string }).hubLastmod ?? "2026-05-22";
  const hubLastModified = new Date(`${hubRaw}T12:00:00.000Z`);

  const entries: MetadataRoute.Sitemap = [];
  const staticPaths = (manifest as { staticPaths?: string[] }).staticPaths ?? [];

  for (const path of staticPaths) {
    const url = sitemapUrl(path);
    entries.push({
      url,
      lastModified: hubLastModified,
      changeFrequency: path === "/" ? "weekly" : "monthly",
      priority: path === "/" ? 1 : 0.8,
    });
  }

  for (const article of articles) {
    const path = `/resources/${article.slug}`;
    entries.push({
      url: sitemapUrl(path),
      lastModified: new Date(`${article.publishDate}T12:00:00.000Z`),
      changeFrequency: "monthly",
      priority: 0.7,
    });
  }

  return entries;
}
