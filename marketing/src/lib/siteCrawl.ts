/**
 * @deprecated Import from `@/lib/crawlUrls` for new code. Re-exports preserved for incremental migration.
 */
export {
  SITE_ORIGIN,
  TRAILING_SLASH,
  normalizePath,
  canonicalUrl,
  sitemapUrl,
  robotsSitemapUrl,
  routeToOutputPath,
  assertTrailingSlashPolicy,
} from "./crawlUrls";

import { canonicalUrl } from "./crawlUrls";

/** @deprecated Prefer `canonicalUrl` from `@/lib/crawlUrls`. */
export function absoluteUrl(path: string): string {
  return canonicalUrl(path);
}
