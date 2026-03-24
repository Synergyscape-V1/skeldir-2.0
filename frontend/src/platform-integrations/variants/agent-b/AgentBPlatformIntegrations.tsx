import React, { useMemo } from "react";
import { formatRelativeTime } from "../../core/formatters";
import { STATUS_CONFIG } from "../../core/constants";
import type {
  PlatformIntegrationsRendererProps,
  Platform,
  PlatformStatus,
} from "../../core/types";
import "./styles.css";

/* ── Agent B: Status-First Visual Hierarchy ──
   Health signal arrives before conscious reading.
   Color + icon + border = pre-attentive processing.
   Paradigm: PagerDuty · Datadog · AWS Health Dashboard */

const STATUS_ICON: Record<PlatformStatus, string> = {
  connected: "\u2713",
  disconnected: "\u2013",
  syncing: "\u21BB",
  error: "!",
};

function StatusBadge({ status }: { status: PlatformStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={`pib-badge pib-badge-${status}`}
      role="status"
      aria-label={`Status: ${cfg.label}`}
    >
      <span className="pib-badge-icon" aria-hidden="true">
        {STATUS_ICON[status]}
      </span>
      {cfg.label}
    </span>
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
    <article className={`pib-card pib-card-${status}`}>
      <div className="pib-card-stripe" />
      <div className="pib-card-body">
        <div className="pib-card-head">
          <div className="pib-card-logo-wrap">
            <img
              className="pib-card-logo"
              src={platform.iconUrl}
              alt={`${platform.name} logo`}
              width={36}
              height={36}
            />
            <span
              className={`pib-status-ring pib-status-ring-${status}`}
              aria-hidden="true"
            >
              {STATUS_ICON[status]}
            </span>
          </div>
          <div className="pib-card-title-block">
            <h3 className="pib-card-name">{platform.name}</h3>
            <StatusBadge status={status} />
          </div>
        </div>

        <p className="pib-card-desc">{platform.description}</p>

        {connectionDetails?.lastSyncAt && status !== "syncing" && (
          <span className="pib-card-meta">
            Last synced: {formatRelativeTime(connectionDetails.lastSyncAt)}
          </span>
        )}

        {status === "error" && connectionDetails?.error && (
          <p className="pib-card-error-box" role="alert">
            {connectionDetails.error.message}
          </p>
        )}

        {status === "disconnected" && connectionDetails?.error && (
          <p className="pib-card-error-box" role="alert">
            {connectionDetails.error.message}
          </p>
        )}

        {status === "syncing" && connectionDetails?.syncProgress && (
          <div className="pib-progress">
            <div className="pib-progress-track">
              <div
                className="pib-progress-fill"
                style={{ width: `${connectionDetails.syncProgress.percentage}%` }}
              />
            </div>
            <div className="pib-progress-info">
              <span>{connectionDetails.syncProgress.statusText}</span>
              <span className="pib-progress-pct">
                {connectionDetails.syncProgress.percentage}%
              </span>
            </div>
          </div>
        )}

        <div className="pib-card-actions">
          {status === "connected" && (
            <button
              type="button"
              className="pib-btn pib-btn-secondary pib-btn-full"
              onClick={() => onConfigure(platform.id)}
            >
              Configure
            </button>
          )}
          {status === "disconnected" && (
            <button
              type="button"
              className={`pib-btn pib-btn-full ${connectionDetails?.error?.canAutoReconnect ? "pib-btn-reconnect" : "pib-btn-primary"}`}
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
              className="pib-btn pib-btn-primary pib-btn-full"
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
              className="pib-btn pib-btn-secondary pib-btn-full"
              disabled
            >
              Syncing&hellip;
            </button>
          )}
        </div>
      </div>
    </article>
  );
}

export function AgentBPlatformIntegrations({
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
      <section className="pib-root pib-state" aria-busy="true" role="status">
        <div className="pib-skel pib-skel-header" />
        <div className="pib-skel pib-skel-banner" />
        <div className="pib-skel-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="pib-skel pib-skel-card" />
          ))}
        </div>
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="pib-root pib-state" role="alert">
        <h2>Unable to Load Integrations</h2>
        <p>{state.error.message}</p>
        <button type="button" className="pib-btn pib-btn-primary" onClick={() => void onRetry()}>
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="pib-root pib-state">
        <h2>No Platforms Connected</h2>
        <p>Connect your ad platforms and revenue sources to start tracking attribution.</p>
      </section>
    );
  }

  const { platforms } = state.data;
  const unhealthyCount = useMemo(
    () => platforms.filter((p) => p.status === "disconnected" || p.status === "error").length,
    [platforms],
  );

  return (
    <section className={`pib-root pib-scenario-${scenario}`}>
      <header className="pib-header">
        <h1 className="pib-title">Platform Integrations</h1>
        <p className="pib-subtitle">
          Monitor and manage your marketing platform connections.
        </p>
      </header>

      {unhealthyCount > 0 && (
        <div className="pib-alert" role="alert" aria-live="polite">
          <span className="pib-alert-icon" aria-hidden="true">!</span>
          <span>
            <strong>Action Required:</strong> {unhealthyCount} platform
            {unhealthyCount > 1 ? "s" : ""} need{unhealthyCount === 1 ? "s" : ""}{" "}
            attention. Reconnect to resume data syncing.
          </span>
        </div>
      )}

      <div className="pib-grid">
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
