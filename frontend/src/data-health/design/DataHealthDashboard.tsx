import React, { useMemo, useState } from "react";
import type { DataHealthRendererProps } from "../core/types";
import { DashboardHeader } from "./DashboardHeader";
import { HealthScoreBanner } from "./HealthScoreBanner";
import { PerIntegrationStatusGrid } from "./PerIntegrationStatusGrid";
import { buildIntegrationStatusSeed } from "./integrationStatusGridMock";
import { FixGuidanceStack } from "./FixGuidanceStack";
import { FIX_GUIDANCE_SEED, seedRowsToProps } from "./fixGuidanceData";
import { RevenueMatching } from "./RevenueMatching";
import { DataFreshness } from "./DataFreshness";
import "./styles.css";

export function DataHealthDashboard({
  state,
  scenario,
  onRefresh,
  onRetry,
  onNavigateToIntegrations,
}: DataHealthRendererProps) {
  const [dismissedFixIds, setDismissedFixIds] = useState<string[]>([]);
  const [lastUpdated] = useState("3 min ago");

  const fixGuidanceCards = useMemo(
    () =>
      seedRowsToProps(
        FIX_GUIDANCE_SEED.filter((row) => !dismissedFixIds.includes(row.id)),
        {
          onNavigate: () => onNavigateToIntegrations(),
          onDismiss: (id) => setDismissedFixIds((prev) => (prev.includes(id) ? prev : [...prev, id])),
        },
      ),
    [dismissedFixIds, onNavigateToIntegrations],
  );

  const hasFixCards = fixGuidanceCards.length > 0;

  const integrationStatusCards = useMemo(
    () =>
      buildIntegrationStatusSeed({
        onNavigate: () => onNavigateToIntegrations(),
        onSyncNow: () => onNavigateToIntegrations(),
      }),
    [onNavigateToIntegrations],
  );

  const handleRefresh = () => {
    onRefresh();
  };

  /* ── Loading ─────────────────────────────────────────────── */
  if (state.type === "initial_loading") {
    return (
      <div className="dhd-root" aria-busy="true" role="status">
        <div className="dhd-skeleton-grid">
          <div className="dhd-skeleton dhd-skeleton-metric" />
          <div className="dhd-skeleton dhd-skeleton-metric" />
          <div className="dhd-skeleton dhd-skeleton-metric" />
          <div className="dhd-skeleton dhd-skeleton-metric" />
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "5fr 7fr", gap: 16 }}>
          <div className="dhd-skeleton dhd-skeleton-panel" />
          <div className="dhd-skeleton dhd-skeleton-panel" />
        </div>
      </div>
    );
  }

  /* ── Error ───────────────────────────────────────────────── */
  if (state.type === "error") {
    return (
      <div className="dhd-root">
        <div className="dhd-state-screen" role="alert">
          <p className="dhd-state-title">Unable to Load Data Health</p>
          <p className="dhd-state-desc">{state.error.message}</p>
          <button
            type="button"
            className="dhd-action-btn dhd-action-btn-primary"
            onClick={() => void onRetry()}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  /* ── No data ─────────────────────────────────────────────── */
  if (state.type === "no_data") {
    return (
      <div className="dhd-root">
        <div className="dhd-state-screen">
          <p className="dhd-state-title">No Data Health Metrics</p>
          <p className="dhd-state-desc">
            Connect at least one platform to activate data health tracking.
          </p>
          <button
            type="button"
            className="dhd-action-btn dhd-action-btn-primary"
            onClick={onNavigateToIntegrations}
          >
            Connect Platform
          </button>
        </div>
      </div>
    );
  }

  /* ── Steady state — new design ─────────────────────────── */
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "transparent",
        padding: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Top bar: first child, same position as Command Center TopBar */}
      <DashboardHeader lastUpdated={lastUpdated} onRefresh={handleRefresh} />

      {/* Content: same horizontal inset (24px) as TopBar for alignment */}
      <div
        style={{
          width: "100%",
          padding: "28px 24px 48px 24px",
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: "28px",
        }}
      >
        {/* Health Score Banner */}
        <HealthScoreBanner score={74} threshold={70} timestamp="09:14:22" />

        {/* Per-Integration Status Grid — Interface 8 / Constitution §7.1 */}
        <PerIntegrationStatusGrid
          integrations={integrationStatusCards}
          sortBy="severity"
          onCardClick={() => onNavigateToIntegrations()}
          onRefreshAll={handleRefresh}
        />

        {/* Fix Guidance + Right Column (strict 2-column macro layout) */}
        <div
          style={{
            display: "grid",
            /* Equal columns so .fgc-root matches .rmb-root width (same as Revenue Matching block) */
            gridTemplateColumns: hasFixCards ? "minmax(0, 1fr) minmax(0, 1fr)" : "1fr",
            gap: "16px",
            alignItems: "start",
          }}
        >
          {/* Left: Fix Guidance (only when there are active cards) */}
          {hasFixCards && (
            <FixGuidanceStack
              cards={fixGuidanceCards}
              maxVisible={3}
              sortOrder="severity_desc"
              filter="all"
              onViewAll={() => onNavigateToIntegrations()}
            />
          )}

          {/* Right: Revenue Matching + Data Freshness */}
          <div style={{ display: "flex", flexDirection: "column", gap: "12px", minHeight: 0 }}>
            <RevenueMatching
              onRowClick={() => onNavigateToIntegrations()}
              onExport={() => onNavigateToIntegrations()}
            />
            <DataFreshness
              onIntegrationClick={() => onNavigateToIntegrations()}
              onSyncNow={() => onNavigateToIntegrations()}
              onLogsClick={() => onNavigateToIntegrations()}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
