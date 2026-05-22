/**
 * App Router–aware URL resolution for D0 inventory.
 * Does NOT naively map filesystem paths to URLs.
 *
 * Rules applied (Next.js App Router):
 * - Route groups `(name)` are excluded from URL path
 * - Parallel route slots `@slot` are excluded from URL path
 * - Intercepting routes `(.)`, `(..)`, `(...)` are route-segment-relative;
 *   when encountered, caller should mark unknown_requires_resolution unless
 *   explicitly resolved by build output cross-check.
 * - Dynamic segments `[slug]` preserved in pattern
 * - `page.tsx` / `route.ts` at app root → `/`
 */

const INTERCEPTING_PREFIXES = ["(.)", "(..)", "(...)"];

/**
 * @param {string} segment
 * @returns {boolean}
 */
export function isRouteGroup(segment) {
  return segment.startsWith("(") && segment.endsWith(")") && !isInterceptingSegment(segment);
}

/**
 * @param {string} segment
 * @returns {boolean}
 */
export function isParallelSlot(segment) {
  return segment.startsWith("@");
}

/**
 * @param {string} segment
 * @returns {boolean}
 */
export function isInterceptingSegment(segment) {
  return INTERCEPTING_PREFIXES.some((p) => segment.startsWith(p));
}

/**
 * Resolve a path relative to `src/app` containing `page.tsx` to a Next.js route pattern.
 * @param {string} pageRelativePath e.g. "resources/[slug]/page.tsx" or "(marketing)/pricing/page.tsx"
 * @returns {{ routePattern: string, hasIntercepting: boolean, hasAmbiguity: boolean, segments: string[] }}
 */
export function resolvePagePathToRoutePattern(pageRelativePath) {
  const normalized = pageRelativePath.replace(/\\/g, "/");
  if (!normalized.endsWith("/page.tsx") && normalized !== "page.tsx") {
    throw new Error(`Not a page file: ${pageRelativePath}`);
  }

  const dir = normalized === "page.tsx" ? "" : normalized.slice(0, -"/page.tsx".length);
  const rawSegments = dir ? dir.split("/").filter(Boolean) : [];

  let hasIntercepting = false;
  let hasAmbiguity = false;
  const urlSegments = [];

  for (const seg of rawSegments) {
    if (isRouteGroup(seg)) {
      continue;
    }
    if (isParallelSlot(seg)) {
      continue;
    }
    if (isInterceptingSegment(seg)) {
      hasIntercepting = true;
      hasAmbiguity = true;
      continue;
    }
    urlSegments.push(seg);
  }

  const routePattern = urlSegments.length === 0 ? "/" : `/${urlSegments.join("/")}`;
  return { routePattern, hasIntercepting, hasAmbiguity, segments: urlSegments };
}

/**
 * Convert static export HTML path under `out/` to logical route.
 * @param {string} relativePath from out/ e.g. "resources/foo.html" or "index.html"
 */
export function outHtmlPathToRoute(relativePath) {
  const p = relativePath.replace(/\\/g, "/");
  if (p === "index.html") return "/";
  if (p.endsWith(".html")) {
    const withoutExt = p.slice(0, -".html".length);
    return `/${withoutExt}`;
  }
  if (p.endsWith("/index.html")) {
    const without = p.slice(0, -"/index.html".length);
    return without ? `/${without}` : "/";
  }
  return null;
}

/**
 * Convert public static HTML path to route (if index.html).
 */
export function publicHtmlPathToRoute(relativePath) {
  const p = relativePath.replace(/\\/g, "/");
  if (p.endsWith("/index.html")) {
    return outHtmlPathToRoute(p);
  }
  return null;
}

/**
 * Expand dynamic pattern using concrete slugs.
 * @param {string} pattern e.g. "/resources/[slug]"
 * @param {string[]} slugs
 */
export function expandDynamicRoutes(pattern, slugs) {
  if (!pattern.includes("[slug]")) return [pattern];
  return slugs.map((slug) => pattern.replace("[slug]", slug));
}
