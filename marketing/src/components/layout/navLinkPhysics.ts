/** Header text-link interaction — single source of truth (no hover “pill” box) */

export const NAV_LINK_APPEARANCE = {
  solid: "solid",
  overlay: "overlay",
} as const;

export type NavLinkAppearance =
  (typeof NAV_LINK_APPEARANCE)[keyof typeof NAV_LINK_APPEARANCE];

export const NAV_TEXT_LINK_CLASS = "nav-text-link";

export const NAV_LINK_TRANSITION_MS = 200;

/** Resolved from header `data-nav-appearance` in globals.css */
export const NAV_LINK_COLORS = {
  solid: {
    default: "#1E293B",
    hover: "#2563EB",
  },
  overlay: {
    default: "#FFFFFF",
    hover: "#93C5FD",
  },
} as const;

export function navLinkAppearanceFromVisible(isVisible: boolean): NavLinkAppearance {
  return isVisible ? NAV_LINK_APPEARANCE.solid : NAV_LINK_APPEARANCE.overlay;
}

/**
 * App paths that render on a light/white background from the first paint.
 * The global header must use `data-nav-appearance="solid"` (dark link text +
 * white bar) on these routes — not `overlay` (white link text for hero pages).
 *
 * Home (`/`) and `/agencies` keep overlay-at-top until scroll. Methodology routes,
 * legal placeholders, pricing, resources, etc. are listed here.
 */
export const NAV_SOLID_FROM_LOAD_PREFIXES = [
  "/pricing",
  "/resources",
  "/book-demo",
  "/product",
  "/privacy",
  "/terms",
  "/gdpr",
  "/security",
  "/methodology",
  "/ai-boundary",
  "/trust-envelope",
  "/revenue-verification",
  "/attribution-methodology",
  "/discrepancy-taxonomy",
  "/docs",
  "/api",
  "/about",
  "/careers",
  "/press",
  "/status",
] as const;

/** @param pathname Next.js pathname (may be null during SSR) */
export function pathnameNeedsSolidNavFromLoad(pathname: string | null): boolean {
  if (!pathname) return false;
  return NAV_SOLID_FROM_LOAD_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}
