import React, { useMemo, useState } from "react";
import { formatRelativeTime } from "../../core/formatters";
import { STATUS_CONFIG } from "../../core/constants";
import type {
  PlatformIntegrationsRendererProps,
  Platform,
  PlatformStatus,
} from "../../core/types";
import "./styles.css";

/* ── Agent D: Command Console / Operational Density ──
   Table/list hybrid. Power-user optimized. All 6 at a glance.
   Inline actions. Status filter. Bulk awareness.
   Paradigm: GitHub Actions · Vercel Deployments · AWS IAM */

type FilterValue = "all" | PlatformStatus;

export function AgentDPlatformIntegrations({
  state,
  scenario,
  onConnect,
  onReconnect,
  onDisconnect,
  onConfigure,
  onRetry,
}: PlatformIntegrationsRendererProps) {
  const [filter, setFilter] = useState<FilterValue>("all");

  if (state.type === "initial_loading") {
    return (
      <section className="pid-root pid-state" aria-busy="true" role="status">
        <div className="pid-skel pid-skel-header" />
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="pid-skel pid-skel-row" />
        ))}
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="pid-root pid-state" role="alert">
        <h2>Unable to Load Integrations</h2>
        <p>{state.error.message}</p>
        <button
          type="button"
          className="pid-btn pid-btn-primary"
          onClick={() => void onRetry()}
        >
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="pid-root pid-state">
        <h2>No Platforms Connected</h2>
        <p>
          Connect your ad platforms and revenue sources to start tracking
          attribution.
        </p>
      </section>
    );
  }

  const { platforms } = state.data;

  const statusCounts = useMemo(() => {
    const counts: Record<PlatformStatus, number> = {
      connected: 0,
      disconnected: 0,
      syncing: 0,
      error: 0,
    };
    for (const p of platforms) counts[p.status]++;
    return counts;
  }, [platforms]);

  const unhealthyCount = statusCounts.disconnected + statusCounts.error;

  const filtered = useMemo(
    () =>
      filter === "all"
        ? platforms
        : platforms.filter((p) => p.status === filter),
    [platforms, filter]
  );

  return (
    <section className={`pid-root pid-scenario-${scenario}`}>
      <div className="pid-header">
        <div>
          <h1 className="pid-title">Platform Integrations</h1>
          <p className="pid-subtitle">
            Monitor and manage your marketing platform connections.
          </p>
        </div>

        <div className="pid-filters">
          {(
            [
              ["all", "All", platforms.length],
              ["connected", "Connected", statusCounts.connected],
              ["syncing", "Syncing", statusCounts.syncing],
              ["error", "Errors", statusCounts.error],
              ["disconnected", "Disconnected", statusCounts.disconnected],
            ] as const
          ).map(([value, label, count]) =>
            count > 0 || value === "all" ? (
              <button
                key={value}
                type="button"
                className={`pid-filter-chip ${filter === value ? "pid-filter-chip-active" : ""}`}
                onClick={() => setFilter(value as FilterValue)}
              >
                {label}
                <span className="pid-filter-count">{count}</span>
              </button>
            ) : null
          )}
        </div>
      </div>

      {unhealthyCount > 0 && (
        <div className="pid-alert" role="alert" aria-live="polite">
          <span className="pid-alert-dot" aria-hidden="true" />
          <span>
            <strong>{unhealthyCount}</strong> platform
            {unhealthyCount > 1 ? "s" : ""} need
            {unhealthyCount === 1 ? "s" : ""} attention.
          </span>
        </div>
      )}

      {/* Summary strip */}
      <ul className="pid-summary">
        {(["connected", "syncing", "disconnected", "error"] as const).map(
          (s) =>
            statusCounts[s] > 0 ? (
              <li key={s} className="pid-summary-item">
                <span className={`pid-summary-dot pid-summary-dot-${s}`} />
                <span className="pid-summary-num">{statusCounts[s]}</span>
                {STATUS_CONFIG[s].label}
              </li>
            ) : null
        )}
      </ul>

      {/* Table */}
      <div className="pid-table" role="table" aria-label="Platform integrations">
        <div className="pid-table-head" role="row">
          <span role="columnheader">Platform</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Last Sync</span>
          <span role="columnheader">Details</span>
          <span role="columnheader">Actions</span>
        </div>

        {filtered.length === 0 && (
          <div className="pid-empty-filter">
            No platforms match the selected filter.
          </div>
        )}

        {filtered.map((platform) => (
          <PlatformRow
            key={platform.id}
            platform={platform}
            onConnect={onConnect}
            onReconnect={onReconnect}
            onConfigure={onConfigure}
          />
        ))}
      </div>
    </section>
  );
}

function PlatformRow({
  platform,
  onConnect,
  onReconnect,
  onConfigure,
}: {
  platform: Platform;
  onConnect: (id: string) => void;
  onReconnect: (id: string) => void;
  onConfigure: (id: string) => void;
}) {
  const { status, connectionDetails } = platform;
  const cfg = STATUS_CONFIG[status];

  return (
    <div className={`pid-table-row pid-table-row-${status}`} role="row">
      {/* Platform */}
      <div className="pid-cell-platform" role="cell">
        <img
          className="pid-cell-logo"
          src={platform.iconUrl}
          alt={`${platform.name} logo`}
          width={24}
          height={24}
        />
        <div>
          <span className="pid-cell-name">{platform.name}</span>
          <div className="pid-cell-desc">{platform.description}</div>
        </div>
      </div>

      {/* Status */}
      <div className="pid-cell-status" role="cell">
        <span
          className={`pid-status-dot pid-status-dot-${status}`}
          aria-hidden="true"
        />
        <span
          className="pid-status-label"
          role="status"
          aria-label={`Status: ${cfg.label}`}
        >
          {cfg.label}
        </span>
      </div>

      {/* Last sync */}
      <div className="pid-cell-sync" role="cell">
        {connectionDetails?.lastSyncAt
          ? formatRelativeTime(connectionDetails.lastSyncAt)
          : "\u2014"}
      </div>

      {/* Detail */}
      <div className="pid-cell-detail" role="cell">
        {status === "error" && connectionDetails?.error && (
          <span className="pid-cell-error-text">
            {connectionDetails.error.message}
          </span>
        )}
        {status === "disconnected" && connectionDetails?.error && (
          <span className="pid-cell-error-text">
            {connectionDetails.error.message}
          </span>
        )}
        {status === "syncing" && connectionDetails?.syncProgress && (
          <div className="pid-inline-progress">
            <div className="pid-inline-track">
              <div
                className="pid-inline-fill"
                style={{
                  width: `${connectionDetails.syncProgress.percentage}%`,
                }}
              />
            </div>
            <span className="pid-inline-pct">
              {connectionDetails.syncProgress.percentage}%
            </span>
          </div>
        )}
        {status === "connected" && connectionDetails?.accountName && (
          <span>{connectionDetails.accountName}</span>
        )}
      </div>

      {/* Actions */}
      <div className="pid-cell-actions" role="cell">
        {status === "connected" && (
          <button
            type="button"
            className="pid-btn pid-btn-secondary"
            onClick={() => onConfigure(platform.id)}
          >
            Configure
          </button>
        )}
        {status === "disconnected" && (
          <button
            type="button"
            className="pid-btn pid-btn-primary"
            onClick={() =>
              connectionDetails?.error?.canAutoReconnect
                ? onReconnect(platform.id)
                : onConnect(platform.id)
            }
          >
            {connectionDetails?.error?.canAutoReconnect
              ? "Reconnect"
              : "Connect"}
          </button>
        )}
        {status === "error" && (
          <button
            type="button"
            className="pid-btn pid-btn-danger"
            onClick={() =>
              connectionDetails?.error?.canAutoReconnect
                ? onReconnect(platform.id)
                : onConfigure(platform.id)
            }
          >
            {connectionDetails?.error?.canAutoReconnect
              ? "Reconnect"
              : "Resolve"}
          </button>
        )}
        {status === "syncing" && (
          <button type="button" className="pid-btn pid-btn-secondary" disabled>
            Syncing&hellip;
          </button>
        )}
      </div>
    </div>
  );
}
