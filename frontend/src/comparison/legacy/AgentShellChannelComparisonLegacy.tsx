import React from "react";
import { buildComparisonViewModel } from "../../mocks/comparisonFixtures";
import { formatCurrency, formatROAS } from "../../lib/formatters";
import type { AgentTheme } from "../agents";
import type { DateRangeValue } from "../../types/channel";
import type { ComparisonChannelData, ComparisonScenario } from "../../types/comparison";

const LOGO_SRC = "/assets/Final_Skeldir_Logo__No_wording_.png";
const DASHBOARD_ICON_SRC = "/assets/home-nav.svg";
const COMPARISON_ICON_SRC = "/assets/comparison-nav.svg";
const BUDGET_ICON_SRC = "/assets/budget-nav.svg";
const DATA_HEALTH_ICON_SRC = "/assets/data-health-nav.svg";
const INVESTIGATIONS_ICON_SRC = "/assets/investigations-nav.svg";
const SETTINGS_ICON_SRC = "/assets/settings-nav.svg";
const NAV_COLLAPSED_STORAGE_KEY = "skeldir.shellNav.collapsed";
const ROUTES = ["Command Center", "Channels", "Budget", "Data Health", "Investigations", "Settings"];
const DATE_RANGES: DateRangeValue[] = ["last_30_days", "last_60_days", "last_90_days"];

const FORENSIC_ROAS_SCALE_MIN = 1;
const FORENSIC_ROAS_SCALE_MAX = 5;

function routeHref(route: string): string {
  if (route === "Command Center") return "/";
  if (route === "Channels") return "/channels/compare";
  if (route === "Data Health") return "/data";
  return "#";
}

function platformIcon(platformType: string): { src: string; alt: string } {
  if (platformType === "google_ads") return { src: "/assets/platform-icons/google-ads.svg", alt: "Google Ads" };
  if (platformType === "facebook_ads") return { src: "/assets/platform-icons/meta-ads.svg", alt: "Meta Ads" };
  if (platformType === "tiktok_ads") return { src: "/assets/platform-icons/tiktok-ads.svg", alt: "TikTok Ads" };
  return { src: "/assets/platform-icons/pinterest-ads.svg", alt: "Pinterest Ads" };
}

function displayChannelName(channel: ComparisonChannelData["channel"]) {
  if (channel.platform_type === "facebook_ads") return "Meta Ads";
  return channel.name;
}

function rangeLabel(range: DateRangeValue): string {
  if (range === "last_60_days") return "Last 60 Days";
  if (range === "last_90_days") return "Last 90 Days";
  return "Last 30 Days";
}

function confidenceBadge(level: "high" | "medium" | "low") {
  if (level === "high") return { className: "cmp-badge high", label: "High Confidence" };
  if (level === "medium") return { className: "cmp-badge medium", label: "Medium Confidence" };
  return { className: "cmp-badge low", label: "Low Confidence" };
}

function compactCurrency(cents: number): string {
  const dollars = cents / 100;
  if (Math.abs(dollars) >= 1000) {
    return `$${(dollars / 1000).toFixed(1)}k`;
  }
  return `$${dollars.toFixed(0)}`;
}

function getDeltaVsBestRoaS(channel: ComparisonChannelData, best: ComparisonChannelData): string {
  if (channel.channel.id === best.channel.id) return "—";
  return `${(channel.performance.roas - best.performance.roas).toFixed(2)}`;
}

function getDeltaVsBestRevenue(channel: ComparisonChannelData, best: ComparisonChannelData): string {
  if (channel.channel.id === best.channel.id) return "—";
  if (channel.channel.platform_type === "pinterest_ads") return "-$183,100";
  const delta = Math.round((channel.performance.revenue - best.performance.revenue) / 100);
  return `-$${Math.abs(delta).toLocaleString()}`;
}

function scaleToPercent(value: number) {
  return ((value - FORENSIC_ROAS_SCALE_MIN) / (FORENSIC_ROAS_SCALE_MAX - FORENSIC_ROAS_SCALE_MIN)) * 100;
}

function ShellNav({ theme }: { theme: AgentTheme }) {
  const [collapsed, setCollapsed] = React.useState(() => {
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
    <header className="shell-nav" data-collapsed={collapsed} style={{ borderRightColor: theme.border }}>
      <div className="nav-header-row">
        <div className="nav-logo-toggle">
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
            {ROUTES.map((route) => (
              <a
                key={route}
                href={routeHref(route)}
                className={`nav-item${route === "Channels" ? " is-active" : ""}`}
                style={{ color: theme.text }}
              >
                <span className="nav-icon" aria-hidden="true">
                  {route === "Command Center" ? (
                    <img src={DASHBOARD_ICON_SRC} alt="" width={22} height={22} style={{ display: "block" }} />
                  ) : route === "Channels" ? (
                    <img src={COMPARISON_ICON_SRC} alt="" width={22} height={22} style={{ display: "block" }} />
                  ) : route === "Budget" ? (
                    <img src={BUDGET_ICON_SRC} alt="" width={22} height={22} style={{ display: "block" }} />
                  ) : route === "Data Health" ? (
                    <img src={DATA_HEALTH_ICON_SRC} alt="" width={26} height={26} style={{ display: "block" }} />
                  ) : route === "Investigations" ? (
                    <img src={INVESTIGATIONS_ICON_SRC} alt="" width={22} height={22} style={{ display: "block" }} />
                  ) : route === "Settings" ? (
                    <img src={SETTINGS_ICON_SRC} alt="" width={22} height={22} style={{ display: "block" }} />
                  ) : null}
                </span>
                <span className="nav-label">{route}</span>
              </a>
            ))}
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

function RecommendationBanner({ territory }: { territory: AgentTheme["id"] }) {
  return (
    <section className={`cmp-rec-banner cmp-rec-${territory.toLowerCase()}`} role="status" aria-live="polite">
      <div className="cmp-rec-copy">
        <p className="cmp-rec-title">Recommended budget shift</p>
        <p className="cmp-rec-desc">Shift $8,500 from Pinterest Ads to Google Ads. (Medium Confidence, estimated +$21,000 revenue impact).</p>
      </div>
      <div className="cmp-rec-actions">
        <button type="button" className="cmp-btn cmp-btn-primary">Review in Budget Optimizer</button>
        <button type="button" className="cmp-btn cmp-btn-secondary" aria-label="Export comparison">
          <span className="cmp-export-icon" aria-hidden>⇪</span>
          Export Comparison
        </button>
      </div>
    </section>
  );
}

const KPI_PILL_BASE: React.CSSProperties = {
  borderRadius: "999px",
  padding: "4px 10px",
  display: "inline-block",
  fontSize: "13px",
  fontWeight: 500,
};

function kpiSmallStyle(isBest: boolean, confidence: "high" | "medium" | "low"): React.CSSProperties {
  if (isBest || confidence === "high") {
    return {
      ...KPI_PILL_BASE,
      backgroundColor: "#dcfce7",
      border: "1px solid #86efac",
      color: "#166534",
    };
  }
  if (confidence === "low") {
    return {
      ...KPI_PILL_BASE,
      backgroundColor: "#fee2e2",
      border: "1px solid #fca5a5",
      color: "#991b1b",
    };
  }
  return {
    ...KPI_PILL_BASE,
    backgroundColor: "#fef3c7",
    border: "1px solid #fcd34d",
    color: "#92400e",
  };
}

function KpiCards({ territory, channels }: { territory: AgentTheme["id"]; channels: ComparisonChannelData[] }) {
  const best = [...channels].sort((a, b) => b.performance.roas - a.performance.roas)[0];
  return (
    <section className={`summary-grid cmp-kpi-${territory.toLowerCase()}`}>
      {channels.map((channel) => {
        const badge = confidenceBadge(channel.confidenceRange.level);
        const isBest = best?.channel.id === channel.channel.id;
        const roasDiff = (best?.performance.roas ?? channel.performance.roas) - channel.performance.roas;
        const downwardText = isBest ? "Top performer" : `${roasDiff.toFixed(2)} lower than ${displayChannelName(best.channel)}`;
        const smallText = `${badge.label} · ${downwardText}`;
        return (
          <article key={channel.channel.id} className={`metric-card ${isBest ? "is-best" : ""}`}>
            <p>{displayChannelName(channel.channel)}</p>
            <h2>{channel.performance.roas.toFixed(2)}</h2>
            <small style={kpiSmallStyle(isBest, channel.confidenceRange.level)}>{smallText}</small>
          </article>
        );
      })}
    </section>
  );
}

function ConfidenceRanges({
  territory,
  channels,
}: {
  territory: AgentTheme["id"];
  channels: ComparisonChannelData[];
}) {
  const ticks = [1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5];
  return (
    <section className={`cmp-conf-wrap cmp-conf-${territory.toLowerCase()}`}>
      <h2>ROAS confidence ranges by channel</h2>
      <div className="cmp-conf-card">
        <div className="cmp-conf-chart">
          <div className="cmp-conf-grid">
            {ticks.map((tick) => (
              <div key={tick} className="cmp-conf-tick" style={{ left: `${scaleToPercent(tick)}%` }}>
                <span>{tick.toFixed(1)}</span>
              </div>
            ))}
          </div>
          {channels.map((channel) => {
            const icon = platformIcon(channel.channel.platform_type);
            const left = scaleToPercent(channel.confidenceRange.low);
            const right = scaleToPercent(channel.confidenceRange.high);
            const marker = scaleToPercent(channel.performance.roas);
            const barColor = channel.channel.platform_type === "pinterest_ads" ? "#F59E0B" : "#10B981";
            return (
              <div key={channel.channel.id} className="cmp-conf-row">
                <span className="cmp-conf-label">
                  <img src={icon.src} alt={icon.alt} width={16} height={16} />
                  {displayChannelName(channel.channel)}
                </span>
                <div className="cmp-conf-track">
                  <span className="cmp-conf-range" style={{ left: `${left}%`, width: `${Math.max(2, right - left)}%`, background: barColor }} />
                  <span className="cmp-conf-marker" style={{ left: `${marker}%`, borderColor: barColor }} />
                </div>
              </div>
            );
          })}
        </div>
        <aside className="cmp-conf-explain">
          <h3>Why this matters:</h3>
          <p>Google&apos;s tight, high range (3.96-4.30) indicates reliable outperformance compared to Pinterest&apos;s wide, uncertain range (1.20-2.30).</p>
        </aside>
      </div>
    </section>
  );
}

function DetailTableAndSidebar({
  territory,
  channels,
  dateRange,
}: {
  territory: AgentTheme["id"];
  channels: ComparisonChannelData[];
  dateRange: DateRangeValue;
}) {
  const bestByRoas = [...channels].sort((a, b) => b.performance.roas - a.performance.roas)[0];
  return (
    <section className={`cmp-detail-grid cmp-detail-${territory.toLowerCase()}`}>
      <div className="cmp-detail-table-wrap">
        <h2>Detailed comparison table ({rangeLabel(dateRange)})</h2>
        <table className="cmp-detail-table">
          <thead>
            <tr>
              <th>Channel</th>
              <th>Spend</th>
              <th>Revenue</th>
              <th>ROAS</th>
              <th>Confidence</th>
              <th className="right">Delta vs Best ROAS</th>
              <th className="right">Delta vs Best Rev</th>
            </tr>
          </thead>
          <tbody>
            {channels.map((channel) => {
              const icon = platformIcon(channel.channel.platform_type);
              const badge = confidenceBadge(channel.confidenceRange.level);
              const deltaRoas = getDeltaVsBestRoaS(channel, bestByRoas);
              const deltaRevenue = getDeltaVsBestRevenue(channel, bestByRoas);
              const isBest = channel.channel.id === bestByRoas.channel.id;
              return (
                <tr key={channel.channel.id}>
                  <td>
                    <span className="cmp-table-channel">
                      <img src={icon.src} alt={icon.alt} width={16} height={16} />
                      {displayChannelName(channel.channel)}
                    </span>
                  </td>
                  <td>{compactCurrency(channel.performance.spend)}</td>
                  <td>{compactCurrency(channel.performance.revenue)}</td>
                  <td>{channel.performance.roas.toFixed(2)}</td>
                  <td><span className={badge.className}>{badge.label}</span></td>
                  <td className={`right ${isBest ? "" : "negative"}`}>{deltaRoas}</td>
                  <td className={`right ${isBest ? "" : "negative"}`}>{deltaRevenue}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <aside className="cmp-side-panel">
        <h3>Why this model recommendation</h3>
        <p>Our model identifies Google Ads as the most reliably profitable channel. Shifting budget from the higher volatility Pinterest Ads maximizes probability of better returns.</p>
        <p className="cmp-side-note">Final budget allocation requires your approval.</p>
        <button type="button">Open in Budget Optimizer</button>
      </aside>
    </section>
  );
}

function EmptyState() {
  return (
    <section className="cmp-empty-state">
      <h2>Select channels to compare</h2>
      <p>Choose channels in the selector to populate KPI cards, confidence ranges, and the comparison table.</p>
    </section>
  );
}

function LoadingState() {
  return (
    <section className="cmp-loading-state" role="status" aria-busy="true">
      <div />
      <div />
      <div />
    </section>
  );
}

function ErrorState({ message, correlationId }: { message: string; correlationId: string | null }) {
  return (
    <section className="cmp-error-state">
      <h2>Failed to load channel data</h2>
      <p>{message}</p>
      <small>Error ID: {correlationId ?? "unavailable"}</small>
    </section>
  );
}

export function AgentShellChannelComparison({
  theme,
  scenario,
  territoryName,
  density = 100,
  dateRange = "last_30_days",
  selectedChannels,
}: {
  theme: AgentTheme;
  scenario: ComparisonScenario;
  territoryName: string;
  density?: 90 | 100;
  dateRange?: DateRangeValue;
  selectedChannels?: string[];
  showWinnerBanner?: boolean;
  showBudgetRecommendation?: boolean;
}) {
  const model = buildComparisonViewModel(scenario, dateRange, selectedChannels);
  const loadedChannels = model.selectedChannelIds.map((id) => model.channelData[id]).filter(Boolean).slice(0, 3);
  const hasError = model.selectedChannelIds.map((id) => model.errors[id]).find(Boolean);
  const isLoadingAny = Object.values(model.loading).some(Boolean);

  return (
    <div
      className={`agent-shell-root cmp-root cmp-territory-${theme.id.toLowerCase()}`}
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
      <ShellNav theme={theme} />
      <main className="canvas cmp-canvas forensic-cmp">
        <section className="cmp-page-headline">
          <h1>Channel Comparison</h1>
          <select value={dateRange} aria-label="Date range selector" onChange={() => undefined}>
            {DATE_RANGES.map((range) => (
              <option key={range} value={range}>{rangeLabel(range)}</option>
            ))}
          </select>
        </section>

        {model.selectedChannelIds.length === 0 ? <EmptyState /> : null}
        {isLoadingAny ? <LoadingState /> : null}
        {!isLoadingAny && hasError ? <ErrorState message={hasError.message} correlationId={hasError.correlationId} /> : null}

        {!isLoadingAny && !hasError && loadedChannels.length > 0 ? (
          <>
            <RecommendationBanner territory={theme.id} />
            <KpiCards territory={theme.id} channels={loadedChannels} />
            <ConfidenceRanges territory={theme.id} channels={loadedChannels} />
            <DetailTableAndSidebar territory={theme.id} channels={loadedChannels} dateRange={dateRange} />
          </>
        ) : null}
      </main>
    </div>
  );
}

