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
