import React from "react";
import { useNavigate } from "react-router-dom";
import { useDataHealthData } from "../data-health/core/useDataHealthData";
import type { DataHealthScenario, DataHealthUiState } from "../data-health/core/types";
import { DataHealthDashboard } from "../data-health/design/DataHealthDashboard";
import type { AgentTheme } from "./agents";

import { ShellNavItems } from "./ShellNavItems";

const NAV_COLLAPSED_STORAGE_KEY = "skeldir.shellNav.collapsed";

export function AgentShellDataHealth({
  theme,
  scenario = "warning",
  uiState = "steady",
  stale = false,
  density = 100,
}: {
  theme: AgentTheme;
  scenario?: DataHealthScenario;
  uiState?: DataHealthUiState;
  stale?: boolean;
  density?: 90 | 100;
}) {
  const navigate = useNavigate();
  const { state, refetch } = useDataHealthData({ scenario, uiState, stale });
  const [navCollapsed, setNavCollapsed] = React.useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  return (
    <div
      className={`agent-shell-root data-health-shell data-health-shell-${theme.id.toLowerCase()}`}
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
        onClick={() => {
          const next = !navCollapsed;
          setNavCollapsed(next);
          try {
            window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
          } catch {
            // ignore
          }
        }}
      >
        <div className="nav-header-row">
          <div
            className="nav-logo-toggle"
            onClick={() => {
              const next = !navCollapsed;
              setNavCollapsed(next);
              try {
                window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
              } catch {
                // ignore
              }
            }}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                const next = !navCollapsed;
                setNavCollapsed(next);
                try {
                  window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
                } catch {
                  // ignore
                }
              }
            }}
          >
            <button
              type="button"
              className="nav-collapse-btn nav-logo-toggle-icon"
              aria-label={navCollapsed ? "Expand navigation" : "Collapse navigation"}
              onClick={() => {
                const next = !navCollapsed;
                setNavCollapsed(next);
                try {
                  window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
                } catch {
                  // ignore
                }
              }}
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
            <a
              href="/"
              aria-label="Skeldir home"
              className="logo-link nav-logo-toggle-logo"
            >
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
            <ShellNavItems activeRoute="Data Health" textColor={theme.text} />
          </nav>
        </div>
      </header>
      <main
        className="canvas data-health-cmp"
        style={{
          margin: 0,
          padding: 0,
          overflow: "auto",
        }}
      >
        <DataHealthDashboard
          state={state}
          scenario={scenario}
          onRefresh={refetch}
          onRetry={refetch}
          onNavigateToIntegrations={() => navigate("/data/integrations")}
        />
      </main>
    </div>
  );
}
