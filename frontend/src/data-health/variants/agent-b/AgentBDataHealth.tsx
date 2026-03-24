import React, { useMemo, useState } from "react";
import { computeMetricStatus } from "../../core/healthStatus";
import { formatRelativeTime } from "../../core/formatters";
import {
  METRICS,
  INTEGRATIONS,
  SEVERITY_ORDER,
  SEVERITY_TITLE,
  SEVERITY_IMPACT,
  SEVERITY_STATUS,
  SEVERITY_ACTION,
  metricConfidence,
  grouped,
} from "../../core/constants";
import type { DataHealthRendererProps, DataIssue, MetricStatus } from "../../core/types";
import "./styles.css";

/* ── Agent B: Signal Console ──
   Monitoring-console rails with inline SVG sparklines.
   Monospace readouts, uppercase section labels, console panel aesthetic. */

function Sparkline({ status, width = 120, height = 36 }: { status: MetricStatus; width?: number; height?: number }) {
  const points = useMemo(() => {
    const seeds: Record<MetricStatus, number[]> = {
      good: [0.3, 0.35, 0.4, 0.38, 0.5, 0.6, 0.7, 0.75, 0.82, 0.9],
      warning: [0.5, 0.55, 0.6, 0.45, 0.4, 0.5, 0.42, 0.48, 0.38, 0.42],
      critical: [0.8, 0.75, 0.65, 0.6, 0.5, 0.45, 0.35, 0.3, 0.25, 0.2],
    };
    const values = seeds[status];
    const stepX = width / (values.length - 1);
    return values.map((v, i) => `${i * stepX},${height - v * height}`).join(" ");
  }, [status, width, height]);

  const color =
    status === "good"
      ? "var(--dhb-success)"
      : status === "warning"
        ? "var(--dhb-warning)"
        : "var(--dhb-danger)";

  return (
    <svg className="dhb-sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function DisconnectedLine({ width = 120, height = 36 }: { width?: number; height?: number }) {
  const y = height / 2;
  return (
    <svg className="dhb-sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <line x1="0" y1={y} x2={width} y2={y} stroke="var(--dhb-danger)" strokeWidth="2" strokeDasharray="6,4" />
    </svg>
  );
}

function IssueRows({ issues }: { issues: DataIssue[] }) {
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  return (
    <div className="dhb-rows" role="table" aria-label="Issue rows">
      {issues.map((issue) => {
        const hasGuide = (issue.fixGuide?.steps.length ?? 0) > 0;
        const isOpen = expandedRow === issue.id;
        return (
          <div key={issue.id} className={`dhb-row dhb-row-${issue.severity}`} role="row">
            <div className="dhb-cell dhb-issue-cell" role="cell">
              <span className={`dhb-severity dhb-severity-${issue.severity}`}>
                {SEVERITY_TITLE[issue.severity]}
              </span>
              <div>
                <p>{issue.title}</p>
                <small>{issue.affectedEntity}</small>
              </div>
            </div>
            <div className="dhb-cell" role="cell">{SEVERITY_IMPACT[issue.severity]}</div>
            <div className="dhb-cell" role="cell">{SEVERITY_STATUS[issue.severity]}</div>
            <div className="dhb-cell dhb-actions" role="cell">
              <button type="button" className="dhb-btn dhb-btn-primary">
                {SEVERITY_ACTION[issue.severity]}
              </button>
              {hasGuide && (
                <button
                  type="button"
                  className="dhb-btn dhb-btn-link"
                  aria-expanded={isOpen}
                  onClick={() => setExpandedRow(isOpen ? null : issue.id)}
                >
                  {isOpen ? "Hide Guide" : "Learn More"}
                </button>
              )}
            </div>
            {hasGuide && isOpen && (
              <div className="dhb-fix" role="row">
                <ol role="list">
                  {(issue.fixGuide?.steps ?? []).map((step) => (
                    <li key={step.stepNumber} role="listitem">
                      <span>{step.stepNumber}</span>
                      <div>
                        <p>{step.instruction}</p>
                        {step.codeSnippet && <pre><code>{step.codeSnippet}</code></pre>}
                        {step.resourceLink && (
                          <a href={step.resourceLink.url} target="_blank" rel="noopener noreferrer">
                            {step.resourceLink.text}
                          </a>
                        )}
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function AgentBDataHealth({
  state,
  scenario,
  onRefresh,
  onNavigateToIntegrations,
  onRetry,
}: DataHealthRendererProps) {
  const issueGroups = useMemo(
    () => (state.type === "steady" ? grouped(state.data.issues) : { critical: [], warning: [], info: [] }),
    [state],
  );

  if (state.type === "initial_loading") {
    return (
      <section className="dhb-root dhb-state" aria-busy="true" role="status">
        <div className="dhb-skeleton dhb-skeleton-rail" />
        <div className="dhb-skeleton dhb-skeleton-rail" />
        <div className="dhb-skeleton dhb-skeleton-rail" />
      </section>
    );
  }

  if (state.type === "error") {
    return (
      <section className="dhb-root dhb-state" role="alert">
        <h2>Unable to Load Data Health</h2>
        <p>{state.error.message}</p>
        <button type="button" className="dhb-btn dhb-btn-primary" onClick={() => void onRetry()}>Retry</button>
      </section>
    );
  }

  if (state.type === "no_data") {
    return (
      <section className="dhb-root dhb-state">
        <h2>No Data Health Metrics Available</h2>
        <p>Connect at least one platform to activate data health tracking.</p>
        <button type="button" className="dhb-btn dhb-btn-primary" onClick={onNavigateToIntegrations}>
          Connect Platform
        </button>
      </section>
    );
  }

  const { data, stale } = state;

  return (
    <section className={`dhb-root dhb-scenario-${scenario}`}>
      {/* ── Console top accent bar is via CSS border-top ── */}

      <header className="dhb-header">
        <div>
          <h1 className="dhb-title">Data Health</h1>
          <p className="dhb-sync">Last sync: {formatRelativeTime(data.lastUpdated)}</p>
        </div>
        <button type="button" className="dhb-btn dhb-btn-primary" onClick={() => void onRefresh()}>
          Test All Connections
        </button>
      </header>

      {stale && (
        <div className="dhb-stale" role="status" aria-live="polite">
          <p>Data health last updated over 24 hours ago. Metrics may be outdated.</p>
          <button type="button" className="dhb-btn dhb-btn-secondary" onClick={() => void onRefresh()}>
            Refresh Now
          </button>
        </div>
      )}

      {/* ── System Health — Metric Cards (Command Center style) ── */}
      <section className="dhb-section">
        <h3 className="dhb-section-label">System Health Overview Section</h3>
        <div className="dhb-metric-grid">
          {METRICS.map((metric) => {
            const value = data[metric.key];
            const status = computeMetricStatus(value, metric.target);
            return (
              <article key={metric.key} className={`dhb-metric-card dhb-metric-card-${status}`}>
                <p>{metric.title}</p>
                <h2>{metric.key === "utmConsistency" ? `${value}/100` : `${value}%`}</h2>
                <span className={`dhb-badge dhb-badge-${status}`}>{metricConfidence(status)}</span>
              </article>
            );
          })}
        </div>
      </section>

      {/* ── Platform Integrations — Console Panel ── */}
      <section className="dhb-section">
        <div className="dhb-section-header-row">
          <h3 className="dhb-section-label">Platform Integrations Section</h3>
          <button
            type="button"
            className="dhb-btn dhb-btn-link dhb-section-action"
            onClick={onNavigateToIntegrations}
          >
            Manage Integrations <span aria-hidden="true">&rarr;</span>
          </button>
        </div>
        <div className="dhb-console-panel">
          {INTEGRATIONS.map((integration) => {
            const isConnected = integration.level === "connected";
            return (
              <div key={integration.id} className="dhb-integration-rail">
                <img src={integration.icon} alt={`${integration.name} logo`} width={16} height={16} className="dhb-integration-logo" />
                <span className="dhb-rail-name">{integration.name}</span>
                <div className="dhb-rail-spark-sm" />
                <span className={`dhb-badge dhb-badge-${integration.level}`}>{integration.status}</span>
                <span className="dhb-rail-detail">{integration.detail}</span>
                <div className="dhb-rail-actions">
                  <button type="button" className="dhb-btn dhb-btn-secondary">{integration.primaryAction}</button>
                  {integration.secondaryAction && (
                    <button type="button" className="dhb-btn dhb-btn-ghost">{integration.secondaryAction}</button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Data Quality — Tiles ── */}
      <section className="dhb-section">
        <h3 className="dhb-section-label">Data Quality Monitor Section</h3>
        <div className="dhb-issues-tiles">
          {SEVERITY_ORDER.map((severity) => {
            const items = issueGroups[severity];
            if (items.length === 0) return null;
            return (
              <article key={severity} className={`dhb-issues-tile dhb-issues-tile-${severity}`}>
                <IssueRows issues={items} />
              </article>
            );
          })}
        </div>
      </section>
    </section>
  );
}
