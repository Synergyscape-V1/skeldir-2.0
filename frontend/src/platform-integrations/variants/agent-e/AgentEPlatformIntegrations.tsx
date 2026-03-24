import React, { useMemo } from "react";
import { formatRelativeTime, getStalenessLevel } from "../../core/formatters";
import { STATUS_CONFIG } from "../../core/constants";
import type {
  PlatformIntegrationsRendererProps,
  Platform,
  PlatformStatus,
} from "../../core/types";
import type { StalenessLevel } from "../../core/formatters";
import "./styles.css";

/* ── Agent E: Trust-Signal Centered ──
   Primary question: "How confident should you be in your attribution
   data right now?" Freshness, recency, and confidence signals lead.
   Paradigm: Grafana · Datadog SLO · Monte Carlo observability */

const STALENESS_LABEL: Record<StalenessLevel, string> = {
  fresh: "Data Fresh",
  stale: "Data Aging",
  critical: "Data Stale",
};

function StatusBadge({ status }: { status: PlatformStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={`pie-badge pie-badge-${status}`}
      role="status"
      aria-label={`Status: ${cfg.label}`}
    >
      <span className="pie-badge-dot" aria-hidden="true" />
      {cfg.label}
    </span>
  );
}

function FreshnessBlock({ platform }: { platform: Platform }) {
  const { status, connectionDetails } = platform;

  if (!connectionDetails?.lastSyncAt) return null;

  const staleness = getStalenessLevel(connectionDetails.lastSyncAt);
  const relTime = formatRelativeTime(connectionDetails.lastSyncAt);

  /* For error/disconnected, show data gap message instead of normal freshness */
  if (status === "error" || status === "disconnected") {
    return (
      <p className="pie-data-gap" role="alert">
        Data gap since {relTime}
        {connectionDetails.error ? ` \u2014 ${connectionDetails.error.message}` : ""}
      </p>
    );
  }

  if (status === "syncing") return null;

  return (
    <div className={`pie-freshness pie-freshness-${staleness}`}>
      <span className="pie-freshness-indicator" aria-hidden="true" />
      <div className="pie-freshness-text">
        <div className="pie-freshness-time">{relTime}</div>
        <div className="pie-freshness-label">{STALENESS_LABEL[staleness]}</div>
      </div>
    </div>
  );
}

function PlatformCard({
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

  return (
    <article className="pie-card">
      <div className="pie-card-head">
        <img
          className="pie-card-logo"
          src={platform.iconUrl}
          alt={`${platform.name} logo`}
          width={28}
          height={28}
        />
        <h3 className="pie-card-name">{platform.name}</h3>
        <StatusBadge status={status} />
      </div>

      {/* Freshness — the primary trust signal */}
      <FreshnessBlock platform={platform} />

      {/* Syncing progress — alongside freshness intent */}
      {status === "syncing" && connectionDetails?.syncProgress && (
        <div className="pie-progress">
          <div className="pie-progress-track">
            <div
              className="pie-progress-fill"
              style={{ width: `${connectionDetails.syncProgress.percentage}%` }}
            />
          </div>
          <div className="pie-progress-meta">
            <span>{connectionDetails.syncProgress.statusText}</span>
            <span className="pie-progress-pct">
              {connectionDetails.syncProgress.percentage}%
            </span>
          </div>
        </div>
      )}

      <div className="pie-card-actions">
        {status === "connected" && (
          <button
            type="button"
            className="pie-btn pie-btn-secondary pie-btn-full"
            onClick={() => onConfigure(platform.id)}
          >
            Configure
          </button>
        )}
        {status === "disconnected" && (
          <button
            type="button"
            className="pie-btn pie-btn-primary pie-btn-full"
            onClick={() =>
              connectionDetails?.error?.canAutoReconnect
                ? onReconnect(platform.id)
                : onConnect(platform.id)
            }
          >
            {connectionDetails?.error?.canAutoReconnect ? "Reconnect" : "Connect"}
          </button>
        )}
        {status === "error" && (
          <button
            type="button"
            className="pie-btn pie-btn-danger pie-btn-full"
            onClick={() =>
              connectionDetails?.error?.canAutoReconnect
                ? onReconnect(platform.id)
                : onConfigure(platform.id)
            }
          >
            {connectionDetails?.error?.canAutoReconnect
              ? "Reconnect"
              : "Resolve Issue"}
          </button>
        )}
        {status === "syncing" && (
          <button
            type="button"
            className="pie-btn pie-btn-secondary pie-btn-full"
            disabled
          >
            Syncing&hellip;
          </button>
        )}
      </div>
    </article>
  );
}

export function AgentEPlatformIntegrations({
  state,
  scenario,
  onConnect,
  onReconnect,
  onDisconnect,
  onConfigure,
  onRetry,
}: PlatformIntegrationsRendererProps) {
  if (state.type === "initial_loading") {
    return (
      <section className="pie-root pie-state" aria-busy="true" role="status">
        <div className="pie-skel pie-skel-header" />
        <div className="pie-skel pie-skel-banner" />
        <div className="pie-skel-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="pie-skel pie-skel-card" />
          ))}
        </div>
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="pie-root pie-state" role="alert">
        <h2>Unable to Load Integrations</h2>
        <p>{state.error.message}</p>
        <button
          type="button"
          className="pie-btn pie-btn-primary"
          onClick={() => void onRetry()}
        >
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="pie-root pie-state">
        <h2>No Platforms Connected</h2>
        <p>
          Connect your ad platforms and revenue sources to start tracking
          attribution.
        </p>
      </section>
    );
  }

  const { platforms } = state.data;

  const unhealthyCount = useMemo(
    () =>
      platforms.filter(
        (p) => p.status === "disconnected" || p.status === "error"
      ).length,
    [platforms]
  );

  /* Compute overall data trust score (% of platforms that are fresh or syncing) */
  const trustScore = useMemo(() => {
    let healthy = 0;
    for (const p of platforms) {
      if (p.status === "connected" && p.connectionDetails?.lastSyncAt) {
        const staleness = getStalenessLevel(p.connectionDetails.lastSyncAt);
        if (staleness === "fresh") healthy++;
      } else if (p.status === "syncing") {
        healthy += 0.5;
      }
    }
    return Math.round((healthy / platforms.length) * 100);
  }, [platforms]);

  const trustLevel: StalenessLevel =
    trustScore >= 70 ? "fresh" : trustScore >= 40 ? "stale" : "critical";

  return (
    <section className={`pie-root pie-scenario-${scenario}`}>
      <header className="pie-header">
        <h1 className="pie-title">Platform Integrations</h1>
        <p className="pie-subtitle">
          Data trust dashboard — how reliable is your attribution pipeline right now?
        </p>
      </header>

      {/* Trust score banner */}
      <div className="pie-trust-banner">
        <div>
          <div className="pie-trust-label">Data Trust Score</div>
          <div className={`pie-trust-value pie-trust-${trustLevel}`}>
            {trustScore}%
          </div>
        </div>
        <div className="pie-trust-bar">
          <div
            className={`pie-trust-fill pie-trust-fill-${trustLevel}`}
            style={{ width: `${trustScore}%` }}
          />
        </div>
        <div className="pie-trust-desc">
          {trustLevel === "fresh" && "Your attribution model is receiving reliable, fresh data."}
          {trustLevel === "stale" && "Some data sources are aging. Review connections below."}
          {trustLevel === "critical" && "Attribution confidence is degraded. Immediate action needed."}
        </div>
      </div>

      {unhealthyCount > 0 && (
        <div className="pie-alert" role="alert" aria-live="polite">
          <span className="pie-alert-icon" aria-hidden="true">!</span>
          <span>
            <strong>{unhealthyCount}</strong> platform
            {unhealthyCount > 1 ? "s" : ""} creating data gaps in your attribution model.
          </span>
        </div>
      )}

      <div className="pie-grid">
        {platforms.map((platform) => (
          <PlatformCard
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
