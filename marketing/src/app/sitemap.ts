import type { MetadataRoute } from "next";
import manifest from "../../discoverability.sitemap-manifest.json";
import { articles } from "@/data/articlesData";
import { SITE_ORIGIN } from "@/lib/siteCrawl";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const origin = (manifest as { origin?: string }).origin ?? SITE_ORIGIN;
  const staticPaths = (manifest as { staticPaths?: string[] }).staticPaths ?? [];
  const hubRaw = (manifest as { hubLastmod?: string }).hubLastmod ?? "2026-05-22";
  const hubLastModified = new Date(`${hubRaw}T12:00:00.000Z`);

  const entries: MetadataRoute.Sitemap = [];

  for (const path of staticPaths) {
    const url = path === "/" ? `${origin}/` : `${origin}${path}`;
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
      url: `${origin}${path}`,
      lastModified: new Date(`${article.publishDate}T12:00:00.000Z`),
      changeFrequency: "monthly",
      priority: 0.7,
    });
  }

  return entries;
}
