import React, { useMemo, useState } from "react";
import { formatRelativeTime } from "../../core/formatters";
import { STATUS_CONFIG } from "../../core/constants";
import type {
  PlatformIntegrationsRendererProps,
  Platform,
  PlatformStatus,
} from "../../core/types";
import "./styles.css";

/* ── Agent C: Conversational / Progressive Disclosure ──
   Complexity is earned, not imposed. Default card is minimal.
   Error details and config reveal through expand affordance.
   Paradigm: Notion · Linear issue cards · Stripe Dashboard */

function StatusBadge({ status }: { status: PlatformStatus }) {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      className={`pic-badge pic-badge-${status}`}
      role="status"
      aria-label={`Status: ${cfg.label}`}
    >
      <span className="pic-badge-dot" aria-hidden="true" />
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
  const [expanded, setExpanded] = useState(false);
  const { status, connectionDetails } = platform;
  const hasDetails =
    connectionDetails?.accountName ||
    connectionDetails?.accountId ||
    connectionDetails?.error;

  return (
    <article className="pic-card">
      {/* Default collapsed view */}
      <div className="pic-card-default">
        <div className="pic-card-head">
          <img
            className="pic-card-logo"
            src={platform.iconUrl}
            alt={`${platform.name} logo`}
            width={32}
            height={32}
          />
          <h3 className="pic-card-name">{platform.name}</h3>
          <StatusBadge status={status} />
        </div>

        {/* Syncing progress — always visible */}
        {status === "syncing" && connectionDetails?.syncProgress && (
          <div className="pic-progress">
            <div className="pic-progress-track">
              <div
                className="pic-progress-fill"
                style={{ width: `${connectionDetails.syncProgress.percentage}%` }}
              />
            </div>
            <div className="pic-progress-meta">
              <span>{connectionDetails.syncProgress.statusText}</span>
              <span className="pic-progress-pct">
                {connectionDetails.syncProgress.percentage}%
              </span>
            </div>
          </div>
        )}

        {/* Expand trigger — only when details exist */}
        {hasDetails && status !== "syncing" && (
          <button
            type="button"
            className="pic-expand-trigger"
            onClick={() => setExpanded((prev) => !prev)}
            aria-expanded={expanded}
            aria-controls={`detail-${platform.id}`}
          >
            <span
              className={`pic-expand-arrow ${expanded ? "pic-expand-arrow-open" : ""}`}
              aria-hidden="true"
            >
              &#9654;
            </span>
            {expanded ? "Hide details" : "View details"}
          </button>
        )}

        {/* Actions — always visible */}
        <div className="pic-card-actions">
          {status === "connected" && (
            <button
              type="button"
              className="pic-btn pic-btn-secondary pic-btn-full"
              onClick={() => onConfigure(platform.id)}
            >
              Configure
            </button>
          )}
          {status === "disconnected" && (
            <button
              type="button"
              className="pic-btn pic-btn-primary pic-btn-full"
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
              className="pic-btn pic-btn-danger pic-btn-full"
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
              className="pic-btn pic-btn-secondary pic-btn-full"
              disabled
            >
              Syncing&hellip;
            </button>
          )}
        </div>
      </div>

      {/* Expandable detail panel */}
      {hasDetails && (
        <div
          id={`detail-${platform.id}`}
          className={`pic-card-detail ${expanded ? "pic-card-detail-open" : ""}`}
          role="region"
          aria-label={`${platform.name} details`}
        >
          <div className="pic-card-detail-inner">
            {connectionDetails?.accountName && (
              <div className="pic-detail-row">
                <span className="pic-detail-label">Account</span>
                <span className="pic-detail-value">
                  {connectionDetails.accountName}
                </span>
              </div>
            )}
            {connectionDetails?.accountId && (
              <div className="pic-detail-row">
                <span className="pic-detail-label">Account ID</span>
                <span className="pic-detail-value">
                  {connectionDetails.accountId}
                </span>
              </div>
            )}
            {connectionDetails?.lastSyncAt && (
              <div className="pic-detail-row">
                <span className="pic-detail-label">Last synced</span>
                <span className="pic-detail-value">
                  {formatRelativeTime(connectionDetails.lastSyncAt)}
                </span>
              </div>
            )}
            {connectionDetails?.error && (
              <p className="pic-detail-error" role="alert">
                {connectionDetails.error.message}
              </p>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

export function AgentCPlatformIntegrations({
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
      <section className="pic-root pic-state" aria-busy="true" role="status">
        <div className="pic-skel pic-skel-header" />
        <div className="pic-skel pic-skel-banner" />
        <div className="pic-skel-grid">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="pic-skel pic-skel-card" />
          ))}
        </div>
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="pic-root pic-state" role="alert">
        <h2>Unable to Load Integrations</h2>
        <p>{state.error.message}</p>
        <button
          type="button"
          className="pic-btn pic-btn-primary"
          onClick={() => void onRetry()}
        >
          Retry
        </button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="pic-root pic-state">
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

  return (
    <section className={`pic-root pic-scenario-${scenario}`}>
      <header className="pic-header">
        <h1 className="pic-title">Platform Integrations</h1>
        <p className="pic-subtitle">
          Monitor and manage your marketing platform connections.
        </p>
      </header>

      {unhealthyCount > 0 && (
        <div className="pic-alert" role="alert" aria-live="polite">
          <span className="pic-alert-dot" aria-hidden="true" />
          <span>
            <strong>{unhealthyCount}</strong> platform
            {unhealthyCount > 1 ? "s" : ""} need
            {unhealthyCount === 1 ? "s" : ""} attention. Expand cards below for details.
          </span>
        </div>
      )}

      <div className="pic-grid">
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
