import React from "react";
import { SHELL_NAV_ROUTES, SHELL_NAV_ICON_SRC, shellNavRouteHref, type ShellNavRoute } from "./shellNavConfig";

/** Sub-nav children for routes that have them */
const NAV_CHILDREN: Partial<Record<ShellNavRoute, { label: string; href: string; id: string }[]>> = {
  Budget: [
    { id: "budget-optimizer", label: "Optimizer", href: "/budget" },
    { id: "budget-scenarios", label: "Scenarios", href: "/budget/scenarios" },
  ],
};

interface ShellNavItemsProps {
  activeRoute: ShellNavRoute;
  /** For routes with children, which child is active (matched by id) */
  activeChild?: string;
  textColor: string;
}

export function ShellNavItems({ activeRoute, activeChild, textColor }: ShellNavItemsProps) {
  return (
    <>
      {SHELL_NAV_ROUTES.map((r) => {
        const iconSize = r === "Command Center" ? 22 : r === "Data Health" ? 21 : r === "Channels" ? 20 : 22;
        const isActive = r === activeRoute;
        const children = NAV_CHILDREN[r];

        return (
          <React.Fragment key={r}>
            <a
              href={shellNavRouteHref(r)}
              className={`nav-item${isActive ? " is-active" : ""}`}
              style={{ color: textColor }}
              onClick={(e) => e.stopPropagation()}
            >
              <span className="nav-icon" aria-hidden="true">
                <img src={SHELL_NAV_ICON_SRC[r]} alt="" width={iconSize} height={iconSize} style={{ display: "block" }} />
              </span>
              <span className="nav-label">{r}</span>
            </a>
            {isActive && children && (
              <div className="nav-children" onClick={(e) => e.stopPropagation()}>
                {children.map((child) => {
                  const isChildActive = activeChild === child.id;
                  return (
                    <a
                      key={child.id}
                      href={child.href}
                      className={`nav-child${isChildActive ? " nav-child--active" : ""}`}
                      style={{ color: textColor }}
                    >
                      {child.label}
                    </a>
                  );
                })}
              </div>
            )}
          </React.Fragment>
        );
      })}
    </>
  );
}
