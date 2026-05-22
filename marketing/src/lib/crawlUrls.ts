/**
 * Central URL authority for crawl-control surfaces (D2-C2).
 * Sitemap locs, HTML canonicals, robots Sitemap line, and harness expectations must derive from here.
 *
 * The discoverability harness reads `SITE_ORIGIN` from this file via regex — keep a single literal origin.
 */

export const SITE_ORIGIN = "https://skeldir.com";

/**
 * Must match `next.config` / app trailing-slash behavior. When false, non-root paths omit trailing `/`
 * in absolute URLs (except the sitemap root loc, which uses `https://skeldir.com/`).
 */
export const TRAILING_SLASH = false;

/** Normalize an app path: leading slash, strip trailing slash except root. */
export function normalizePath(path: string): string {
  let p = path.startsWith("/") ? path : `/${path}`;
  if (p.length > 1 && p.endsWith("/")) p = p.slice(0, -1);
  return p || "/";
}

/**
 * Absolute URL for HTML `<link rel="canonical">`, OpenGraph, and JSON-LD where applicable.
 * Root is `https://skeldir.com/`; other paths have no trailing slash when `TRAILING_SLASH` is false.
 */
export function canonicalUrl(path: string): string {
  const p = normalizePath(path);
  if (p === "/") return `${SITE_ORIGIN}/`;
  return `${SITE_ORIGIN}${p}`;
}

/** Sitemap `<loc>` URL — same shape as `canonicalUrl` for this site. */
export function sitemapUrl(path: string): string {
  return canonicalUrl(path);
}

/** Exact `Sitemap:` target for `robots.txt` (static export). */
export function robotsSitemapUrl(): string {
  return `${SITE_ORIGIN}/sitemap.xml`;
}

/**
 * Maps a logical app path to the relative path under `out/` for static export (no `trailingSlash` in next.config).
 * Used for documentation parity with harness `sitemapPathToOutRelative`.
 */
export function routeToOutputPath(logicalPath: string): string {
  const p = normalizePath(logicalPath);
  if (p === "/") return "index.html";
  if (p.startsWith("/resources/")) {
    const slug = p.slice("/resources/".length);
    if (!slug) throw new Error(`Invalid resources path: ${logicalPath}`);
    return `resources/${slug}.html`;
  }
  const clean = p.replace(/^\//, "");
  return `${clean}.html`;
}

export function assertTrailingSlashPolicy(path: string): void {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (!TRAILING_SLASH && p.length > 1 && p.endsWith("/")) {
    throw new Error(`Path must not end with / when TRAILING_SLASH is false: ${path}`);
  }
}
