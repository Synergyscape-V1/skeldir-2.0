/** Production origin for canonicals, sitemap, and robots (static export). */
export const SITE_ORIGIN = "https://skeldir.com";

export function absoluteUrl(path: string): string {
  const p = path.startsWith("/") ? path : `/${path}`;
  if (p === "/") return `${SITE_ORIGIN}/`;
  return `${SITE_ORIGIN}${p}`;
}
