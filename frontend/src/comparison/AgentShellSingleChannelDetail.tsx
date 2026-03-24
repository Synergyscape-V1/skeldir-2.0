import React, { useState } from "react";
import { useParams } from "react-router-dom";
import type { AgentTheme } from "./agents";
import type { ChannelDetailScenario } from "../types/channel";
import type { ChannelDatasetVariant } from "../mocks/channelDetailFixtures";
import ChannelDetailContent from "../channel-detail/ChannelDetailContent";
import { ShellNavItems } from "./ShellNavItems";

/* ── Constants ── */
const LOGO_SRC = "/assets/Final_Skeldir_Logo__No_wording_.png";
const NAV_COLLAPSED_STORAGE_KEY = "skeldir.shellNav.collapsed";

/* ── Shell Navigation (shared sidebar) ── */
function ShellNav({ theme }: { theme: AgentTheme }) {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return window.localStorage.getItem(NAV_COLLAPSED_STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });

  const setCollapsedAndPersist = React.useCallback((next: boolean) => {
    setCollapsed(next);
    try {
      window.localStorage.setItem(NAV_COLLAPSED_STORAGE_KEY, next ? "1" : "0");
    } catch {
      // ignore
    }
  }, []);

  return (
    <header
      className="shell-nav"
      data-collapsed={collapsed}
      style={{ borderRightColor: theme.border }}
      onClick={() => setCollapsedAndPersist(!collapsed)}
    >
      <div className="nav-header-row">
        <div
          className="nav-logo-toggle"
          onClick={() => setCollapsedAndPersist(!collapsed)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setCollapsedAndPersist(!collapsed);
            }
          }}
        >
          <button
            type="button"
            className="nav-collapse-btn nav-logo-toggle-icon"
            aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
            onClick={() => setCollapsedAndPersist(!collapsed)}
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
              src={LOGO_SRC}
              alt="Skeldir logo"
              style={{ height: 40, width: "auto", display: "block" }}
            />
          </a>
        </div>
      </div>
      <div className="nav-items-wrap">
        <nav className="nav-items" aria-label="Primary">
          <ShellNavItems activeRoute="Channels" textColor={theme.text} />
        </nav>
      </div>
      <div className="nav-aux" style={{ color: theme.textMuted }}>
        <button type="button" className="profile-btn" aria-label="Profile menu">
          <svg className="profile-btn-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
            <circle cx="12" cy="12" r="10" />
            <path d="M12 14a4 4 0 0 0 4-4 4 4 0 0 0-4-4 4 4 0 0 0-4 4 4 4 0 0 0 4 4z" />
            <path d="M6.168 18.849A4 4 0 0 1 10 16h4a4 4 0 0 1 3.834 2.855" />
          </svg>
        </button>
        <button type="button" className="help-btn" aria-label="Help">?</button>
      </div>
    </header>
  );
}

/* ── Main Export ── */
export function AgentShellSingleChannelDetail({
  theme,
  scenario,
  dataset = "mixed",
  density = 100,
}: {
  theme: AgentTheme;
  scenario: ChannelDetailScenario;
  dataset?: ChannelDatasetVariant;
  density?: 90 | 100;
}) {
  const { channelId: urlChannelId } = useParams<{ channelId?: string }>();
  return (
    <div
      className="agent-shell-root"
      style={{
        ["--theme-bg" as string]: theme.bg,
        ["--theme-panel" as string]: theme.panel,
        ["--theme-panel-alt" as string]: theme.panelAlt,
        ["--theme-border" as string]: theme.border,
        ["--theme-text" as string]: theme.text,
        ["--theme-muted" as string]: theme.textMuted,
        ["--theme-accent" as string]: theme.accent,
        ["--theme-gradient" as string]: theme.gradient,
        ["--theme-font-heading" as string]: theme.fontHeading,
        ["--theme-font-body" as string]: theme.fontBody,
        transform: `scale(${density / 100})`,
        transformOrigin: "top left",
      } as React.CSSProperties}
    >
      <ShellNav theme={theme} />
      <main
        className="canvas detail-canvas"
        style={{
          overflow: "auto",
          minHeight: "auto",
          margin: 0,
          padding: 0,
          paddingBottom: 28,
          background: "transparent",
        }}
      >
        <ChannelDetailContent channelId={urlChannelId} />
      </main>
    </div>
  );
}
