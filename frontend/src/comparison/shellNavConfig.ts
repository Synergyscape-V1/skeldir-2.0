/**
 * Single source of truth for shell navigation.
 * All agent shells must use these routes so the nav is identical across views.
 */
export const SHELL_NAV_ROUTES = [
  "Command Center",
  "Channels",
  "Budget",
  "Data Health",
  "Investigations",
  "Settings",
] as const;

export type ShellNavRoute = (typeof SHELL_NAV_ROUTES)[number];

export const SHELL_NAV_ROUTE_ICONS: Record<ShellNavRoute, string> = {
  "Command Center": "CC",
  Channels: "Ch",
  Budget: "Bu",
  "Data Health": "DH",
  Investigations: "In",
  Settings: "St",
};

export const SHELL_NAV_ICON_SRC: Record<ShellNavRoute, string> = {
  "Command Center": "/assets/home-nav.svg",
  Channels: "/assets/comparison-nav.svg",
  Budget: "/assets/budget-nav.svg",
  "Data Health": "/assets/data-health-nav.svg",
  Investigations: "/assets/investigations-nav.svg",
  Settings: "/assets/settings-nav.svg",
};

export function shellNavRouteHref(route: ShellNavRoute): string {
  if (route === "Command Center") return "/";
  if (route === "Channels") return "/channels/compare";
  if (route === "Budget") return "/budget";
  if (route === "Data Health") return "/data";
  if (route === "Investigations") return "/investigations";
  if (route === "Settings") return "#";
  return "#";
}
