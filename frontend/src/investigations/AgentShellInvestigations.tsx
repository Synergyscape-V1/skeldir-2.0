import React from "react";
import type { AgentTheme } from "../comparison/agents";
import { ShellNavItems } from "../comparison/ShellNavItems";
import { InvestigationConsole } from "./InvestigationConsole";
import "./investigations.css";

const NAV_COLLAPSED_STORAGE_KEY = "skeldir.shellNav.collapsed";

export function AgentShellInvestigations({
  theme,
  density = 100,
}: {
  theme: AgentTheme;
  density?: 90 | 100;
  view?: "queue" | "detail";
}) {
  const [navCollapsed, setNavCollapsed] = React.useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const toggleNav = () => {
    const next = !navCollapsed;
    setNavCollapsed(next);
    try {
      window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
    } catch {
      // ignore
    }
  };

  return (
    <div
      className="agent-shell-root"
      style={
        {
          "--theme-bg": theme.bg,
          "--theme-panel": theme.panel,
          "--theme-panel-alt": theme.panelAlt,
          "--theme-border": theme.border,
          "--theme-text": theme.text,
          "--theme-muted": theme.textMuted,
          "--theme-accent": theme.accent,
          "--theme-gradient": theme.gradient,
          "--theme-font-heading": theme.fontHeading,
          "--theme-font-body": theme.fontBody,
          transform: `scale(${density / 100})`,
          transformOrigin: "top left",
        } as React.CSSProperties
      }
    >
      <header
        className="shell-nav"
        data-collapsed={navCollapsed}
        style={{ borderRightColor: theme.border }}
        onClick={toggleNav}
      >
        <div className="nav-header-row">
          <div
            className="nav-logo-toggle"
            onClick={toggleNav}
            role="button"
            tabIndex={0}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                toggleNav();
              }
            }}
          >
            <button
              type="button"
              className="nav-collapse-btn nav-logo-toggle-icon"
              aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"}
              onClick={toggleNav}
              style={{ color: theme.textMuted }}
            >
              <img
                src="/assets/hamburger-menu.svg"
                alt=""
                width="18"
                height="18"
                style={{ display: "block", opacity: 0.82 }}
              />
            </button>
            <a href="/" aria-label="Skeldir home" className="logo-link nav-logo-toggle-logo">
              <img
                src="/assets/Final_Skeldir_Logo__No_wording_.png"
                alt="Skeldir logo"
                style={{ height: 40, width: "auto", display: "block" }}
              />
            </a>
          </div>
        </div>
        <div className="nav-items-wrap">
          <nav className="nav-items" aria-label="Primary">
            <ShellNavItems activeRoute="Investigations" textColor={theme.text} />
          </nav>
        </div>
      </header>

      <main
        className="canvas"
        style={{ display: "block", padding: "20px clamp(16px, 2.5vw, 48px) 48px" }}
      >
        <div className="inv-page">
          <InvestigationConsole />
        </div>
      </main>
    </div>
  );
}
